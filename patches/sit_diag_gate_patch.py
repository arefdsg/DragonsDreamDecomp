#!/usr/bin/env python3
"""
Dragon's Dream sit-freeze DIAGNOSTIC gate-bypass patch.

Background
----------
After exhaustive analysis (see memory/sit-freeze-2026-04-29-breakthrough.md),
the actual sit-freeze gate is at FUN_06030CEC (the polling function called
from FUN_06036B6C state 0). It reads byte at 0x06067D58; if non-zero, returns
0xFFFE which causes state 0 to stay forever, locking the table list.

This is a DIAGNOSTIC patch — it bypasses the gate so the state machine can
progress, allowing the server to capture which messages/fields the production
game depended on. Once those are identified and fixed in the server, this
patch is reverted.

The patch
---------
At 0x06030CEC (file offset 0x20CEC), the gate-check is::

    06030CEC  sts.l pr,@-r15
    06030CEE  mov.l @(...,pc),r2     ; r2 = 0x06067D58
    06030CF0  mov.b @r2,r3            ; r3 = byte at 0x06067D58 (gate)
    06030CF2  tst r3,r3               ; T := (r3 == 0)
    06030CF4  bf 0x06030CFE           ; 8B 03 — if gate != 0, return 0xFFFE
    06030CF6  bsr ...                 ; (gate clear path: do real work)
    06030CF8  nop
    06030CFA  bra 0x06030D00
    06030CFC  mov r0,r4               ; (delay slot)
    06030CFE  mov #-2,r4              ; <-- bf target: r4 = -2 (= 0xFFFE)
    06030D00  lds.l @r15+,pr
    06030D02  rts
    06030D04  extu.w r4,r0

We replace the ``bf 0x06030CFE`` (2-byte ``8B 03``) at offset 0x20CF4 with
``nop`` (``00 09``). The gate check still runs but its result is ignored —
control always falls through to the BSR, which performs the real work
regardless of gate state.

This is a single 2-byte patch in 0.BIN and in the Mode1/2352 CD image.

Usage
-----
Default (auto-discover under DD-Saturn-bincue and extracted)::

    py -3 sit_diag_gate_patch.py

Pass a specific directory to patch::

    py -3 sit_diag_gate_patch.py "D:\\DragonsDreamDecomp\\DD-Saturn-bincue"

Re-running is safe — already-patched files are detected and skipped.

Reverting
---------
Each target file has a ``.pre_sit_diag_gate.bak`` sibling. To revert::

    py -3 sit_diag_gate_patch.py --revert

Or copy the ``.bak`` files manually over the originals.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import struct
import sys
from pathlib import Path

# ----- patch constants -----------------------------------------------------

# Mem 0x06030CF4 -> file 0x20CF4 (image base 0x06010000)
PATCH_OFFSET_IN_0BIN = 0x20CF4
EXPECTED_PRE_BYTES = b"\x8B\x03"     # bf 0x06030CFE
PATCHED_BYTES = b"\x00\x09"          # nop

# Anchor for finding the patch site in a CD image. 16 bytes starting at
# 0x06030CEC (= file 0x20CEC) — the entire FUN_06030CEC function body.
#   4F22 sts.l pr,@-r15
#   D238 mov.l @(0xE4,pc),r2     ; r2 = 0x06067D58
#   6320 mov.b @r2,r3             ; r3 = byte at gate
#   2338 tst r3,r3
#   8B03 bf 0x06030CFE            ; <-- patch site (becomes 0009 nop)
#   BEC2 bsr -> 0x06030A7E
#   0009 nop
#   A001 bra -> 0x06030D00
ANCHOR_OFFSET_IN_0BIN = 0x20CEC
ANCHOR_BYTES_PRE = bytes.fromhex("4f22d2386320233 8 8b03 bec20009a001".replace(" ", ""))
ANCHOR_BYTES_POST = bytes.fromhex("4f22d2386320233 8 0009 bec20009a001".replace(" ", ""))

MODE1_SECTOR_BYTES = 2352
MODE1_USER_DATA_OFFSET = 16  # 12-byte sync + 4-byte header
MODE1_USER_DATA_SIZE = 2048

BACKUP_SUFFIX = ".pre_sit_diag_gate.bak"

# ----- helpers --------------------------------------------------------------


def _verify_anchor(data: bytes, file_offset: int) -> str:
    """Return one of: 'pre', 'post', 'mismatch'."""
    chunk = data[file_offset:file_offset + len(ANCHOR_BYTES_PRE)]
    if chunk == ANCHOR_BYTES_PRE:
        return "pre"
    if chunk == ANCHOR_BYTES_POST:
        return "post"
    return "mismatch"


def _patch_0bin(path: Path) -> str:
    with open(path, "rb") as f:
        data = bytearray(f.read())

    state = _verify_anchor(data, ANCHOR_OFFSET_IN_0BIN)
    if state == "post":
        return f"already patched"
    if state == "mismatch":
        actual = bytes(data[ANCHOR_OFFSET_IN_0BIN:ANCHOR_OFFSET_IN_0BIN + 16]).hex()
        return f"ANCHOR MISMATCH at file 0x{ANCHOR_OFFSET_IN_0BIN:X}: got {actual}"

    bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not bak.exists():
        shutil.copy2(path, bak)

    data[PATCH_OFFSET_IN_0BIN:PATCH_OFFSET_IN_0BIN + len(PATCHED_BYTES)] = PATCHED_BYTES

    with open(path, "wb") as f:
        f.write(bytes(data))

    return f"patched (backup: {bak.name})"


def _patch_cd_image(path: Path) -> str:
    with open(path, "rb") as f:
        data = bytearray(f.read())

    # Search for the anchor in the CD image. We have to skip Mode1 sector
    # boundaries: the anchor data must lie entirely within ONE 2048-byte
    # user-data span.
    # Strategy: scan for ANCHOR_BYTES_PRE; for each hit, verify the bytes
    # don't cross a sector boundary, then patch.
    pre_offsets = []
    post_offsets = []
    pre_pat = ANCHOR_BYTES_PRE
    post_pat = ANCHOR_BYTES_POST
    i = 0
    while i < len(data) - len(pre_pat):
        if data[i:i + len(pre_pat)] == pre_pat:
            pre_offsets.append(i)
            i += 1
            continue
        if data[i:i + len(post_pat)] == post_pat:
            post_offsets.append(i)
            i += 1
            continue
        i += 1

    if post_offsets and not pre_offsets:
        return f"already patched ({len(post_offsets)} hit(s) at 0x{post_offsets[0]:X}+)"
    if not pre_offsets:
        return "ANCHOR not found"
    if len(pre_offsets) > 1:
        return f"ANCHOR FOUND {len(pre_offsets)} times — ambiguous, refusing to patch"

    bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not bak.exists():
        shutil.copy2(path, bak)

    # patch_bytes_offset within CD image:
    # anchor_at_cd + (PATCH_OFFSET_IN_0BIN - ANCHOR_OFFSET_IN_0BIN)
    patch_off = pre_offsets[0] + (PATCH_OFFSET_IN_0BIN - ANCHOR_OFFSET_IN_0BIN)
    data[patch_off:patch_off + len(PATCHED_BYTES)] = PATCHED_BYTES

    with open(path, "wb") as f:
        f.write(bytes(data))

    return f"patched at CD off 0x{patch_off:X} (backup: {bak.name})"


def _revert(path: Path) -> str:
    bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not bak.exists():
        return "no backup found, skipping"
    shutil.copy2(bak, path)
    return f"reverted from {bak.name}"


def _discover(roots: list[Path]) -> tuple[list[Path], list[Path]]:
    bins = []
    zbs = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            n = p.name.lower()
            if (("track 1" in n or "track01" in n) and n.endswith(".bin")
                    and p.stat().st_size > 10 * 1024 * 1024):
                bins.append(p)
            elif n == "0.bin" and p.stat().st_size == 504120:
                zbs.append(p)
    return bins, zbs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=None,
                    help="Root directory to scan for 0.BIN and Track 1.bin")
    ap.add_argument("--revert", action="store_true",
                    help="Revert any previously applied patches")
    args = ap.parse_args()

    if args.root:
        roots = [Path(args.root).resolve()]
    else:
        # Default: scan project root and DD-Saturn-bincue sibling
        here = Path(__file__).resolve().parent
        roots = [
            here.parent,
            here.parent.parent / "DD-Saturn-bincue",
            Path("D:/DragonsDreamDecomp"),
        ]

    print(f"=== sit_diag_gate_patch.py ({'REVERT' if args.revert else 'APPLY'}) ===")
    print(f"  scanning: {[str(r) for r in roots]}")

    bins, zbs = _discover(roots)
    print(f"  found {len(bins)} CD image(s), {len(zbs)} 0.BIN file(s)")
    print()

    op = _revert if args.revert else None

    for p in zbs:
        print(f"[0.BIN] {p}")
        try:
            if args.revert:
                print("  ->", _revert(p))
            else:
                print("  ->", _patch_0bin(p))
        except Exception as e:
            print("  ERR:", e)

    for p in bins:
        print(f"[CD]    {p}")
        try:
            if args.revert:
                print("  ->", _revert(p))
            else:
                print("  ->", _patch_cd_image(p))
        except Exception as e:
            print("  ERR:", e)

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
