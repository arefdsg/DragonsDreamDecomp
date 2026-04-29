---
name: Sit-freeze 2026-04-29 — SBL identified, gate byte pinpointed
description: Major breakthrough — DD uses SBL 2.11 (NOT custom). The freeze is a screen-transition gate byte at 0x06067D58, NOT a dialog widget or input deadlock as previously theorized.
type: project
---

# Sit-freeze: 2026-04-29 breakthrough session

## TL;DR

Prior sessions concluded incorrectly:
- ❌ "DD uses a custom Fujitsu/HRPG library" — WRONG. **DD uses SBL 2.11** (1996-03-21).
- ❌ "Static analysis is fully exhausted, need live debugging" — WRONG. We just hadn't traced the right poll loop.
- ❌ "The freeze is in the dialog widget polling input_dispatch" — WRONG. The dialog widget is never reached.

The actual freeze is in **`FUN_06036B6C` state 0**, polling **`FUN_06030CEC`**, which reads byte at **`0x06067D58`** (a state struct around base `0x06067D54`). When that byte is non-zero, the function returns `0xFFFE`, and state 0 stays. The dialog widget never gets set up.

Symptom: table list still visible during freeze (user-confirmed 2026-04-29). That confirms we're stuck before any UI transition begins.

## Verified facts from this session

### 1. DD uses SBL 2.11 (HARD EVIDENCE, not inference)

Direct binary string scan reveals these embedded SBL banner strings:

| File offset | String |
|---|---|
| 0x07A09C | `GFS_SBL Version 2.11 1996-03-21` |
| 0x07A0C4 | `STM_SBL Version 2.11 1996-03-21` |
| 0x07A0DC | `SYS Version 2.11 1996-02-26` |
| 0x07A164 | `RSD Version 0.60 1997-02-07` |

**Why prior FID matching returned ~0 hits**: CyberWarriorX has sigs for SBL **6.0/6.0.1** (Nov 1996+) and SGL 2.0a/2.1/3.00/3.02j. DD uses SBL **2.11** (Mar 1996) — a year-older minor version, not in any public sig set. FLIRT byte patterns don't match across versions.

**NOV96 DTS CD has full SBL 6.0 source** at `D:\Claude Saturn Skill Documentation\NOV96_DTS\LIBRARY\SBL6\SEGALIB\`. The headers (SEGA_PER.H, SEGA_SYS.H, etc.) describe APIs that are stable across 2.11 → 6.0 (minor versions), so the function names from the .A archives apply.

### 2. Compiler: Hitachi SHC (NOT GCC)

DD's game-code function prologues match SHC convention:
```
sit_request_sender (FUN_060232DC):
  2fe6 mov.l r14,@-r15
  2fd6 mov.l r13,@-r15
  2fc6 mov.l r12,@-r15
  2fb6 mov.l r11,@-r15
  2fa6 mov.l r10,@-r15
  6b43 mov  r4,r11
  4f22 sts.l pr,@-r15
