# Sit freeze — 2026-04-22 session findings

## Status
**Still freezes** after exhausting the 4 investigation paths from `tavern-flow.md`
lines 235-259. FIX2 (`0x020F+0x0247+0x024D+0x01B6`, 0x020F first, all payload
formats corrected per 2026-04-10) is the live config and still hangs the client.

## What this session verified (don't re-try)

### State 259 / ctx[0x1B85] polling — **NOT the freeze point**
- Exhaustive 124,874-instruction Ghidra scan confirms `ctx[0x1B85]` is **never
  written by any code in the binary** (scanned: PC-relative literal loads
  followed by byte/word/long stores; literal `0x202CCB85` absolute-address
  search; GBR+8 + offset + ADD patterns). Six readers, zero writers.
- `init_seat_grid` writes `0x06068B6C` (a standalone global), **not**
  `ctx+0x1B85` — so `PTR_DAT_06036008 → 0x06068B6C` is a global seat-count,
  unrelated to state 259's gate.
- **Binary patch confirmed not to help.** Applied the 2-byte patch at file
  offset `0x24E52` (`tst r3,r3` → `clrt`, forcing BF to always take the advance
  branch to state 260). Tested on hardware (Satiator ODE, file-verified
  patched, power-cycled). Freeze is identical. State 259 is not the actual
  hang point.
- The patch script is in `patches/sit_patch.py` — **reverted** (not applied).
  Keep the script for future reference; do not apply without new evidence.

### The `0x0274` "recovery" observation was misinterpreted
- Prior note said `_DIAG_SEND_0274=True` "recovers after 2.5min with table
  full". Re-reading the dispatch table confirms `0x0274` is **NOT a valid
  msg_type** — it's silently dropped by the client dispatcher. The 2.5-min
  behavior is the *normal paired-wait timeout* for `0x020E` since no paired
  reply arrived.
- Why doesn't the same timeout fire with `0x020F`? The paired-wait-clear code
  in `scmd_dispatch_inner` (file `0x0134AC`: `mov.w r0,@(0x6,r11)` clears
  `ctx+6` on pair-table match) does fire — paired-wait table entry 24 is
  `[0x020E, 0x020F]`, verified. So `ctx+6 = 0` after `0x020F`. The main-loop
  timeout at `0x0601015A` requires `ctx+6 != 0`, so it never fires after the
  wait is legitimately cleared. Post-`0x020F` freeze is not a paired-wait
  issue.

### Bisect of 4-message sit atomic
Tested with full baseline `0x020F+0x0247+0x024D+0x01B6`, single `0x020F`,
and no response — **all freeze identically**. The freeze is triggered by
the client's *own local processing after sending 0x020E*, not by our server
response content.

### `flags=0` drift
The 2026-04-07 fix setting table `flags=0` in `h_sakaya_tbllist` had drifted
back to `flags = 1 if bot else 0`. **Reset to `flags = 0`** this session
(line ~524 of `handlers_social.py`). Do not revert.

## Path 1: main-loop post-wait check (0x0601015A)
```
if (*(byte *)0x06060F6C != 0 &&
    *(u32  *)0x06060E84 == 1 &&
    *(u16  *)(ctx + 6) != 0)
{
    call 0x06010A36;   // paired-wait timeout logic
}
```
Both flags are written by `FUN_06010554` = `init_zone_transition`. Confirmed
set during zone entry. After `0x020F` arrives and clears `ctx+6`, the third
condition fails → no timeout fires → explains the permanent (non-2.5min)
silence with `0x020F`.

## Path 2: task SM at 0x060674A8 (***IMPORTANT — further investigation needed***)
Prior note: "DIFFERENT from simple paired wait. Used for zone transitions/
warps, NOT tavern sit. If tavern sit somehow uses this path → investigate why."

**Confirmed this session:** the tavern sit driver `FUN_06036B6C` DOES access
the task SM struct at `0x060674A8`:
- `FUN_06036B6C` state 0 calls `FUN_0602E920(0)` (via `PTR_FUN_06036CF8`).
  `FUN_0602E920` is a thin wrapper that calls
  `FUN_0602E974(task_sm_struct_ptr, param_1=0, param_3=0)`. `FUN_0602E974`
  writes:
  - `struct[+0xB0] = 0` (byte, "ready flag"?)
  - `struct[+0xB4] = param_1` (u32, "data/param")
