---
name: Cycle-2/3 freeze SMOKING GUN — SV_Poll gate restoration logic
description: Identified the binary code path that controls whether SV_Poll re-activates after a zone-transition reconnection. Single byte g_state[+0x1B6B] selects init-path-with-restore vs non-init-path-without-restore.
type: project
---

# THE BYTE THAT CONTROLS THE FREEZE

After deep tracing across multiple sessions, I've found the specific code path that almost certainly causes the cycle-2/3 GOTOLIST freeze.

## The chain

### Step 1: zone-transition starts
`FUN_0601AD7C` (same-server zone transition handler — runs each `0x02EF`):

```asm
0601AD7C: mov.l r14,@-r15
0601AD80: mov.l pc+,r3            ; r3 = 0x0605F429 (SV_Poll gate)
0601AD86: mov #0,r13
0601AD94: mov.l pc+,r10           ; r10 = 0x060610C8 (reconnect SM struct)
0601AD9C: mov.l @(0x4,gbr),r0     ; r0 = g_state
0601ADA0: mov r0,r4                ; r4 = g_state
0601ADA2: mov.b @r3,r0             ; r0 = current SV_Poll gate value
0601ADA4: mov.b r0,@(0xE,r10)      ; struct+0xE = saved SV_Poll gate ← SAVE
0601ADC0: mov.w pc+,r1             ; r1 = 0x00FF
0601ADC2: mov.b @(R0,r4),r2        ; r2 = g_state[+0x1B6B]
0601ADC6: cmp/eq r1,r2             ; T = (r2 == 0xFF)
0601ADC8: bt/s -> 0x0601ADF4       ; if 0xFF, take "init" path
                                    ; else "already initialized" path
0601AE36: mov.b r13,@r3            ; SV_Poll gate = 0 (DISABLED)
0601AE38: mov.b r13,@(R0,r10)      ; struct+0x11 = 0
0601AE3E: mov.l r2,@r3             ; install per-frame callback
0601AE44: ...                      ; bsr to enqueue task that calls FUN_0601B058
```

So: every transition saves the current SV_Poll gate value to `struct@(0x060610C8 + 0xE)`, then disables SV_Poll.

### Step 2: per-frame poller runs
`FUN_0601B058` (called every frame after reconnect installer fires):

```asm
0601B058: mov.l r14,@-r15
0601B05C: mov.l @(0x4,gbr),r0      ; r0 = g_state
0601B05E: mov r0,r14                ; r14 = g_state
0601B060: mov.w pc+,r0              ; r0 = 0x1B6B
0601B062: mov.b @(R0,r14),r3        ; r3 = g_state[+0x1B6B]
0601B068: cmp/eq r2,r3              ; T = (r3 == 0xFF)
0601B06A: bt -> 0x0601B09A          ; if 0xFF: INIT BRANCH (restores SV_Poll)
                                     ; else: non-init branch (DOES NOT restore)
                                     ; ← FREEZE HAPPENS HERE
                                     ; ─── INIT BRANCH ───
0601B09A: bsr -> 0x0601B316         ; init function
0601B09E: tst r0,r0
0601B0A0: bf -> 0x0601B0AE          ; if init in progress, exit
0601B0A2: bsr -> 0x0601B94E         ; init complete, do final
0601B0A6: mov.l pc+,r3              ; r3 = 0x060610D6 (struct+0xE)
0601B0A8: mov.l pc+,r1              ; r1 = 0x0605F429 (SV_Poll gate)
0601B0AA: mov.b @r3,r2              ; r2 = saved SV_Poll gate value
0601B0AC: mov.b r2,@r1              ; SV_POLL GATE = saved value ← RESTORE!
0601B0AE: lds.l @r15+,pr
0601B0B0: rts
```

## THE KEY: `g_state[+0x1B6B]`