```

Multiple callee-saved register pushes BEFORE PR — that's SHC. GCC tends to push only frame pointer + PR. **Use the `.LIB` archives (SHC) for any future FID generation, not `.A` (GCC).**

### 3. SBL function symbols extracted (1097 total, ready for FID matching)

From the GCC `.A` archive symbol tables in `NOV96_DTS\LIBRARY\SBL6\SEGALIB\LIB\`:

| Archive | Functions | Sample names |
|---|---|---|
| SEGA_PER.A | 9 | PER_LInit, PER_LGetPer, PER_IntFunc + 6 globals |
| SEGA_GFS.A | 220 | GFS_*, GFCD_*, GFCB_*, GFBF_*, GFCD_AllocBuf, etc. |
| SEGA_STM.A | 111 | STM_*, STL_*, STMERR_*, STMMNG_*, STMSVR_*, STMTRN_* |
| SEGA_SCL.A | 141 | SCL_AutoExec, SCL_DisplayFrame, SCL_*, ReqDisplayFlag |
| SEGA_PCM.A | 165 | PCM_Init, PCM_Change, PCM_Drv*, PCM_Gfs*, PCM_Me* |
| SEGA_SND.A | 35 | SND_Init, SND_StartSeq, SND_ChgPcm, SND_Set3D_Init |
| SEGA_INT.A | 260 | INT_GetScuFunc, INT_SetScuFunc + 256 interrupt handlers |
| SEGA_DMA.A | 23 | DMA_CpuStart, DMA_CpuMemCopy*, DMA_ScuStart, DMA_ScuMemCopy |
| SEGA_MTH.A | 36 | MTH_Sin, MTH_Cos, MTH_Sqrt, MTH_RotateMatrix*, fcos, fsin |
| SEGA_BPL.A | 24 | BPL_Init, BPL_SelectBranch, BPL_GetBranchInfo |
| SEGA_DBG.A | 16 | DBG_Printf, DBG_Initial, DBG_IntrCpuAddrErr |
| SEGA_SYS.A | 3 | SYS_CheckTrack, SYS_Exit, _sys_version |

### 4. The actual freeze gate (DEFINITIVE)

`FUN_06036B6C` state 0 (the sit driver):
```c
if (state == 0) {
    uVar6 = FUN_06030CEC();              // POLL
    if (uVar6 == 0xFFFFFFFF) → state 1;
    if ((uVar6 & 0x0F00) != 0x0100) return uVar6;   // STAY in state 0
    // else: do seat lookup, init task SM, → state 2
}
```

`FUN_06030CEC` decompiled (file 0x20CEC = mem 0x06030CEC):
```
sts.l pr,@-r15
mov.l @(...,pc),r2     ; r2 = 0x06067D58
mov.b @r2,r3           ; r3 = byte at 0x06067D58
tst r3,r3
bf 0x06030CFE          ; if byte != 0, return 0xFFFE
bsr 0x06030A7E         ; (do real work — animation/transition logic)
nop
bra 0x06030D00
mov r0,r4
mov #-2,r4             ; (the bf-target: returns -2)
lds.l @r15+,pr
rts
extu.w r4,r0           ; return r0 = r4 zero-extended u16
```

**When `*0x06067D58 != 0`, function returns `0xFFFE`. State 0 evaluates `0xFFFE & 0x0F00 = 0x0F00 ≠ 0x0100` → STAY in state 0. PERMANENT FREEZE.**

### 5. The gate byte at 0x06067D58 — what we know

- Direct 32-bit literal load only appears ONCE in the whole binary (in `FUN_06030CEC` itself).
- Therefore writes to it use **indirect addressing through a struct base** (`mov.b R0,@(disp,Rn)` patterns where Rn was loaded with the struct base).
- **Struct base candidate: `0x06067D54`** (likely; possibly earlier).
- Nearby addresses also referenced as literals: `0x06067D54, D56, D57, D5C, D60, D64, D68, D6C, D6E` — confirms a state struct.
- Functions managing this struct: `FUN_06030A7E` (the "do work" branch — animation/transition driver), `FUN_06030C66` (owns the literal pool entry for 0x06067D58).

### 6. What this rules out (don't re-investigate)

- ✗ Dialog widget input deadlock (FUN_0602EBDA polling input_dispatch). Real but **never reached** because state 0 never advances.
- ✗ Input-enable flag at 0x0605F428. `init_zone_transition` SETS it to 1 on every zone entry (verified by disassembling 0x0601064A: r12 = `mov #1,r12` at 0x0601055E, never modified before write). Tavern entry leaves input enabled.
- ✗ Button table swap. Table at 0x06054FCC is hardcoded and referenced only once. Never swaps. C → action 2, B → action 3 — exactly what the dialog widget would need.
- ✗ Server response content/format. Bisect already proved freeze is response-independent. Freeze happens entirely in state 0 polling, before any 0x020F could matter.
- ✗ ctx[0x1B85] state 259 poll. Confirmed 2026-04-22 — patching it doesn't help (because that's a different state machine entirely).

## Where this leaves us

The freeze is purely client-local. The fix path requires:

1. **Identify what writes `*0x06067D58 = 0`** (the transition-complete clearer). Search for `mov.b R0,@(disp,Rn)` patterns where Rn was loaded with `0x06067D54` and disp = 4. The clearer is the missing piece.
2. **Identify what triggers the clearer.** Is it gated on:
   - SCL_AutoExec animation completion?
   - A timer/semaphore?
   - A server-pushed message we're not sending or sending wrong?
3. If (3): there's a server-side fix.
4. If (1)/(2): possibly a hardware/SBL state issue that doesn't have a server fix.

## Continued investigation 2026-04-29 (later in session)

### Gate-byte writer FOUND — `FUN_06030D90`