- `FUN_06036B6C` state 2 calls `FUN_0602E962(task_sm_struct_ptr)` — this is
  `FUN_0602EBDA`, a 2-frame timer + byte-check with 3 sub-paths based on
  `struct+DAT_0602EC5E` value.
- `FUN_06036B6C` state 2 also calls `FUN_0602E96E` → `FUN_0602EC88` which
  invokes `FUN_0602ED54(struct+0x1C)` twice (once for `+0x1C`, once for `+0x60`).

So the tavern sit flow IS driving the zone-transition task SM. That is either:
1. A shared/generic "pause UI for N frames then callback" mechanism legitimately
   used by both zone-transition and tavern-sit — in which case its behavior
   is likely fine and the freeze is elsewhere, or
2. A bug where tavern-sit is picking up stale state left in the task SM from
   a prior zone transition.

**Static analysis cannot distinguish these without live RAM inspection.**

## Path 3: sit_sender (file 0x0132DC)
Already decompiled — it's `FUN_060232DC` at memory `0x060232DC`. With
`target=0` (auto-assign), it writes `0` to `ctx+0x7515`, sends 0x020E. With
`target=table_id`, it looks up in `ctx+0x6DA8` (stride 0x30) and copies the
table name to `ctx+0x7515`. Confirmed our log shows `target=0, cmd=8`.

## Path 4: check_input (0x0601F120)
Called twice from `tavern_state_machine` epilogue (0x06034EFA and 0x06034F04)
to detect return values 5 or 6 (some exit/cleanup action). Button table at
`0x06054FCC` has actions 0x0001, 0x0002, 0x0003, 0x000D-0x0010 — **no 5 or
6**. So these checks never fire from this button table. Input path is not
gating sit progress from here.

## Remaining investigation (needs live tooling)
- Breakpoint on read/write of `ctx+6`, `ctx+4`, flag `0x06060F6C`, and task
  SM `0x060674A8+0xB0`/`+0xB4` on the client while frozen. Mednafen's
  debugger or a Saturn ICE would answer this in minutes.
- Confirm with live RAM: is the task SM in a state where `struct+DAT_0602EC5A
  < 2` and stuck there, or past it and waiting on `struct+DAT_0602EC5E`?

## Re-testing protocol (if someone tries again)
1. Satiator loads live from SD; on patch changes, power-cycle Saturn, don't
   just soft reset.
2. Observable freeze signature: client stops emitting `0x019A` input ticks
   (it was tick-ing every ~3-5s before sit) immediately after receiving
   `0x020F`. Keepalives keep flowing (network alive, UI main thread stuck).
3. Wait >3 minutes before concluding "permanent" freeze. No observed recovery
   between 3:00 and test end.

## Files touched this session
- `server/dragons_dream_server_v4/handlers_social.py`
  - Removed `_DIAG_SIT_REJECT`, `_DIAG_SEND_0274` dead-end flags.
  - Added `SIT_INCLUDE` bisect tuple (for future bisection tests).
  - Updated docstring with Ghidra evidence block.
  - Restored `flags = 0` in `h_sakaya_tbllist`.
  - Removed `0x01B6` push from `h_sakaya_tbllist` and `h_sakaya_in`
    (premise was disproved by full decomp).
- `patches/sit_patch.py` + `sit_patch.bat` + `README.md`
  - Tooling for the state-259 patch. Reverted on disk but script retained
    for documentation.
- `GHIDRA Project/*.java`
  - Many investigation scripts. Outputs under
    `GHIDRA Project/decompiled/_*.txt`.

## 2026-04-28 follow-up — FID matching + diagnostic patch attempt

### FID match (data-driven, conclusive)

Located CyberWarriorX's six Saturn `.sig` files (only public Saturn FIDs
that exist), patched NWMonster/ApplySig.py for headless, applied each:

