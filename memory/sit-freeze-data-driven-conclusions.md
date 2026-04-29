---
name: Sit-freeze data-driven conclusions (2026-04-22 follow-up)
description: Post-FID-match binary analysis: input gate, task SM gate, and the bisect data-point that needs re-verification before further protocol work
type: project
---

# Static-only conclusions on the tavern sit freeze

## Verified from binary (no live RAM)

1. **Input gate**: `FUN_0601F120` (input_dispatch) returns 0 unless `*0x0605F428 == 1`. Only two functions in the entire 504KB binary set it to 1: `FUN_0601C236` and `FUN_0603D75C`. Six functions clear it to 0 (at dialog-show sites). FUN_0601C236 is called from many BSR/BRA sites at 0x0601b... range — those are dialog-clear sites in `phase4_input_dispatch`.

2. **0x020F handler matches our payload format exactly**: reads `[u16 status][u16 unused]`; if status==0 strcpy; clears a single byte at `ctx+sRam060151f2`. We send `>HH 0 0` — correct. There is no "more data needed" case the handler is silently failing.

3. **Task SM gate (Path 2)**: `FUN_0602EBDA(0x060674A8)` returns 1 only when `task_sm[+DAT_0602EC5E] == 2` AND `FUN_0602ec84(1) == 2`. The byte at +DAT_0602EC5E is read here; no writer of that exact offset appears in the bulk decompile. It is set by user dialog confirmation (Yes/No dialog setup is `FUN_0602E986`, called when stage counter == 1).

4. **Sit driver call chain**: `sit_request_sender` (`FUN_060232DC`) is called via DATA reference from `0x060527B0` — a button-action table, not direct code. Our server log confirms client sends `target=0, cmd=8`.

5. **Tavern outer state machine**: `FUN_06037774` has sub-states 0-4. State 0 dispatches to `FUN_06036b6c`, which itself has states 0-3. State 4 of the outer machine routes through `FUN_06037EF6` whose sub-state 0 calls `seated_input_handler` (= goal state).

## Logical implication

If the bisect note is correct ("0x020F-only and no-response BOTH freeze identically"), the freeze must be entirely client-local — independent of any protocol gate — and no server-side fix is possible without binary patching.

**BUT** — the bisect's "no-response freezes identically" claim is the load-bearing premise that closes the door on a server fix. Per session memo, there IS a 2.5-min paired-wait timeout at `0x0601015A` that fires when `ctx+6 != 0`. With no response, ctx+6 stays nonzero and that timeout SHOULD fire. If it does, the no-response case is NOT a permanent freeze — it's a 2.5-min recoverable hang.

If that's true, the 0x020F response is causally responsible (it clears ctx+6, suppressing the recovery timeout) and there IS a server-side angle: don't reply to 0x020E, or reply with a response that doesn't clear ctx+6 (probably impossible since paired-wait clearing is in scmd_dispatch_inner, not 0x020F's handler).

## Action item before any next attempt

**Re-test "no-response" specifically**: send 0x020E response = none. Wait >5 minutes. If the client recovers (input returns, OR an error message appears, OR the menu redraws) at ~2.5 minutes, the prior session's "freezes identically" claim was misobservation, and the 0x020F response IS the cause. If the client truly stays dead past 5 minutes, the freeze is fully client-local and protocol fixes are off the table.

## Live debugging is achievable without ICE

Mednafen Saturn supports NetLink emulation that routes through a virtual serial port. tcpser or dreampi-style bridges can connect that to a local TCP server. NetLink games CAN be debugged in Mednafen — the prior session's "this is NetLink so how would it connect" was a wrong premise. Setup: Mednafen NetLink → tcpser → localhost:server-port. Mednafen has a built-in SH-2 debugger with breakpoints and RAM watch.