```c
void FUN_06030D90(int r4) {
    byte *gate = 0x06067D58;
    u16  *flag = 0x06067BC6;
    if (r4 != 0) {           // SET gate
        *flag &= ~1;
        *gate = 1;
    } else {                  // CLEAR gate
        *flag |= 1;
        *gate = 0;
    }
}
```

Referenced as a 32-bit function pointer literal at **19 sites** across 0x060312D0–0x06039E24
(game logic) and 0x06052CDC (a vtable). Notably called from:
- **`FUN_06036B6C` state 0** (sit driver): `FUN_06030D90(1)` when transitioning state 0 → state 2.
  This is INTENTIONAL: lock the table-list UI while sit transition runs.

The gate is set to 1 deliberately. The bug is whatever should call `FUN_06030D90(0)` to release
it never fires — OR the freeze is downstream of state 2 (in the dialog poll) and we never
return to state 0 anyway.

### Task SM offsets — both DAT_EC5E and DAT_EA3A resolve to +0xA5

Critical: the byte that FUN_0602E986 sets to 1 (DAT_0602EA3A) is the SAME byte that
FUN_0602EBDA reads (DAT_0602EC5E) — both resolve to task_sm[+0xA5].

FUN_0602EBDA self-advances over 4 frames:
1. Frame 1: counter (+0xB0) = 0 < 2 → counter→1, return 0
2. Frame 2: counter == 1 → call FUN_0602E986 (sets [+0xA5]=1), counter→2, return 0
3. Frame 3: counter == 2, [+0xA5]==1 → set [+0x26]|=1, [+0x6a]|=1, [+0xA5]=2, return 0
4. Frame 4+: counter == 2, [+0xA5]==2 → poll input_dispatch() looking for action 2 (C) or 3 (B)

So state 2 of FUN_06036B6C IS reached and IS polling input. My earlier "freeze is in state 0"
analysis was wrong; the table list staying visible just means the dialog is a modal overlay
that doesn't fade the underlying UI.

### User observation: NO dialog visible during freeze

User confirmed (2026-04-29): only the bare table list, no dialog box overlay.

This is strange given our analysis says state 0 → state 2 transition SHOULD work:
- Action-2 path at 0x06030B08 stores `0x0100 + cursor_X` to *0x06067D6E
- Final return at 0x06030C52 reads u16 from 0x06067D6E
- Return value 0x0100-0x01XX satisfies state 0 advance check `(v & 0x0F00) == 0x0100`
- State 0 → state 2: inits task SM, sets gate to 1
- State 2 polls task SM via FUN_0602EBDA
- After 3-4 frames, FUN_0602E986 sets up dialog widget (writes button labels, glyphs,
  enables button widget bits at +0x26 and +0x6a)
- Subsequent frames poll input_dispatch

We KNOW state 0 advanced to state 2 because:
- 0x020E was sent (sit_request_sender called) — logs confirm `target=0, cmd=8`
- (sit_request_sender is called via vtable at 0x060527B0[0]; it would be called as part of
  the action-2 dispatch chain in production)

**Most likely remaining cause: VDP1/sprite resource issue with FUN_0602E986 dialog widget.**

FUN_0602E986 does heavy graphics setup:
- PTR_FUN_0602ea4c — likely VDP1 sprite/buffer allocation
- PTR_FUN_0602ea54 — ditto
- PTR_FUN_0602ea58 — more allocation
- FUN_0602e844 — text/label rendering (uses memset, accesses table at DAT_0602e93c+)
- PTR_FUN_0602eb0c, eb10, eb14, eb18 — VDP1 command setup
- PTR_FUN_0602eb1c — sprite placement loop (called in for-loop over button count)
- PTR_FUN_0602eb24 — finalize button widget
- PTR_FUN_0602ec60 — initialize sub-struct at +0x60
- PTR_FUN_0602ec68, ec70, ec74, ec78 — more setup

If any of these allocators fails (returns null or bad ptr), the dialog renders into nothing.
The state machine continues polling input as if visible, but player sees only the table list.

ALTERNATIVELY: the first C-press (which triggered sit_request_sender via the action-2 button
handler in 0x060527B0 vtable) consumed the just-pressed bit at 0x06060E78. Subsequent C
presses while held register no NEW press-edge. State 2's input_dispatch returns 0 (no new
press) every frame.

This last theory is testable: if the player RELEASES C completely and presses again ONCE
after the freeze starts, does it eventually take effect? (The user has tested with multiple
button presses and reports no response, so this seems ruled out — but worth confirming the
specific gesture.)