| Sig file | Library version | DB count | Matches in 0.BIN |
|---|---|---|---|
| sbl60.sig | SBL 6.0 | 197 | 0 |
| sbl601.sig | SBL 6.0.1 | 198 | 0 |
| sgl20a.sig | SGL 2.0a | 311 | 0 |
| sgl21.sig | SGL 2.1 | 38 | 0 |
| sgl300.sig | SGL 3.00 | 349 | 1 |
| sgl302j.sig | SGL 3.02j | 346 | 1 |

**1539 candidate functions across all sigs, 1 unique match
(`_SYSUB_SetStackptr`).** Effectively zero coverage.

Reason: Dragon's Dream is NOT built on SBL/SGL. Source-string analysis of
the binary reveals it was compiled from `kn_main.c`, `kn_chat.c`,
`kn_cmd.c`, `lib_util.c`, `lib_sv.c`, `lib_scmd.c`, `timers.c`,
`queues.c` — a custom Fujitsu/HRPG network stack with `NRSV_*`,
`psv->pbSendPtr`, `nMsgSize`, `iv_timer_inited` identifiers. No public
FID exists for this code. Source-file partition by assertion-string
xrefs:

| File | Address range |
|---|---|
| `kn_main.c` | ~`0x06010000` |
| `kn_chat.c` | `0x0601218C` — `0x0601262A` |
| `lib_util.c` | `0x0601F6D0` |
| `lib_sv.c` | `0x060221F8` — `0x060226DA` |
| `lib_scmd.c` | `0x06024A32` — `0x06024D60` |
| `timers.c` | `0x06042EF4`+ |
| `queues.c` | `0x060457E4` — `0x0604618C` |

The sit-flow code (`tavern_state_machine`, `FUN_06036B6C`,
`FUN_06037774`, `FUN_0602EBDA`) sits in `0x0602D000-0x0603C000` — pure
game code with no public symbol coverage.

### Diagnostic RAM-dump patch attempt — failed, then reverted

Built `patches/diag_patch.py` that:
1. Repointed dispatch entry for `0x0249` (a 4-byte RTS;NOP stub in the
   stock binary) from `0x06016DD4` to `0x06087384` (a 76-byte zero region
   we identified as unreferenced).
2. Wrote 76 bytes of hand-assembled SH-2 at `0x06087384` to handle
   `0x0249 [addr:U32 BE][len:U16 BE]` by sending `0x024A` reply with the
   bytes from `addr`.

**Result: every `0x0249` we sent caused IMMEDIATE client silence** — even
when we replaced the 76-byte handler with a single `RTS;NOP` (effectively
identical to the stock stub). The dispatch redirect was honored
(verified — would have been a no-op if not), and the address held
`RTS;NOP`, but executing instructions from `0x06087384` killed the SH-2.

Most likely root cause: **SH-2 instruction-cache coherency** — the
4KB unified cache held stale data for that line from before binary load,
and our patch bytes never made it into the I-fetch path. The Saturn
requires explicit cache-line invalidation (write 0 to `addr +
0x40000000`) for code written to RAM that the cache may have already
seen, but neither the BIOS load nor any startup code does this for our
chosen address.

We didn't try other addresses inside the .text region because the
risk of overwriting real code is too high without live RAM tools.

**All patches reverted.** All `pre_diag_patch.bak` files cleaned up.
Server is back to stock-binary-only mode.

### Conclusions for the next session

- Static analysis is FULLY exhausted (1529-fn decomp, FID match, all
  prior-author paths walked, multiple bisects).
- Two server-side experiments that helped discover dead ends are now
  baked into the code: removed `_DIAG_SEND_0274`, removed unsolicited
  `0x01B6` pushes, set table `flags=0`.
- The freeze symptom matches a "menu drawn, input dead" state. Without
  live RAM tooling, we can't distinguish between
  "input-enable flag at `0x0605F428` is 0" vs "the whole main loop is
  parked in a state we can't see." Both are downstream of the
  paired-wait clearing.
- **Recommended next move: don't try server-side fixes anymore.** Either
  (a) get an emulator + native NetLink TCP redirect setup to live-debug,
  or (b) ship the server v4 without sit and accept the gap.