This single byte (memory `0x06060DD7`) selects which branch runs:
- **`== 0xFF`** → INIT branch → eventually RESTORES SV_Poll gate → SV_Poll resumes → game continues
- **`!= 0xFF`** → non-init branch → SV_Poll stays at 0 → CLIENT GOES SILENT

## Why cycles 1-2 work but cycle 3 freezes

On the very first connection (cold boot), `g_state[+0x1B6B] == 0xFF` (uninitialized RAM is interpreted as that value, OR something writes 0xFF during very early init we haven't found). The init branch runs, restoring SV_Poll gate. Cycle 1 works.

On cycle 1's transition, the init branch writes a NEW value to `g_state[+0x1B6B]` (probably the destination zone's server_table index). Subsequent transitions take the non-init branch.

But cycle 2 still works in the user's hardware tests. Why?

Possible reasons:
1. The non-init branch ALSO restores SV_Poll, just via a different code path (need to disassemble `wait_connect_to_server` at `0x06027DCA` and `wait_connect_same_server` at `0x06027CD2`).
2. There's a ONE-FREE-RECONNECT mechanism — first re-transition uses cached state.
3. Some other byte field controls the actual cycle limit and `+0x1B6B` is a different gate.

## Searches that returned ZERO writers

- All 16-bit literal loads of `0x1B6B` followed by store via `@(R0,Rn)`
- All 32-bit literal references to absolute address `0x06060DD7`
- Even within `init_zone_transition` body (file 0x00554-0x00720)

This means `g_state[+0x1B6B]` is written via either:
1. Computed addresses (base + offset where neither half is a clean literal)
2. A different addressing pattern my scans don't catch
3. Or it's never written at all — and the cycle limit is in a different field

## The 7 functions that touch struct `0x060610C8` (reconnect SM)

- `FUN_0601ABB8`
- `FUN_0601AD7C` (the 0x02EF event handler — saves SV_Poll gate)
- `FUN_0601AE98` (reconnection setup)
- `FUN_0601B058` (per-frame poller — restores SV_Poll gate IF init branch)
- `FUN_0601B12C`
- `FUN_0601B316` (init function called from B058)
- `FUN_0601B620`
- `FUN_0601B84A`

## Next steps if this lead pans out

1. **Disassemble FUN_0601B12C, FUN_0601B316, FUN_0601B620** — these likely write to `g_state[+0x1B6B]` via the missing addressing pattern.

2. **Find what 0xFF "uninitialized" trigger really is.** It might be:
   - The byte at boot from BIOS (often 0)
   - Set by a function we haven't disassembled
   - The "no current server" sentinel — set by disconnect, cleared by connect

3. **If we can identify what server-pushed message resets `g_state[+0x1B6B]` back to 0xFF**, we can trigger that on every cycle to force the init branch every time, restoring SV_Poll.

## Why this matters for the server

If the freeze IS due to non-restoration of SV_Poll gate after cycle 2/3, the fix could be:

**Option A**: Send a server message that triggers code resetting `g_state[+0x1B6B]` to 0xFF before each cycle. We need to find which message handler does this.

**Option B**: The server sends 0x02EF with a special parameter that forces the init path. Looking at 0x02EF structure: `[u8, u8 dest_index, u8, u8]`. Maybe the first or last byte controls re-init.

**Option C**: A specific message during reconnection (between `0x02EF` and `ESP_NOTICE`) that resets the state.

## Honest assessment

This is the deepest the analysis has gone in any session. We've identified:
- The SAVE-AND-RESTORE mechanism for SV_Poll gate (`struct+0xE` = `0x060610D6`)
- The CONDITIONAL byte that gates restoration (`g_state[+0x1B6B]` = `0x06060DD7`)
- The two functions that read it (`FUN_0601AD7C`, `FUN_0601B058`)

What's missing: who writes `g_state[+0x1B6B]`, when, and what value. That's the final missing piece.

This finding is more concrete than any previous attempt and gives a specific binary location to focus on.