### What still needs investigation

1. Are the VDP1 sprite allocators in FUN_0602E986 succeeding? Static can show what they write,
   but not whether they fail in our specific run.
2. Is the dialog rendering off-screen (Z-priority below table list, palette wrong, etc.)?
3. Is the task SM struct getting corrupted by overlapping use with zone-transition?
   FUN_0602E920(0) only inits 3 fields (+0xA7, +0xB0, +0xB4). Many other fields keep stale
   values. The +0xA5 byte in particular might have a stale "post-confirm" value from the
   most recent zone transition.

### FUN_0602E986 callee resolution (2026-04-29)

All function pointers resolved — NONE are SBL functions. All are DD game code:

| Pointer | Target | Region |
|---|---|---|
| PTR_FUN_0602ea4c | 0x0603FF94 | timers.c neighborhood (+0x2FF94) — buffer init? |
| PTR_FUN_0602ea54 | 0x0604008C | timers.c neighborhood — format function (local_44=0x40F00000) |
| PTR_FUN_0602ea58 | 0x0603FF08 | timers.c neighborhood — result fetch |
| PTR_FUN_0602eb0c | 0x0601CA7C | dialog UI (in 0x0601C dialog handler region) |
| PTR_FUN_0602eb10 | 0x0601CAD6 | dialog UI |
| PTR_FUN_0602eb14 | 0x0601CB58 | dialog UI |
| PTR_FUN_0602eb18 | 0x0601CC42 | dialog UI |
| PTR_FUN_0602eb1c | 0x0601C2CE | sprite placement (in for-loop) |
| PTR_FUN_0602eb24 | 0x06025D02 | scmd-region finalize |
| PTR_FUN_0602ec60 | 0x06025D02 | scmd-region (same as eb24, sub-struct init) |
| PTR_FUN_0602ec78 | 0x06025E38 | scmd-region final |

The 0x0601CA7C-0x0601CC42 functions live in the same code region as the input-flag
write sites (per `_input_gate.txt` — 0x0601B7-0x0601C2 range). They're the dialog
rendering primitives. Nothing visibly SBL-dependent.

The dialog-render call chain looks deterministic — nothing should fail in our setup.
This pushes the freeze hypothesis toward:

a) **Z-priority / clipping**: dialog rendered but obscured by table list or off-screen.
b) **Stale state 2 reentrant**: state went to 2, but advanced and reset state to 0 before
   dialog rendered. State 0 then locked by gate byte = 1.
c) **Press-edge consumption**: first C-press triggered sit and consumed press-edge bit;
   state 2 input_dispatch sees no new press until release+repress.

Theory (b) is interesting: if state 2 enters and advances on the SAME C-press that
triggered sit (because press-edge bit at 0x06060E78 still has C set when state 2 enters),
FUN_0602EBDA would skip stages 0-2 (counter advance) but reach input_dispatch IMMEDIATELY
at frame 4. Wait — counter only goes 0→1→2 over 3 frames; input_dispatch isn't polled
until frame 4. By then press-edge is cleared.

So theory (b) doesn't explain it either.

Most likely remaining: theory (a) — dialog rendered but invisible due to Z-priority or
palette misconfiguration in tavern context specifically. To verify would need to
disassemble 0x0601CA7C and trace what VDP1 commands it issues and whether tavern's VDP1
state has the necessary configuration.

### 2026-04-29 (later) — 5 CLEAR-gate sites identified, all internal

Comprehensive scan of all 19 callers of FUN_06030D90 (gate writer) found:
- **10 SET sites** (r4=1, lock the gate)
- **5 CLEAR sites** (r4=0, release the gate) — listed below
- 4 other (passthrough or unrecognized)

The 5 CLEAR-gate call sites and their parent functions:

| Call site | Parent function | Gating condition |
|---|---|---|
| 0x06031290 | 0x06031204 | calls FUN_0602C0B8 first, then state-byte-driven |
| 0x06033910 | 0x060337EC | (within FUN_060337EC, deep in code) |
| 0x06033B4A | 0x060337EC | (same function, second clear path) |
| 0x06034768 | 0x060346A2 | paired set/clear pattern: SET then condition then maybe CLEAR |
| 0x06037EE4 | 0x06037B0C | gated on `FUN_0602DA04()` returning -1 or 2 |

**The most relevant for sit (0x06037B0C is called from tavern_state_machine at 0x06034E40)**:

