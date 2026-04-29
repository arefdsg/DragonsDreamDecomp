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

### Open question (needs user observation)

During the freeze: **is a dialog box / Yes-No prompt visible** on screen, or **only the bare
table list with cursor highlight**? Determines whether we're stuck in:
- State 2 dialog poll (dialog visible) — input_dispatch not returning 2 for C-press
- State 0 polling FUN_06030A7E (no dialog) — return value not matching 0x01XX mask

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