```c
result = FUN_0602DA04();              // returns counter-stage result
if (result == -1) goto clear_gate;    // (taken if FUN_0602DAA8 returns -1 path)
if (result == 1) goto alt_path;        // different cleanup
if (result == 2) goto clear_gate;     // confirmation path
goto return;                            // gate stays
```

`FUN_0602DA04` is a 3-stage state machine using byte at `0x0606740C` (WRAM-H, internal):
- Stage 0,1: counter advances, returns 0
- Stage 2+: calls `FUN_0602DAA8(0x1874)` and returns its result

`FUN_0602DAA8(r4)` reads byte at offset `0xC7` from the passed base. For our call (r4=0x1874),
the effective read address is `0x193B`. **That's in BIOS ROM area** — strange, doesn't pattern
match a normal game state read. Either:
1. My addressing interpretation is wrong (mov.b @(R0,Rm),Rn semantics)
2. The byte at 0x193B IS read from BIOS (which would be a fixed value at runtime)
3. The 16-bit literal 0x1874 is not actually what's in r4 at the JSR (possible decoder bug)

### Final 2026-04-29 verdict: server-side path definitively closed

Searched all SCMD handler region (file 0x4000-0x7800) for ANY 32-bit literal in the gate
struct range 0x06067D40-0x06067D90: **0 hits.** Confirmed:
- No SCMD handler references the gate byte struct at 0x06067D54.
- No SCMD handler can write the input-enable flag at 0x0605F428 either (verified earlier).
- The only paths to clear the gate byte are FUN_06030D90(0) called from internal game logic.

The freeze is entirely in client-local state machine logic with NO protocol gate. The fix
options remaining, given user constraints (no emulator debug, no binary patches):

- **(A) Accept the gap**: ship server v4 without sit, document limitation.
- **(B) Binary patch FUN_06030CEC at 0x06030CF4** (the BF instruction): change to skip the
  gate-byte check unconditionally. Single-byte patch. Tested earlier sit-related patches
  didn't help (state-259 patch at 0x24E52), but THIS specific patch targets the actual
  identified gate. Untested.
- **(C) Re-examine user observation**: maybe there's a button-glyph indicator at screen
  bottom that user dismisses as "table list UI" but is actually the dialog widget. If
  dialog renders as small icon rather than popup box, it'd be on-screen but not
  dialog-shaped.

### 19 callers of FUN_06030D90 (gate writer)

Need to per-site disassemble each call site to find: which calls pass r4=1 (set), which
pass r4=0 (clear). The clearer call site reveals what must trigger to release the gate.

Sites to check (file offsets):
0x212D0, 0x21CB8, 0x239F0, 0x23C0C, 0x23D10, 0x24820, 0x24998, 0x24E00,
0x267C0, 0x26BEC, 0x26D00 (FUN_06036B6C state 0), 0x2728C, 0x27F70, 0x285A0,
0x28700, 0x29754, 0x29A5C, 0x29E24, 0x42CDC (vtable entry).

## Next session start

1. **First**: ask user about dialog visibility during freeze (state 2 vs state 0 question).
2. If state 2: trace why input_dispatch returns 0 instead of 2 — could be that button-state
   variables 0x06060E78 (just-pressed) aren't getting C bit due to some PER_LGetPer interaction.
3. If state 0: disassemble FUN_06030A7E action-2 path (0x06030B08) common code at 0x06030B2C
   to see what it returns — verify (& 0x0F00) == 0x0100 holds for action 2.
4. Either way: per-site analyze 19 callers of FUN_06030D90 to find the clear-gate trigger.

## Files / artifacts

- SBL source: `D:\Claude Saturn Skill Documentation\NOV96_DTS\LIBRARY\SBL6\SEGALIB\`
- SBL FID symbol lists: extracted via `parse_archive` Python script (in conversation history; can be re-run from `/d/Claude Saturn Skill Documentation/NOV96_DTS/LIBRARY/SBL6/SEGALIB/LIB/*.A`)
- Bulk decomp: `D:\DragonsDreamDecomp\GHIDRA Project\decompiled\bulk\` (1529 functions)
- Key decompile files used: `FUN_06036B6C.c`, `FUN_0602EBDA.c`, `FUN_0602E920.c`, `FUN_0602E974.c`, `FUN_0602E986.c`, `init_zone_transition.c`, `input_dispatch.c`, `main_loop.c`, `_input_gate.txt`, `_deep_freeze.txt`
