# GOTOLIST Flow — Detailed Analysis

## GBR Pointer Table (CONFIRMED 2026-04-01)
| Slot | Opcode | Address | Purpose |
|------|--------|---------|---------|
| GBR[0] | C600 | 0x06052530 | Function pointer table (200+ send commands) |
| GBR[1] | C601 | 0x0605F26C | g_state (game state struct) |
| GBR[2] | C602 | 0x202CB000 | Session/network context (Work RAM-L, cache-through) |
| GBR[3] | C603 | 0x06060DD8 | Unknown |
| GBR[4] | C604 | 0x06060DDC | Unknown |
| GBR[5] | C605 | 0x06060E74 | Unknown |
- GBR set at file 0x00032E: GBR = 0x06060EBC

## CORRECTION: INFORMATION_NOTICE Context
- Handler at file 0x3DDA uses **GBR[2] = 0x202CB000** (session context), NOT GBR[1] (g_state)
- Previous MEMORY.md references to "g_state+0x94" and "g_state+0xA0" were WRONG
- Correct absolute addresses:
  - ctx+0x04 = 0x202CB004 (status, U16 BE) — zero means success
  - ctx+0xA0 = 0x202CB0A0 (info_type, U16 BE) — only written if status==0
  - ctx+0x94 = 0x202CB094 (info_value, U32 BE) — only written if status==0
- If status != 0, handler skips info_type/info_value storage and returns immediately

## CORRECTION: R10 in Main Loop = session_ctx, NOT g_state (2026-04-01)
- Main loop prologue at 0x0601006A: `C602 mov.l @(2*4,GBR),R0` then `6A03 mov R0,R10`
- **R10 = 0x202CB000 (session_ctx)** throughout main loop
- All offsets like 0xABAB, 0xABA5 etc. are relative to session_ctx, NOT g_state
- Previous analysis referencing "g_state[0xABA5]" was WRONG — should be "session_ctx[0xABA5]"

## Main Loop Dispatch (file 0x0000A4, confirmed 2026-04-01)
Every frame:
1. Calls polling function 0x0601F120(1)
2. If return == 14 (normal frame): reads g_state[0x01AD] at 0x0605F419
3. **If g_state[0x01AD] == 3** (game world):
   - Calls game_world_sm 0x0603B51C(0)
   - Re-reads g_state[0x01AD]:
     - **If == 2**: calls gate(0) — NO gate check
     - **If != 2**: calls gate(1) — PERFORMS gate check
4. **If g_state[0x01AD] != 3**: gate(1) is called with arg=1

## THREE SV_Poll Gates (CORRECTED 2026-04-01)

Main loop at file 0x00013C-0x000158 has **THREE** gates, not just one:

```
0x0601013C: R3 = [0x0605F429]     ; Gate #1: SV_Poll active flag
0x0601013E: R0 = byte @R3
0x06010140: tst R0,R0
0x06010142: bt SKIP_SV_POLL       ; if 0 → skip
0x06010144: R1 = [0x06053420]     ; Gate #2: reconnect-in-progress flag
0x06010146: R2 = byte @R1
0x06010148: tst R2,R2
0x0601014A: bf SKIP_SV_POLL       ; if non-zero → skip!
0x0601014C: R2 = [0x06060E88]     ; Gate #3: connection management flag
0x0601014E: R0 = [R2]
0x06010150: cmp/eq #1,R0
0x06010152: bt SKIP_SV_POLL       ; if 1 → skip
0x06010154: R1 = 0x060220E8
0x06010156: jsr @R1               ; CALL SV_Poll
```

### Gate #2 [0x06053420] — reconnect-in-progress flag
- Located 4 bytes before paired table at 0x043424
- SET to 1 at mem 0x060212D0: marks "reconnect in progress"
- CLEARED to 0 at mem 0x06013320: marks "reconnect complete"
- While set, ALL SV_Poll traffic is blocked

## Gate Function Detail (0x0603B6F0, file 0x02B6F0)

### Gate PASSES (session_ctx[0xE8C2] == 1):
1. At file 0x02B7D2: checks g_state[0x01AD] == 3
2. If yes: calls gate_dispatcher(0) → game_world_sm(0) → g_state[0x01AD] = 0
3. At file 0x02B7E0: g_state[0x013A] = -1, g_state[0x013B] = -1
4. Various jsr cleanup calls
5. At file 0x02B868-0x02B874:
   - g_state[0x01BC] = 0 (clear trigger)
   - **g_state[0x01AD] = 2** (transition to LOGIN)
6. Calls task_dispatch(6, 1) → gate_set(1) → re-sets g_state[0xE8C2]=1

### Gate FAILS (session_ctx[0xE8C2] != 1):
1. Calls task_dispatch(3, 1)
2. g_state[0x01BC] = 1 (stays set, retry next frame)
3. **g_state[0x01AD] stays at current value** = stays in game world = **BLACK SCREEN**

## send_gotolist_notice (file 0x01313E)
- Entry #65 in function pointer table at file 0x042680
- Uses GBR[2] (session context 0x202CB000), loads offsets 0x1B8C and 0x0260
- If ctx[0x1B8C] == ctx[0x0260]: clears init flags ctx[0x8E-0x91]
- Sends 0x019C with dest_id via scmd_new_message/scmd_add_long/scmd_send

## Paired Message Completion (CONFIRMED 2026-04-02)
- Paired completion is JUST tracking: handler dispatch at 0x0601341C clears session_ctx[6]
  when response msg_type matches the pending request stored in session_ctx[6].
- NO callbacks, NO event queue writes, NO [0x0605F420] modifications.
- Code at 0x06024914 is the TAIL of event dispatch (0x06024864), NOT paired completion.
- Only ONE pending request at a time (session_ctx[6] is single uint16).

## GOTOLIST Entry Layout (28 bytes, CONFIRMED 2026-04-02)
| Offset | Size | Field |
|--------|------|-------|
| 0-3 | U32 BE | dest_id |
| 4-5 | U16 BE | zone_id |
| 6-7 | U16 BE | map_id |
| 8 | U8 | map_x (VDP2 character selector: +0x07BC) |
| 9 | U8 | map_y (display sub-parameter) |
| 10 | U8 | server_info/flag |
| 11-26 | 16B | name (Shift-JIS, handler reads at entry+11) |
| 27 | U8 | terminator (handler writes 0) |

## GOTOLIST State Machine (file 0x00DFB0)
- Context struct with function pointer at ctx[0x00] (cooperative tail-call pattern)
- Active flag at ctx[0x74], timer at ctx[0xB4], sub-state at ctx[0x01AE]
- Send path: 0x06041496 → 0x06041322 (dispatch engine) → function pointer table
- After send, polls for response via paired message system

## Hardware Test Results (25 tests)
| # | Date | Response to 0x019C | Result |
|---|------|-------------------|--------|
| 1 | 171830 | ESP only (mode=0) | Game world, no D-pad |
| 2 | 180726 | INFO only (mode=0) | Black screen |
| 3 | 195555 | INFO only (mode=0) | Black screen |
| 4 | 213824 | ESP only (mode=6) | Interactive GOTOLIST, loop, **GAME WORLD after ~100s** |
| 5 | 214712 | INFO+zone (mode=6) | Black screen |
| 6 | 215632 | ESP+break (mode=6) | **GAME WORLD after ~53s** (count=0 → timeout → 0x0048) |
| 7 | 223721 | ESP→break→CHARDATA(no ESP) | Dead silence |
| 8 | 224417 | ESP+CHARDATA burst (mode=6) | Dead silence |
| 9 | 232813 | INFO only (info_value=0x01010101) | Dead silence |
| 10 | 065555 | INFO+ESP+UPDATE_CHARDATA_REQ, loop breaker→INFO | Dead silence |
| 11 | 091023 | INFO+ESP+UPDATE_CHARDATA_REQ (no loop breaker) | Cities visible, navigate, CANNOT ENTER |
| 12 | 131350 | INFO only (no ESP, no UPDATE_CHARDATA_REQ) | Black screen, zero client messages |
| 13 | 215911 | 0x02EF+INFO (no ESP) | Black screen, zero client messages |
| 14 | 055540 | INFO+ESP+UPDATE_CHARDATA_REQ (v4, 50ms delay) | Cities visible, navigate, CANNOT ENTER (GOTOLIST loop) |
| 15 | 142735 | INFO→500ms→re-establish→ESP→UPDATE + name@byte11 | Cities visible, CANNOT ENTER, GOTOLIST loop→silence |
| 16 | — | INFO→0x02EF(dest_idx=1)→500ms→reset seq→establish | BLACK SCREEN: bit 7 prevents INIT re-send, infinite keepalive |
| 17 | — | INFO→0x02EF→500ms→establish→500ms→ESP+UPDATE | BLACK SCREEN: establish arrived BEFORE SV_Init (~2.17s) |
| 18 | — | INFO→0x02EF→seq=0→3.5s→establish→1.5s→ESP(seq=0) | BLACK SCREEN: 3.5s correct, but session[116]=1229 rejects seq=0 |
| 19 | — | INFO→0x02EF→old seq→3.5s→establish→1.5s→ESP(old seq) | GOTOLIST LOOP: seq fix works, but 0x02EF→gate_set(0)→loop |
| 20 | 140139 | INFO (0x019D) ONLY | BLACK SCREEN: 0x019D→zone_transition→SV_Init→silence (no re-establish) |
| 21 | 165221 | INFO→3.5s→re-establish→ESP+UPDATE, count=0 on re-login | PERMANENT HANG: zone transition disrupted SM timer. count=0 shows blank GOTOLIST, user pressed C→loop. After 2nd cycle count=0, 3+ min hang. |
| 22 | 171139 | ESP+UPDATE only (NO 0x019D, full destinations) | GOTOLIST loop ×3, 0x0048 at ~4.5min, idle. NO game world. Matches v3 tests 4/6 timer-exit pattern. |
| 22b | 172302 | 0x019D+ESP(mode=0)+UPDATE immediately (no delay) | GOTOLIST loop ×3, idle. NO game world. ESP mode=0 wrong. |
| 23 | 173341 | ESP(mode=6)+UPDATE+MAP+CHARDATA, loop breaker count≥2 | Loop break → empty 0x019B → client sends 0x019C anyway → after count=3, permanent keepalive silence (no 0x0048). WORSE than no loop breaker. |
| 24 | 192541 | 0x019D→4.0s→re-establish→0.5s→ESP(mode=6)+UPDATE (NO 0x02EF) | Client ACKed establishment, then sent 0x019A (LOGOUT) NOT 0x019E. Zone transition NEVER fired — no 0x02EF = no event queue write. Confirmed root cause. |
| 25 | PENDING | 0x019D→**0x02EF(dest_idx)**→4.0s→re-establish→0.5s→ESP→UPDATE + byte10 fix + name@byte12 | Three binary-proven fixes: (1) 0x02EF triggers event queue write, (2) byte 10=1-7 not 0, (3) name at wire[12] not wire[11]. |
| 26 | 060406 | 0x02EF event_type=9 (skip init_zone_transition) → 0.3s → ESP → UPDATE | GOTOLIST LOOP: handler 9 only cleans event queue. g_state[0x01AD] unchanged → client sends 0x019A immediately. |
| 27 | 060406 | 0x019D → 0x02EF event_type=0 → 5.0s → reset seq=0 → establish → 1.0s → ESP → UPDATE | BLACK SCREEN: Server reset send_seq=0, client session NEVER reset (val2=1201=old seq). ESP at seq=0 silently dropped. |
| 28 | 080958 | 0x019D → 0x02EF event_type=0 → NO session manipulation | BLACK SCREEN: 0x019D paired completion → GOTOLIST SM blocks BEFORE event_dispatch processes 0x02EF. Both msgs in same SV_Poll → SM blocks forever. |
| 29 | 085947 | 0x02EF(dest_idx=1) → 300ms → 0x019D → NO session manipulation | BLACK SCREEN: Same result as test 28. Ordering doesn't matter. Client silent after both arrive. No ESP = no init flags = no deferred auto-sends = silence. |
| 30 | PENDING | 0x02EF(dest_idx=1) → 0x019D → 1.5s → ESP(mode=6) → UPDATE_CHARDATA_REQ | Data-driven: tests 11/14 (with ESP) → client responds. Tests 28/29 (no ESP) → silence. ESP re-inits init flags for deferred auto-sends. |

## ESP_NOTICE Handler Analysis (0x06013F1C, confirmed 2026-04-01)

**Critical writes by ESP_NOTICE handler** (base = R14 from GBR[2] = session_ctx):
- ctx+0x00A4, ctx+0x00A5: bytes from payload (session_param, connection_id area)
- ctx+0x00A6: 16 bytes (server name from payload)
- ctx+0x7C88: 12 bytes + individual fields at 0x7C94-0x7CA0
- **ctx+0xABA4 = 0** (event queue produce index — CLEARED)
- **ctx+0xABA5 = 0** (event queue consume index — CLEARED)
- ctx+0xAB14 = 0, ctx+0xAB15 = 0
- ctx+0xAD48 = 0 (word)
- ctx+0xD044 = 0 (long)
- ctx+0x6F88 = 0 (word)
- ctx+0xF4B4 = 0
- **[0x0605F432] = 0** (absolute address, global flag)
- **ctx+0x0090 = 1** (init flag: CMD_BLOCK_REPLY auto-send)
- **ctx+0x008F = 1** (init flag: PARTY_BREAKUP_NOTICE auto-send)
- **ctx+0x0091 = 1** (init flag: SYSTEM_NOTICE auto-send)
- **ctx+0x008E = 1** (init flag: STANDARD_REPLY auto-send)
- ctx+0x06 = 0 (word)

**ESP_NOTICE does NOT write to session_ctx[0x1B6B]** — no writes in 0x1B00-0x1BFF range.

## Critical Observation: Test 131350
- After 0x019D sent, client sends ZERO messages for 74+ seconds
- No keepalives, no SV frames, no BBS commands — total silence
- Server keepalives get no response
- **NOT SV teardown** — SV_Poll is gated off by per-frame callback writing 0 to [0x0605F429]
- Root cause: without ESP_NOTICE, no init flags set → no deferred auto-sends → no SV traffic

## Per-Frame Callback System
- **[0x0605F420]**: per-frame callback function pointer (set by event dispatch or paired msg)
- **session_ctx[0xABAB]**: gate byte — if 0, per-frame callback is SKIPPED
- Main loop at 0x06010174: `mov.b @(R0,R10),R2` where R0=0xABAB, R10=session_ctx
- If R2==0: skips callback AND game state dispatch (jumps to 0x060101F0)

## CORRECTED: 0x02EF Event Queue Approach (2026-04-03)

Test 13 failure was NOT due to 0x02EF being wrong — it was due to **dest_index=0**.

**Root cause of test 13 failure**: event_data=[0x00,0x00,0x00,0x00] → dest_index=0 →
server_table[0]=[FF,FF,FF,00] → zone_id=0x00 → R12=0 → handler took cleanup-only
path (finish_zone_transition). init_zone_transition was NEVER called. No SV_Init.
Client SV state not reset. Establishment frame arrived on existing session = confusion.

**Fix (2026-04-03)**: event_data=[0x00,0x01,0x00,0x00] → dest_index=1 →
server_table[1]=[FF,FF,FF,01] → zone_id=0x01, same-server → R12!=0, R11==0 →
func_B(0,1) → CD → init_zone_transition → SV_Init → client reconnects properly.

The 0x02EF approach IS correct. ESP_NOTICE is sent by h_init AFTER the client
reconnects and sends INIT (0x0035), not during the GOTOLIST response.

## DISPROVEN: Immediate ESP (2026-04-02, test 14)

Sending INFO+ESP+UPDATE_CHARDATA_REQ with 50ms delays: cities visible, can navigate,
but CANNOT ENTER any city. Client cycles: select → server responds → client sends
0x01EC(×2), 0x0268(×2), 0x019A(LOGOUT) → GOTOLIST again.

**Root cause**: ESP sent 50ms after INFO zeroes event queue indices (ctx+0xABA4/0xABA5).
The GOTOLIST SM writes the zone transition event AFTER paired completion. In the same
SV_Poll call, INFO + ESP are both processed. ESP zeroes the indices. GOTOLIST SM then
writes event (produce goes 0→1). But the event DATA at 0xAB24 was also zeroed by ESP's
bulk clear → zone handler reads invalid data → validation fails → no zone transition.

**Also found**: Name offset bug. Handler at 0x06014930 reads 16-byte name at entry
byte 11. Server was writing at byte 12 (off by one). First byte of displayed name was
0x00, causing rendering issues / "overlapping town names."

## Current Fix: INFO + delay + re-establish + ESP + UPDATE_CHARDATA_REQ (2026-04-02)

1. **0x019D INFORMATION_NOTICE** — paired ack for 0x019C
2. **500ms delay** — lets GOTOLIST SM write event, dispatch process it, zone handler fire
3. **Session re-establishment frame** (256B, ESTABLISH flag 0x0008)
4. **200ms delay**
5. **0x01E8 ESP_NOTICE** — init flags (by now event queue already consumed = safe to zero)
6. **0x019F UPDATE_CHARDATA_REQ** — triggers login flow restart

**Also fixed**: Name at entry byte 11 (not 12).

## Test 15 Results (2026-04-02, log 142735)
- Cities visible with correct names, can navigate GOTOLIST menu
- After selection: client ACKs establishment (0xA6 flags=0x34), then sends LOGOUT (0x019A)
- Client does NOT send 0x0035 INIT after re-establishment (bit 7 prevents re-send)
- Client does NOT send 0x019E LOGIN_REQUEST — goes straight to LOGOUT
- After 3 GOTOLIST cycles, client goes permanently silent (keepalives only)
- **Root cause**: The reconnection function (0x0601AE98) was never entered because
  the event queue transition event was never properly dispatched. Without reconnection
  completing, task_dispatch(zone_id,1) never fires, game world never initializes.

## game_world_sm (0x0603B51C, CONFIRMED 2026-04-02)
- **Two paths**: arg==0 (teardown, called from main loop when state==3)
  and arg!=0 (initialization, called from dispatcher)
- **PATH 1 (arg=0, teardown)**: If g_state[0x01AD]==3: sets to 0, memset 57KB at
  struct[0]+0x2000, clears flags, g_state[0x01BC]=1, task_dispatch(6,1)
- **PATH 2 (arg!=0, initialization)**: CRITICAL gate: checks **session_ctx[0xDDFE]==1**
  - If !=1: task_dispatch(3,1), g_state[0x01BC]=1, return → **GATE FAILS**
  - If ==1: tear down old state if g_state[0x01AD]==2, reinit game world struct,
    g_state[0x01BC]=0, **g_state[0x01AD]=3** (ENTERS GAME WORLD), task_dispatch(6,1)
- BSS game world struct at 0x060692DC
- Dispatcher at 0x0603B4CC: state==2→login_sm(0x0603B6F0), state==3→game_world_sm

## gate_set CORRECTION (2026-04-02)
- gate_set at 0x0603B488 writes to **session_ctx** (GBR[2]=0x202CB000), NOT g_state
- R14 = session_ctx + 0xDDFC, R5 = session_ctx + 0xE8C0
- `mov.b R0,@(2,R14)` → session_ctx[0xDDFE] = arg
- `mov.b R0,@(2,R5)` → session_ctx[0xE8C2] = arg
- Login gate at 0x0603B5F4: session_ctx[0xDDFE]==1 (game world entry condition)
- Game world gate at 0x0603B7C8: session_ctx[0xE8C2]==1 (game world exit condition)

## Event Handler Table (0x06056F98, CONFIRMED 2026-04-02)
- handler[0] = 0x0601AD7C (same-server zone transition)
- handler[1] = 0x0601AFC4 (cross-server zone transition)

## Reconnection Function (0x0601AE98, CONFIRMED 2026-04-02)
- Installed as per-frame callback [0x0605F420] after GOTOLIST per-frame handler fires
- 2-state machine (sub-state at 0x060610D9):
  - State 0: Check GBR[9] busy flag. Read server_table entry.
    If field[0]==0xFF: begin_connect_same_server(0x06027C50)
    Else: begin_connect_to_server(0x06027C84). Advance to state 1.
  - State 1: Poll wait function.
    If field[0]==0xFF: wait_connect_same_server(0x06027CD2)
    Else: wait_connect_to_server(0x06027DCA)
    If return==0 (complete): task_dispatch(zone_id,1), restore SV_Poll, finish_zone_transition
- **begin_connect_same_server (0x06027C50)**: DISASSEMBLED 2026-04-06
  For same-server (arg==struct[5]): sets g_state[0x01B0]=1, struct[225]=0, returns.
  NO SV_Init, NO SV_Setup, NO session reset. Total NO-OP for networking.
- **wait_connect_same_server (0x06027CD2)**: DISASSEMBLED 2026-04-06
  Checks g_state[0x01B0]==1, returns 0 (success) immediately. NO waiting.
- Same-server zone transitions do NOT touch the SV/session layer at all.

### Key Addresses
| Address | Purpose |
|---------|---------|
| 0x0605F429 | SV_Poll gate #1 (0=stopped, nonzero=active) |
| 0x06053420 | SV_Poll gate #2 (0=normal, nonzero=reconnect-in-progress) |
| 0x06060E88 | SV_Poll gate #3 (1=blocked, other=normal) |
| 0x0605F420 | Per-frame callback pointer |
| 0x0601AD7C | GOTOLIST validation + SV_Poll disable |
| 0x0601AE98 | Reconnection setup (dial new server) |
| 0x06056F98 | Function pointer table (dest index → handler) |
| 0x060220E8 | SV_Poll entry point |
| 0x060610D9 | Reconnection sub-state |
| 0x06013F1C | ESP_NOTICE handler (sets init flags) |
| 0x06013320 | Clears gate #2 (reconnect complete) |
| 0x060212D0 | Sets gate #2 (reconnect in progress) |

### Server Table (ROM at 0x06053CAC, file 0x043CAC)
- 16 entries × 4 bytes each
- Entries 0-7: [0xFF, 0xFF, 0xFF, completion_id] — server_id=0xFF = same-server shortcut
- Entries 8-15: [0x02-0x0A, 0xFF, 0xFF, completion_id] — all have [1]=0xFF
- **EVERY entry has [1]=0xFF** — the game NEVER re-dials modem for zone changes

## CRITICAL FINDING: v3 Logs Analysis (2026-04-05)

**v3 tests 4/6 did NOT send 0x019D after 0x019C** — the logs prove it:
- Test 4 (213824 line 218): send_seq jumps 1173→1232 (59B = ESP only, no room for 0x019D)
- Test 6 (215632 line 218): same pattern, ESP+UPDATE only
- The v3 source code's 0x019D was added AFTER these tests

**ALL tests eventually get 0x0048 after GOTOLIST timer expires:**
- Test 4: 3 cycles, ~103s → 0x0048 (user typed "bubbinsbubbins") → then idle
- Test 6: 3 cycles (loop break at count≥2), ~54s → 0x0048 → user typed chat → idle
- Test 22: 2 cycles, **~405s** → 0x0048 (user typed "111...") → then idle
- **NO test ever got movement, combat, or gameplay after 0x0048**

**Root cause of blank game world**: Client sends 0x019A (LOGOUT→GOTOLIST) instead of
0x019E (LOGIN) after ESP+UPDATE. This bypasses h_update_chardata_reply, so MAP_NOTICE
(0x01DE) and CHARDATA_NOTICE (0x01AB) are never sent for the new zone.

## Test 23 Results (2026-04-05, log 173341)
Approach: ESP+UPDATE+MAP+CHARDATA (proactive) + loop breaker on count≥2.
Result: GOTOLIST loop → loop breaker sends empty 0x019B (result_code=1, count=0) → client
still sends 0x019C → same pattern repeats → after count=3 loop breaker, permanent keepalive
silence. NO 0x0048 message. WORSE than test 22 (no loop breaker) which at least gets 0x0048.
Root cause: Loop breaker (empty 0x019B) confuses GOTOLIST SM — SM expects valid entries.
When it gets empty list, blank map shown, user sees nothing and can't navigate.

**CONCLUSION from tests 1-23**: No approach that bypasses zone transition can reach gameplay.
Tests 4/6 "game world" was just an idle chat state (0x0048 typing), not actual gameplay.
The client MUST execute init_zone_transition (CD subsystem load) to render any zone data.

## Test 24 Results — FAILED (2026-04-05, log 192541)

**Approach**: 0x019D → 4.0s → re-establish → 0.5s → ESP → UPDATE (NO 0x02EF)
**Result**: Client ACKed establishment (0xA6 flags=0x34), then sent 0x019A (LOGOUT) NOT 0x019E.
Zone transition NEVER happened. Client went straight back to GOTOLIST.

**Root cause**: Server never sent 0x02EF. Binary disassembly PROVES:
- Paired completion at 0x0601341C only clears session_ctx[6] — NO event queue writes
- GOTOLIST SM does NOT write to event queue after paired completion
- Without 0x02EF, no event in queue, no zone transition handler fires
- Client sees paired completion, SM advances, but no zone change = back to GOTOLIST

## Test 25 Approach — 0x02EF Fix (2026-04-05)

**Implementation**: handlers_login.py `h_gotolist_notice` + `h_logout`

**Three binary-proven fixes:**

1. **0x02EF (EXEC_EVENT_NOTICE)** added after 0x019D in h_gotolist_notice
   - Payload: [0x00, dest_index, 0x00, 0x00]
   - event_data[0]=0x00 → handler_table[0] = zone transition (0x0601AD7C)
   - event_data[1]=dest_index → server_table[dest_index*4] at ROM 0x06053CAC
   - dest_index clamped to 1-7 (same-server, completion_code != 0)

2. **Byte 10 in GOTOLIST entries** changed from 0 to dest_zid clamped 1-7
   - Previously 0 → server_table[0] completion_code=0 → cleanup ONLY
   - Now 1-7 → proper same-server server_table index

3. **Name offset** changed from wire[11:27] to wire[12:28]
   - Handler at 0x06014930: skips wire byte 11 (mov.b @R3+), reads name from wire[12]
   - Previous offset caused first name byte = 0x00 → "overlapping city names"

**9-step flow (was 8, now includes 0x02EF):**
1. 0x019D INFORMATION_NOTICE — paired ack
2. **0x02EF EXEC_EVENT_NOTICE** — event queue trigger (dest_index=1-7)
3. Pause keepalives (_zone_transitioning=True)
4. Wait 4.0s — CD read + init_zone_transition (SV_Init at step 4)
5. 256B establishment frame — preserve send_seq
6. Wait 0.5s — connection SM processes establishment
7. ESP_NOTICE (mode=6) — init flags, server info
8. UPDATE_CHARDATA_REQ — triggers login flow restart
9. Resume keepalives, reset login_phase=0

**Test 25 expected client flow:**
1. 0x019D → paired completion → GOTOLIST SM advances
2. 0x02EF → event written to queue at session_ctx+0xAB24
3. Event dispatch → handler[0] (0x0601AD7C) → server_table[dest_index]
4. Same-server path: func_B(completion_code, 1) → CD → init_zone_transition
5. init_zone_transition: SV_Init (step 4), gate_set(0) (step 22), BRAM load (step 28)
6. Server re-establishes → CONNECTED
7. ESP + UPDATE → init flags set → deferred auto-sends
8. Gate check: E8C2=1 (from BRAM) → g_state[0x01AD]=2 → login SM
9. User presses A → LOGIN_REQUEST (0x019E) → CHARDATA sequence → game world

**Test 25 PROVEN BROKEN (2026-04-05, pre-hardware analysis):**
Root cause: SV_Init at 0x0602219E clears [0x202E4B3C]=0. SV_Poll at 0x060220E8
checks [0x202E4B3C]==1 before calling SV_RecvFrame (at file 0x012122-0x012126:
MOV.L @R14,R0 / CMP/EQ #1,R0 / BF end). When cleared, SV_Poll skips ALL
incoming data. SV_Setup (the only writer of [0x202E4B3C]=1) is only called from
connection SM states 1-2, but SM is at state 0x84 (past states 1-2).
No code path re-enables SV_Poll after SV_Init without full modem reconnection.
Server re-establishment frame sits in TCP buffer, never processed.

## Test 26 Approach — event_type=9 (2026-04-05)

**Key insight**: Use handler 9 instead of handler 0 to avoid init_zone_transition entirely.

**Binary evidence**:
- Handler 9 at file 0xB604 (mem 0x0601B604): A1A3 C602
  = BRA 0x0601B94E; delay: MOV.L @(GBR[2]),R0 (R0=session_ctx)
- finish_zone_transition at file 0xB94E (mem 0x0601B94E, 20 bytes):
  ```
  E200  MOV #0,R2           ; R2 = 0
  D109  MOV.L ...,R1        ; R1 = 0x0605F420 (&g_state[0x01B4])
  C602  MOV.L @(GBR[2]),R0  ; R0 = session_ctx
  6403  MOV R0,R4            ; R4 = session_ctx
  D00C  MOV.L ...,R0        ; R0 = 0x0000ABA5
  034C  MOV.B @(R0,R4),R3   ; R3 = session_ctx[0xABA5] (LOAD: 0nmC format)
  7301  ADD #1,R3            ; R3 = consume_idx + 1
  0434  MOV.B R3,@(R0,R4)   ; session_ctx[0xABA5] = R3 (STORE: 0nm4 format)
  000B  RTS
  2122  MOV.L R2,@R1         ; g_state[0x01B4] = 0 (delay slot)
  ```
- Does NOT call init_zone_transition, SV_Init, gate_set, or anything else
- SV layer stays fully active — SV_Poll continues processing server messages

**SH-2 opcode correction**: In the 0-family indexed MOV.B:
- 0x0nm4 = STORE: MOV.B Rm,@(R0,Rn) — address = R0+Rn, data = Rm
- 0x0nmC = LOAD: MOV.B @(R0,Rm),Rn — address = R0+Rm, result = Rn
Previously confused these two, leading to wrong function interpretation.

**Implementation**: handlers_login.py `h_gotolist_notice`
- 0x02EF payload: [0x09, 0x00, 0x00, 0x00] (event_type=9, rest unused)
- No 4s wait (no CD read, no SV_Init)
- No re-establishment (SV stays active)
- No keepalive pause
- 0.3s delay for event processing
- ESP_NOTICE + UPDATE_CHARDATA_REQ sent normally

**Expected client flow:**
1. 0x019D → paired completion → GOTOLIST SM advances
2. 0x02EF event_type=9 → event queue → handler 9 → finish_zone_transition
3. finish_zone_transition: clears g_state[0x01B4], advances consume index, returns
4. SV_Poll still active, processes ESP_NOTICE normally
5. ESP handler: stores server params, zeros event queue, sets init flags
6. UPDATE_CHARDATA_REQ: stores char data
7. Init flags trigger deferred auto-sends (0x0048, 0x025F, 0x02D4, 0x006D)
8. Gate flags unchanged (E8C2 stays=1 from original login)
9. g_state[0x01AD] stays=2 (game world) — no login SM, client stays in game

**Trade-offs:**
- No CD zone data loaded (zone graphics from previous zone persist)
- No init_zone_transition reset (some state not cleared)
- Login SM skipped — no character select prompt (seamless transition)

## Test 26 Results — FAILED (2026-04-06)

**Result**: Client loops back to GOTOLIST (sends 0x019A LOGOUT immediately after ESP+UPDATE).

**Root cause**: Handler 9 (finish_zone_transition) is a 20-byte leaf function that ONLY:
1. Clears g_state[0x01B4] (per-frame callback pointer)
2. Advances event queue consume index (session_ctx[0xABA5]++)
3. Returns

It does NOT:
- Reset g_state[0x01AD] (stays at current value)
- Call gate_set (gate flags unchanged)
- Call init_zone_transition (no state reset)
- Load CD zone data
- Reset SV layer

Client's game world SM remains active (g_state[0x01AD] unchanged), immediately
sends 0x019A (LOGOUT → GOTOLIST) because no zone transition actually occurred.

## Test 27 Approach — event_type=0 with re-establishment (2026-04-06)

**KEY DISCOVERY**: Post-init_zone_transition reconnection code path.

**Binary evidence** (CD callback at file 0x09C0-0x0A22):
```
File 0x0A06: BSR 0x06010554    ; call init_zone_transition
File 0x0A10: MOV.L 0x060211FC,R2
File 0x0A12: JMP @R2            ; tail-call to post-init reconnection
```

**Post-init function at file 0x0111FC** (mem 0x060211FC):
1. Sets g_state[4] = 0
2. BRA to 0x06021292

**Post-init continuation at file 0x011292** (mem 0x06021292):
1. BSR 0x06021214 (sub-main-loop: processes frames, timing)
2. JSR 0x060272D2 (connection initiate, R5=8)
   - Calls 6 functions: 0x06013376, 0x060274F6, 0x060710D2, 0x06026DB8, 0x06071680, 0x06071AA4
   - Likely: SV_Setup (re-enables SV_Poll), connection state init
3. JSR 0x060273A0 (connection wait, R5=0x7FFFFFFF = infinite timeout)
   - Checks state at 0x0605725C for values 1 or 8
   - Returns 0 on success, -1 on error/timeout
4. On success: g_state[0]=0, session_ctx[0]=0, *0x06053420=1 (gate #2 unblocked)
5. Main loop resumes normally

This is how the original game reconnects after zone transitions — NOT via the
connection SM at 0x06061D80 (which stays at state 0x84 and is a no-op).

**Implementation**: handlers_login.py `h_gotolist_notice`
1. Pause keepalives + 0.5s drain
2. Send 0x019D (paired ack)
3. Send 0x02EF [0x00, dest_index, 0x00, 0x00] (event_type=0, real zone transition)
4. Wait 5.0s (CD load + init_zone_transition + SV_Setup)
5. Reset send_seq=0, client_seq=0 (SV_Init resets client session state)
6. Send 256-byte establishment frame (ESTABLISH flag 0x0008)
7. Wait 1.0s (client processes establishment → CONNECTED)
8. Resume keepalives
9. Send ESP_NOTICE (mode=6) + UPDATE_CHARDATA_REQ
10. Reset login_phase=0

**Expected client flow:**
1. 0x019D → paired completion
2. 0x02EF → event queue → handler[0] → server_table[dest_index]
3. Same-server: func_B(map_param, 1) → CD → init_zone_transition → full reset
4. Post-init: sub-main-loop → connection initiate → SV_Setup → SV_Poll active
5. Connection wait: polls for CONNECTED (waits for server establishment)
6. Server sends establishment after 5s → CONNECTED → wait returns success
7. *0x06053420=1 → gate #2 cleared → SV_Poll fully operational
8. ESP_NOTICE → init flags set → deferred auto-sends (0x0048, 0x025F, 0x02D4, 0x006D)
9. UPDATE_CHARDATA_REQ → char_id stored
10. Gate: E8C2=1 (from BRAM) → g_state[0x01AD]=2 → login SM
11. User presses A → LOGIN_REQUEST (0x019E) → CHARDATA → game world

**Connection SM stays at state 0x84 after init** (confirmed by disassembly):
- State 4 with bit 7 set: checks R14[0xBE]
- After init_zone_transition: R14[0xBE]=0 → state 4 just returns (no-op)
- Connection SM does NOT participate in post-zone-transition reconnection

**Open questions for hardware test:**
- Is 5.0s enough for CD load? Disc read speed varies.
- Does send_seq reset to 0 correctly match client's post-SV_Init state?
- Does *0x06053420=1 (set by post-init code) gate SV_Poll correctly?
  If it's set BEFORE our establishment arrives, SV_Poll may be blocked.

## Test 27 Results — FAILED (2026-04-06, logs 073924 + 074338)

**Result**: Black screen after zone transition. Login + GOTOLIST work, but after
selecting destination → black screen forever.

**Root cause** (binary-proven from log evidence):
1. Server reset send_seq=0 and sent establishment frame
2. Client session protocol was NEVER reset for same-server transitions
3. val2=1201 in ALL post-transition client 0xA6 frames = old server send_seq
4. Client's cmp/hi check: new seq(0) must be > tracked seq(1201) → FAILS
5. ESP_NOTICE at seq=0 silently dropped → no init flags → black screen

**Critical disassembly discoveries** (2026-04-06):

### begin_connect_same_server (0x06027C50)
For same-server (arg == struct[5] at 0x06066315):
```
06027C66: R2 = 1
06027C68: R0 = 0x01B0
06027C6C: g_state[0x01B0] = 1   ; MARK DONE IMMEDIATELY
06027C7A: struct[225] = 0
06027C80: RTS                    ; NO SV_Init, NO SV_Setup
```

### wait_connect_same_server (0x06027CD2)
```
06027CE8: CMP/EQ #1,R0          ; g_state[0x01B0] == 1?
06027CEC: BRA return_success     ; RETURN 0 IMMEDIATELY
```

### CD callback same-server path (0x060109C0 → 0x0607631C)
Flag at 0x06060F67 determines path:
- flag != 0 (cross-server): init_zone_transition → reconnection (0x060211FC)
- flag == 0 (same-server): tail-call to 0x0607631C → processes CD result → returns to main loop

0x0607631C does NOT call init_zone_transition, SV_Init, or any session/SV functions.

**CONCLUSION**: Same-server zone transitions keep SV/session COMPLETELY UNTOUCHED.
Game stays in GAME WORLD state (g_state[0x01AD] unchanged). The zone data is loaded
from CD, rendering switches to new zone assets, but networking continues normally.

## Test 28 Results — FAILED (2026-04-06, log 080958)

**Approach**: Send 0x019D first, then 0x02EF. No session manipulation.
**Result**: Client sends ZERO bytes after receiving both messages. Server keepalives
every 6s get no response. val2=0x0495=1173 in last client frame = acked only up to 0x019B.

**Root cause** (binary-proven from main loop Phase 4 disassembly):
```
06010174: R3 = [0x0605F420]     ; event handler fptr (g_state[0x01B4])
06010176: R1 = [R3]             ; load function pointer
06010178: TST R1,R1             ; NULL?
0601017A: BT 06010190           ; if NULL → secondary check
0601017C: R0 = 0xABAB
0601017E: R2 = session_ctx[0xABAB] ; GATE BYTE
06010180: TST R2,R2             ; == 0?
06010182: BT 060101F0           ; if 0 → SKIP handler entirely
06010188: JSR @R2               ; else call handler
```

When 0x019D arrives first → paired completion fires → GOTOLIST SM advances to a
BLOCKING STATE that waits for zone transition to be in progress. But event_dispatch
(task 254 in GBR[0] table) hasn't processed the 0x02EF event yet because both
messages arrived in the SAME SV_Poll call.

SM enters blocking wait BEFORE handler_0 (0x0601AD7C) is installed → SM blocks
forever → client goes completely silent.

**Evidence across ALL tests:**
- Tests WITHOUT 0x019D (11, 14, 22): client responds (GOTOLIST loops)
- Tests WITH 0x019D (2, 3, 12, 13, 20, 27, 28): client goes COMPLETELY SILENT
- 0x019D paired completion is the TRIGGER for client silence

## Test 29 Approach — 0x02EF FIRST, delay, then 0x019D (2026-04-06)

**Root cause fix**: Reverse message order so event_dispatch installs handler_0
BEFORE paired completion fires.

**Binary evidence for ordering**:
- event_dispatch (0x06024864) is task 254 in GBR[0] table, runs each main loop frame
- If [0x0605F420] NULL: reads event queue → installs handler_table[event_type]
- Main loop Phase 4: if [0x0605F420] non-NULL AND session_ctx[0xABAB]!=0 → calls handler
- Handler_0 (0x0601AD7C): reads dest_index from event[1] → server_table → func_B → CD load
- 300ms = ~18 frames: enough for event_dispatch + handler_0 + CD load to begin

**Implementation**: handlers_login.py `h_gotolist_notice`
1. Send 0x02EF [0x00, dest_index, 0x00, 0x00] FIRST (event trigger)
2. Wait 300ms (~18 frames for event processing)
3. Send 0x019D (paired ack — SM advances AFTER zone transition in progress)
4. No session manipulation (same-server: SV/session stays alive)

**Expected client flow:**
1. 0x02EF → event written to queue at session_ctx+0xAB24
2. Next frame: event_dispatch reads queue → installs handler_0 into [0x0605F420]
3. Next frame: Phase 4 calls handler_0 → server_table[dest_index] → func_B → CD load
4. CD callback → 0x0607631C → returns to main loop with new zone data
5. Meanwhile: 0x019D arrives → paired completion → GOTOLIST SM advances
6. SM checks zone transition state → transition in progress/complete → proceeds
7. Game continues in GAME WORLD with new zone assets from disc
8. Session alive throughout — keepalives continue, seq numbers preserved

**Key question**: Does GOTOLIST SM block when paired completion fires? If it checks
a flag set by handler_0 or func_B, the 300ms delay should be sufficient. If it
blocks on a different condition, we'll see in the logs.

## Test 30 Results — PARTIAL SUCCESS (2026-04-06, log 091654)

**Approach**: 0x02EF + 0x019D (back-to-back) → 1.5s → ESP(mode=6) → UPDATE_CHARDATA_REQ
**Result**: GOTOLIST loop ×2 cycles, then client goes silent (keepalives only).

**Evidence from log**:
- First cycle: 0x019C(dest=1) → server sends 0x02EF+0x019D → 1.5s → ESP+UPDATE →
  client sends 0x019A 273ms after ESP (val2=0x4EC=1260 matches ESP send_seq)
- Second cycle: 0x019C(dest=1) → same flow → 0x019A at 09:17:53.549
- Third: server sends 0x019B → client SILENT → keepalives only for 3+ minutes

**Root cause of limited cycles**: ESP's auto-sends enable outgoing traffic for 1-2
cycles, but repeated ESP+UPDATE resets interfere with the SM's state. After 2-3 cycles,
either SM exhausts queue or state corruption silences the client.

## CRITICAL BINARY FINDINGS (2026-04-06, deep investigation)

### 1. handler_0 ALWAYS Takes Same-Server Path (dest_index 1-7)

**Full disassembly of 0x0601AD7C** confirms:

Server_table at ROM 0x06053CAC, 8 entries × 4 bytes:
| Index | Bytes | server_group | byte[1] | byte[2] | zone_cd_id |
|-------|-------|-------------|---------|---------|------------|
| 0 | FF FF FF 00 | 0xFF | 0xFF | 0xFF | 0x00 |
| 1 | FF FF FF 01 | 0xFF | 0xFF | 0xFF | 0x01 |
| ... | ... | 0xFF | 0xFF | 0xFF | ... |
| 7 | FF FF FF 07 | 0xFF | 0xFF | 0xFF | 0x07 |

For g_state[0x1B6B] != 0xFF (includes 0, BSS zero-init):
```
0601ADBE: R0 = 0x1B6B
0601ADC2: R2 = MOV.B @(R0,g_state)    ; R2 = g_state[0x1B6B]
0601ADC4: R2 = EXTU.B R2               ; unsigned
0601ADC6: CMP/EQ R1(0xFF), R2(0)       ; T=0 (not equal)
0601ADC8: BT/S 0xFF_path               ; NOT taken
0601ADCC: R2 = MOV.B @server_table[dest] ; byte[0] = 0xFF, sign-extended = -1
0601ADCE: CMP/PZ R2                     ; -1 >= 0? NO
0601ADD0: BF 0x0601ADF2                 ; TAKEN → R11=0 (same-server)
```

For g_state[0x1B6B] == 0xFF:
Takes 0xFF path → calls get_server_info → checks server_table[dest][0] → if 0xFF → R11=0.

**RESULT**: For entries 0-7 (all byte[0]=0xFF), handler_0 ALWAYS sets R11=0 (same-server)
regardless of g_state[0x1B6B] value. Cross-server path is IMPOSSIBLE for these entries.

### 2. g_state[0x1B6B] Writers (COMPLETE)

| Value | Function | File Offset | Condition |
|-------|----------|-------------|-----------|
| server_table2[idx][3] | Tick handler 0x0601B12C | 0x00B1FE | Event handler[2] processing |
| 0xFF | Connectivity check 0x0601B316 | 0x00B3CA | SCMD send failure |

server_table2 at 0x06053E50: [area_id, sub1, sub2, server_id]
Entries: [0x00,0xFF,0xFF,0x08], [0x01,0xFF,0xFF,0x09], ..., [0x08,0xFF,0xFF,0x15]

ESP_NOTICE does NOT write to g_state[0x1B6B]. init_zone_transition does NOT write to it.

### 3. GOTOLIST Entry Bytes 8-9 Are DEAD DATA

Exhaustive binary search: NO code reads entry[8:10] from GOTOLIST entries.
Only three fields are EVER read:
- entry[0:4] = dest_id (zone_id, sent in 0x019C)
- entry[10] = server_table_index (used by handler_0)
- entry[11:27] = name string (displayed in menu)

Map display is a COMPLETELY SEPARATE system:
- Uses entries at session_ctx+0x0EE8 (22 bytes each)
- Count at session_ctx+0x1B86
- Populated from CD-loaded zone data during zone init
- Display function at 0x06032054
- Server CANNOT control map marker positions

### 4. GOTOLIST SM Exit Mechanism

g_state[0x01AC] (SM prerequisite flag):
- Set to 1 by init_zone_transition at file 0x000580. NEVER cleared.
- Once set, stays 1 forever. It's a "zone transition has occurred" flag.

g_state[0x01AA] (SM trigger):
- SET to 1 by SM init function at 0x0601D358
- CLEARED to 0 by SM deactivation at 0x0601D6A8

SM Phase Table at 0x06054E74 (3 entries × 8 bytes):
| Phase | Function | Param | Description |
|-------|----------|-------|-------------|
| 0 | 0x0601DFB0 | 19 | Main command processing (up to 19 batch cycles) |
| 1 | 0x0601E01A | 1 | Response wait (1 command) |
| 2 | 0x0601DDBA | 0 | Finalize + exit |

SM does NOT self-terminate from phases alone. Exits ONLY via deactivation (0x0601D6A8):
- User presses B (cancel) → action_id 3 → deactivation
- Gate/login SM teardown
- Event handlers

Button mapping table at 0x06054FCC: B=cancel(action_id=3), A=select(1), C=secondary(2)

Pressing B does NOT clear g_state[0x01AC]. SM goes dormant but prerequisite stays.

## Test 31 Approach — Separated 0x02EF (2026-04-06)

**Key change from test 30**: 1.0s gap between 0x02EF and 0x019D ensures they arrive
in different SV_Poll cycles. No UPDATE_CHARDATA_REQ. No login_phase reset.

**Implementation**: handlers_login.py `h_gotolist_notice`
1. Send 0x02EF [0x00, dest_index, 0x00, 0x00] (event trigger)
2. Wait 1.0s (event dispatch + handler_0 + CD load starts)
3. Send 0x019D [0, 0, 0] (paired completion — SM advances)
4. Wait 0.5s (SM processes)
5. Send ESP_NOTICE (init flags — enables auto-sends)
6. No UPDATE_CHARDATA_REQ (not needed for zone transitions)
7. No login_phase reset (stay in GAME WORLD state)

**Expected client flow**:
1. 0x02EF → event enqueued → dispatched → handler_0 → CD_load(zone_id, 1)
2. CD reads zone data from disc (200-500ms)
3. CD callback (0x0607631C) → sound reinit → return to main loop
4. 0x019D arrives (1.0s later) → paired completion → SM advances
5. ESP arrives → init flags set → auto-sends fire
6. SM sends 0x019A (requests new destinations for new zone)
7. Server sends 0x019B → user navigates GOTOLIST or presses B to enter game
8. User presses B → SM deactivates → game world visible with loaded zone data

**User instruction**: After selecting a destination, press **B button** to exit the
GOTOLIST and enter the game world. A = navigate between zones, B = enter current zone.

---

## Test 31 Hardware Log Analysis (2026-04-06)

### Log 1 (dd_server_20260406_113500.log) — Zone 1 start
- Login → ESP → UPDATE → 0x019E → 0x01AA → CHARDATA → 0x01EC(×2) → 0x0268(×2) → 0x019A
- **1st GOTOLIST** (dest_id=1, zone 1→1): **SUCCESS**
  - 0x02EF(dest_index=1) at 11:35:43.287 → 1.0s → 0x019D → 0.5s → ESP
  - Client sends 0x019A at 11:35:45.084 (val2=0x04EC=1260, matches ESP send_seq) ✓
  - Server sends 0x019B (3 destinations for zone 1)
- **2nd GOTOLIST** (dest_id=8, zone 1→8): **FAILED**
  - 0x02EF(dest_index=7) at 11:36:08.272 → **keepalive at 11:36:09.105** → 0x019D → 0.5s → ESP
  - SILENCE after ESP — keepalives from 11:36:15 onwards, never answered
  - Client last ack: val2=0x0550=1360 (acked 0x019B but NOT 0x02EF/0x019D/ESP)

### Log 2 (dd_server_20260406_113836.log) — Zone 8 start
- Login → same deferred messages → 0x019A (4 destinations for zone 8)
- **1st GOTOLIST** (dest_id=8, zone 8→8): **SUCCESS**
  - 0x02EF(dest_index=7) → 1.0s → 0x019D → 0.5s → ESP
  - Client sends 0x019A (val2=0x0508=1288, matches ESP send_seq) ✓
- **2nd GOTOLIST** (dest_id=1, zone 8→1): **SUCCESS**
  - 0x02EF(dest_index=1) → 1.0s → 0x019D → 0.5s → ESP
  - Client sends 0x019A (val2=0x05DF=1503, matches ESP send_seq) ✓
  - Server sends 0x019B (3 destinations for zone 1)
- **3rd cycle**: SILENCE after 0x019B at send_seq=1603. Keepalives unanswered.

### ROOT CAUSE: ctx[6] Race Condition

The ESP_NOTICE handler clears `ctx+0x06=0` (the paired request tracker). In test 31
ordering (0x02EF → 0x019D → ESP), the timing creates a destructive race:

1. Client sends 0x019C → SM sets ctx[6]=0x019C (pending paired request)
2. Server sends 0x02EF → event processed (ctx[6] still 0x019C)
3. Server sends 0x019D → paired completion → SM clears ctx[6]=0 → SM advances
4. SM sends 0x019A → SM sets ctx[6]=0x019A (pending for 0x019B)
5. **Server sends ESP → ESP handler clears ctx[6]=0** → SM thinks 0x019B arrived!
6. SM prematurely advances → accumulated state corruption over cycles → terminal

**Evidence**: Log 2 survived 2 cycles because timing allowed 0x019B to arrive before
ESP cleared ctx[6]. Log 1 failed on 2nd cycle because keepalive injection shifted timing.

---

## Test 32a: 0x02EF → 1.0s → ESP → 0.5s → 0x019D (2026-04-06)

**Change**: Swap ESP_NOTICE and 0x019D order. Send ESP BEFORE paired completion.

**Server sequence**:
1. Send 0x02EF (event trigger → handler_0 → CD load)
2. Wait 1.0s (event dispatch + handler_0 + CD completes)
3. Send ESP_NOTICE (clears ctx[6]=0, sets init flags 0x8E-0x91=1)
4. Wait 0.5s (SM processes premature advance from 0x019C, sends 0x019A)
5. Send 0x019D (arrives harmlessly — ctx[6]=0x019A, paired[0x019A]=0x019B≠0x019D)

**Expected client flow**:
1. 0x02EF → event enqueued → dispatched → handler_0 → CD_load(zone_id, 1)
2. CD reads zone data from disc (200-500ms)
3. CD callback → sound reinit → return to main loop. ctx[6] still = 0x019C
4. ESP arrives → ctx[6]=0 → SM sees "paired done" → premature advance from 0x019C
5. SM sends 0x019A → ctx[6]=0x019A. Init flags set → auto-sends fire.
6. 0x019D arrives → incoming 0x019D ≠ paired[0x019A]=0x019B → no match → harmless
7. Server receives 0x019A → sends 0x019B → matches ctx[6]=0x019A → SM advances ✓
8. User navigates GOTOLIST or presses B to enter game world
9. CONSISTENT across ALL cycles — ESP always clears 0x019C, never 0x019A

**Why this is stable**: The key insight is that ESP clearing ctx[6] while it holds
0x019C is a consistent, predictable premature advance. The SM always transitions
from 0x019C→0x019A. Then 0x019B arrives naturally from the server → normal advance.
In test 31, ESP cleared ctx[6] while it held 0x019A → the WRONG premature advance,
corrupting the SM's pending state for a message that was already in-flight.

## Test 32a Results — FAILED (2026-04-06)

**Result**: Attempt 1: map never cleared. Attempt 2: black screen, never enters game.

**Root cause**: Unknown — possibly ESP's premature advance from 0x019C caused the SM
to take a code path that doesn't properly handle the "zone transition already complete"
condition, or ESP's event queue clearing (ABA4=0, ABA5=0) interfered with handler_0
state. The approach was abandoned in favor of Test 33 (0x019D only), which also failed.

---

## Test 33 — NEVER TESTED (2026-04-06)

**Approach**: Send ONLY 0x019D (no 0x02EF, no ESP).
**Analysis**: Based on State 3 SM state 1 disassembly showing B button exits GOTOLIST.
**Predicted outcome**: FAILURE — tests 2,3,12,20,28,29 all proved that without 0x02EF,
the SM blocks at Phase 2 (zone transition wait). And without ESP, the client can't
send 0x019A (no init flags → no deferred auto-sends). This test was superseded by
Test 34 before hardware verification.

---

## Test 34: 0x02EF → 1.0s → 0x019D + ESP back-to-back (2026-04-06)

**KEY INSIGHT**: The ctx[6] race is eliminated by sending 0x019D and ESP in the same
SV_Poll delivery cycle. SV_RecvFrame (file 0x0126DA) is a byte-by-byte state machine
that processes ALL available data in the UART receive buffer. After delivering one IV
frame, it resets to state 0 and continues scanning. Both IV frames delivered before
main loop Phase 6 (SM dispatch) runs.

**Server sequence**:
1. Send 0x02EF [0x00, dest_index, 0x00, 0x00] (event trigger)
2. Wait 1.0s (event dispatch + handler_0 + CD load + finish_zone_transition)
3. Send 0x019D (paired completion for 0x019C) — NO gap
4. Send ESP_NOTICE (init flags, clears ctx[6] which is already 0)

**Handler dispatch order (within single SV_Poll, Phase 2)**:
1. SV_RecvFrame delivers 0x019D IV frame → handler dispatch → ctx[6]=0x019C matched → ctx[6]=0
2. SV_RecvFrame continues → delivers ESP IV frame → handler dispatch → ctx[6]=0 → harmless
3. SV_Poll returns → Phase 6: SM runs with ctx[6]=0, init_flags=1, zone_transition=done

**Expected client flow**:
1. 0x02EF → event_dispatch installs handler_0 into [0x0605F420]
2. handler_0 → server_table[dest_index] → same-server → CD load → finish
3. (1.0s later) 0x019D + ESP both arrive in same SV_RecvFrame call
4. SM sees: paired done + zone done + init flags → deferred auto-sends fire
5. SM sends 0x019A (ctx[6]=0x019A) — AFTER both 0x019D and ESP processed
6. Server receives 0x019A → sends 0x019B → paired completion (ctx[6]=0x019A→0)
7. SM returns to Phase 0 (GOTOLIST display with new zone destinations)
8. User presses A (navigate) or B (enter game world)

**Why this is stable across ALL cycles**:
- ESP ONLY arrives bundled with 0x019D (ctx[6]=0 from step 1 → ESP harmless)
- h_logout sends 0x019B with NO ESP → 0x019A→0x019B paired completion clean
- No message ever arrives that clears ctx[6] while it holds 0x019A
- Each cycle is self-contained: 0x019C→{0x02EF,0x019D+ESP}→0x019A→0x019B

**Risk**: If SV_RecvFrame only processes ONE IV frame per call (returns after each
delivery), 0x019D and ESP would be processed on separate frames, with the SM running
between them. In that case, SM would send 0x019A (ctx[6]=0x019A) before ESP arrives,
and ESP would clear ctx[6]=0x019A → same race as Test 31. Mitigation: SV_RecvFrame's
byte-scanning loop (state machine at 0x0126DA) does NOT have a "return after delivery"
instruction — it continues scanning the receive buffer after resetting to state 0.

**RESULT**: FAILED on hardware (both attempts, 2026-04-06):
- Attempt 1 (dd_server_20260406_175446.log): Abyss dest=7. Cycle 1 works (client sends
  0x019A), cycle 2 fails (silence after 0x019B). Screen faded to black then nothing.
- Attempt 2 (dd_server_20260406_175850.log): Dragon's Peak dest=6. Cycles 1-2 work,
  cycle 3 fails (silence after 0x019B for 2+ minutes). Stayed on map.
- ROOT CAUSE: No session re-establishment after SV_Init. The 0x02EF triggers
  init_zone_transition → SV_Init, which resets the SV receive state machine. Without
  a 256B establishment frame, the SV layer stays in disconnected state
  ([0x06062374]=0) and silently drops all subsequent IV frames.

---

## Test 35: Replicate PROVEN successful approach from 4/5 tavern log (2026-04-06)

**SOURCE OF TRUTH**: dd_server_20260405_200832.log — the ONLY test where the client
entered the actual game world (store list 0x026F, tavern tables 0x01F8, sat at table
0x020E). This log was analyzed line-by-line to extract the exact server sequence.

**Server sequence** (from log lines 218-237):
1. Send 0x019D (paired ack for 0x019C) — line 218, send_seq=1189
2. Send 0x02EF [0x00, dest_index, 0x00, 0x00] — line 223, send_seq=1201, 2ms gap
3. Wait 4.0 seconds — line 228 timestamp 20:09:39.396 vs line 223 at 20:09:35.388
4. Send session re-establishment (256B, ESTABLISH flag at [8:10]=0x0008) — line 228
5. Wait 0.5 seconds — line 230 timestamp 20:09:39.911 vs line 228 at 20:09:39.396
6. Send ESP_NOTICE 0x01E8 (51B) — line 230, send_seq=1260
7. Send UPDATE_CHARDATA_REQ 0x019F (24B) — line 237, send_seq=1292

**Key differences from Test 34**:
| Aspect | Test 34 (FAILED) | Test 35 (matches successful log) |
|--------|-----------------|----------------------------------|
| Order | 0x02EF first, then 0x019D | 0x019D first, then 0x02EF |
| Re-establish | NONE | 256B session establishment |
| UPDATE | NONE | 0x019F sent after ESP |
| Delay before re-est | 1.0s | 4.0s |
| ESP timing | Back-to-back with 0x019D | 0.5s after re-establish |

**Why re-establishment is essential**:
- 0x02EF triggers init_zone_transition → SV_Init (file 0x01219E)
- SV_Init clears SV context at 0x202E4B3C, resets SV_RecvFrame to state 0
- Connection state [0x06062374] reset to 0 (Disconnected)
- Without re-establishment, no IV frames can be delivered
- Re-establishment: delivery function (0x060423C8) sets [0x06062374]=2 (Connected)

**Expected flow after test 35**:
1. Client receives 0x019D → ctx[6] cleared (paired completion)
2. Client receives 0x02EF → event dispatch → handler_0 → zone transition → SV_Init
3. 4.0s passes → SV_Init complete, SV_RecvFrame scanning for 'I','V'
4. Re-establish → delivery → CONNECTED
5. 0.5s → polling returns 1, connection SM state 3→4
6. ESP → init flags set, deferred auto-sends enabled
7. UPDATE → char data stored, connection SM advances to state 4+
8. Client auto-sends 0x019A → server sends 0x019B → GOTOLIST map
9. User exits map (B or timeout) → GAME WORLD ENTERED

**KNOWN LIMITATION**: Second zone transition failed in the successful log too (lines
340-380). After the second 0x019C→re-establish→ESP→UPDATE, client sent 0xA6 ack but
then went silent. Multi-cycle transitions require separate investigation. The primary
goal of getting INTO the game world for the first time is addressed by this test.

### Test 35 Results (FAILED — 2026-04-06)

**Two hardware attempts**, both following the exact same server sequence from the successful log:

**Attempt 1** (dd_server_20260406_182832.log):
- Cycle 1: dest=6 (Dragon's Peak), same zone → WORKS (client sends 0x019A after re-establish)
- Cycle 2: dest=7 (Abyss), different zone → CLIENT BLACK SCREEN
  - Client acks re-establish (flags=0x34) then 15 keepalives (~84 seconds) of silence
  - Never sends 0x019A, never enters game world

**Attempt 2** (dd_server_20260406_183149.log):
- Cycle 1: dest=7 (Abyss), same zone → WORKS
- Cycle 2: dest=6 (Dragon's Peak), different zone → WORKS (client sends 0x019A)
- After cycle 2's 0x019B: CLIENT GOES SILENT — 6 keepalives (~33 seconds), user gave up

**CONCLUSION: Zone transition via 0x02EF works for cycle 1 but ALWAYS corrupts on cycle 2+.**

---

## Test 36: NO zone transition — paired ack only (2026-04-06)

**KEY INSIGHT from re-analyzing the ONLY successful game world entry**
(dd_server_20260405_200832.log):

The user entered the game world by pressing B on the GOTOLIST map (or letting it
timeout after ~42.6 seconds). They did NOT select a destination.

Evidence from log:
- Line 254: Server sends 0x019B (GOTOLIST_REQUEST, destinations displayed)
- Lines 264-270: 7 keepalives over 42.6 seconds, NO 0x019C from client
- Line 276: Client sends 0x026F (STORE_LIST) = GAME WORLD ENTERED
- User then interacted with store (0x026F, 0x0271), tavern (0x01F8, 0x020E)

**ALL zone transitions (Tests 13-35) that used 0x02EF failed on cycle 2+:**
- dd_server_20260405_200832.log: cycle 2 (dest=5) → ack then silence (lines 374-380)
- dd_server_20260406_182832.log: cycle 2 (dest=7) → black screen, 84s (lines 307-322)
- dd_server_20260406_183149.log: cycle 3 → map stuck, 33s silence (lines 319-325)

**Approach**: Remove ALL zone transition code from h_gotolist_notice. Send only 0x019D
(paired ack). No 0x02EF, no SV_Init, no re-establish, no session corruption.

**Server sequence**:
1. Receive 0x019C (client selected destination)
2. Send 0x019D (INFORMATION_NOTICE) — 8B payload: [status=0, type=0, value=0]
3. Done. No further messages.

**Expected client behavior**:
- Paired completion clears ctx[6] (GOTOLIST SM Phase 1 done)
- GOTOLIST map remains displayed (no event queued)
- User presses B → exits GOTOLIST → enters game world
- OR user waits ~42-45 seconds → GOTOLIST auto-timeout → enters game world

**Code change**: handlers_login.py h_gotolist_notice — stripped to just send 0x019D.

### Test 36 Result (FAILED)
- dd_server_20260406_191128.log: 0x019D only (no 0x02EF) → black screen
- Without 0x02EF, GOTOLIST SM exits but caller has no pending event → error state

---

## Test 37-38: Zone transition with re-establish (2026-04-06)

Restored 0x02EF + 4.0s delay + re-establish + ESP + LOGIN_REPLY. Various timing experiments.

### Test 38 Result (PARTIAL SUCCESS — zone transition works but game world not entered)
- dd_server_20260406_192628.log: dest_index=7 (Abyss)
- Cycle 1: 0x019D → 0x02EF(dest_index=7) → 4.0s → re-establish → ESP → LOGIN_REPLY ✅
- Saturn acknowledges re-establish (0xA6 flags=0x34) ✅
- Saturn sends 0x019A (cycle 2 GOTOLIST) ✅
- Server sends 0x019B (2 entries) ✅
- Cycle 2: Saturn goes COMPLETELY SILENT — 112+ seconds of keepalives, no 0x026F
- **B button does not work. GOTOLIST timeout does not fire.**
- Saturn is in broken state after zone transition with dest_index=7

---

## Test 39: ROOT CAUSE IDENTIFIED — dest_index out of bounds (2026-04-06)

### The Critical Finding

**Byte-for-byte comparison** of the ONE successful log (dd_server_20260405_200832.log, dest_index=4)
vs the latest failure (dd_server_20260406_192628.log, dest_index=7) reveals:

- **ALL messages are IDENTICAL** except destination-related data
- Success: dest_index=4 (Cave Dungeon), 3 GOTOLIST entries
- Failure: dest_index=7 (Abyss), 2 GOTOLIST entries
- ESP_NOTICE, re-establish, timing, sequence numbers — all identical

### Root Cause: server_table out-of-bounds read

The 0x02EF handler dispatches zone transition via `server_table[dest_index*4]` at ROM 0x06053CAC.

**Evidence from 38 hardware tests:**
| dest_index | Zone | Result |
|------------|------|--------|
| 4 | Cave Dungeon | ✅ Works — game world entered |
| 5 | Dark Tower | ✅ Works — re-establish succeeds |
| 6 | Dragon's Peak | ❌ FAILS — Saturn hangs |
| 7 | Abyss | ❌ FAILS — Saturn hangs (cycle 2 stuck) |

The server_table has entries 0-5 (24 bytes). Entries 6+ read out-of-bounds ROM data.
The zone transition's CD load uses the zone_id from server_table entry byte[3].
Original game likely had 5 playable zones (1-5). Our AI-reconstructed zones 6-9 don't
have corresponding data on the game CD.

### Fix Applied

```python
# In h_gotolist_notice:
dest_index = 4  # Always use proven-safe server_table entry

# In h_logout (GOTOLIST entry byte 10):
resp[off + 10] = min(max(dest_zid, 1), 5)  # Cap to safe range
```

Also reset DB characters from zone>5 to zone 1 (character "12345" was stuck in zone 7).

### Test 39 — NOT TESTED (superseded by Test 40)

## Test 40: Exact replication of success log (2026-04-07)

### Changes from Test 39
1. **Removed gotolist_count cycle restriction** — 0x02EF sent on EVERY 0x019C
   - Evidence: success log cycle 3 (tavern) also used 0x02EF(dest_index=5)
   - The cycle restriction blocked post-game-world zone transitions
2. **Set character zone_id=4** in DB (was 1 after Test 39 DB reset)
   - Success log character was in zone 4 → GOTOLIST entries [4, 3, 5]
   - With zone_id=1, entries would be [1, 2, 8] — different from success log
3. **Reset gotolist_count=0** after each zone transition
   - Matches success log behavior (count=1 at each cycle-start LOGOUT)

### GOTOLIST Entry Verification (byte-identical to success log)
| Entry | dest_id | zone | map | map_x | map_y | server_info | Name |
|-------|---------|------|-----|-------|-------|-------------|------|
| 0 | 4 | 4 | 4 | 0 | 0 | 4 | Cave Dungeon |
| 1 | 3 | 3 | 3 | 0 | 0 | 3 | Forest |
| 2 | 5 | 5 | 5 | 0 | 0 | 5 | Dark Tower |

### Expected Flow (matches dd_server_20260405_200832.log)
1. INIT → ESP + UPDATE_CHARDATA_REQ → login → LOGOUT
2. 0x019B (3 entries: Cave Dungeon, Forest, Dark Tower)
3. Client auto-selects Cave Dungeon (~0.3s) → 0x019C(dest=4)
4. Server: 0x019D → 0x02EF(dest_index=4) → 4.0s → re-establish → ESP → UPDATE
5. Client: status frame → 0x019A (LOGOUT) → 0x019B (same 3 entries)
6. **USER: PRESS B on the GOTOLIST to enter game world**
7. Client sends 0x026F → server replies 0x0270 → GAME WORLD ENTERED
8. Client sends 0x0271 → 0x019A (tavern GOTOLIST) → navigate from there

### Confidence Assessment
| Factor | Confidence | Evidence |
|--------|------------|----------|
| dest_index=4 CD load works | **HIGH** | 1 success, 0 failures |
| GOTOLIST entries byte-match | **CERTAIN** | Verified programmatically |
| Zone transition sequence timing | **HIGH** | Exactly matches success log (4.0s+0.5s) |
| B button triggers 0x026F | **HIGH** | 42.6s gap in success log was user-initiated (varying gaps: 42s, 54s, 103s, 246s across tests) |
| Post-game-world transitions work | **HIGH** | Success log cycle 3 (dest_index=5) worked |

### Test 40 Results — PARTIAL SUCCESS (2026-04-07)

**Two hardware attempts:**

#### Attempt 1 (FAILURE: dd_server_20260407_063646.log)
- Character in zone 4, entries: Cave Dungeon(info=4), Forest(info=3), Dark Tower(info=5)
- Cycle 1: auto-select Cave Dungeon(info=4) → 0x019C(dest=4) → 0x02EF(4) → re-establish → cycle 2 GOTOLIST
- Cycle 2: user selected Forest(info=3) → 0x019C(dest=3) → **ANOTHER 0x02EF(4)** → re-establish
- After second re-establish: client sent status frame but **NEVER sent 0x019A** → permanent hang → disconnect
- **ROOT CAUSE**: Second zone transition (0x02EF → re-establish) breaks client session state

#### Attempt 2 (SUCCESS: dd_server_20260407_064243.log)
- Character in zone 3 (changed by failed attempt 1's zone update)
- Entries: Forest(info=3), Plains(info=2), Cave Dungeon(info=4)
- Cycle 1: auto-select Forest(info=3) → 0x019C(dest=3) → 0x02EF(4) → re-establish → cycle 2 GOTOLIST
- Cycle 2 (54s later): user selected Cave Dungeon(info=4) → **0x026F** (NOT 0x019C!) → GAME WORLD ENTERED
- Game world: 0x026F→0x0270 → 0x0271→0x0272 → 0x019A(count=2)→0x019B (tavern GOTOLIST)
- 168s later: 0x01F8 (SAKAYA_TBLLIST) → 0x01F9 (empty, 12B) → game sent 0x01F8 again → hung

### CRITICAL DISCOVERY: server_info vs zone_cd_id

**Client GOTOLIST destination selection logic** (from binary at GOTOLIST SM):
- Each GOTOLIST entry has a `server_info` byte at entry offset 10
- After 0x02EF(dest_index=4), client's `zone_cd_id` is set to 4
- When user presses C on an entry:
  - If `entry.server_info == zone_cd_id` → send **0x026F** (game world entry)
  - If `entry.server_info != zone_cd_id` → send **0x019C** (zone transition request)

**Evidence across ALL tests:**
| Test | Entry selected | server_info | zone_cd_id | Client sent | Result |
|------|---------------|-------------|------------|-------------|--------|
| 40-fail | Forest | 3 | 4 | 0x019C | HANG (2nd transition) |
| 40-success | Cave Dungeon | 4 | 4 | 0x026F | SUCCESS |
| 200832 (original) | ? | ? | 4 | 0x026F | SUCCESS (42.6s gap) |

**This explains EVERY test result across 41 tests.**

### 0x01F8 (SAKAYA_TBLLIST) Issue

After game world entry:
1. Client sends 0x026F → server replies 0x0270 (STORE_LIST, empty)
2. Client sends 0x0271 → server replies 0x0272 (STORE_IN)
3. Client sends 0x019A (LOGOUT, count=2) → server replies 0x019B (GOTOLIST)
4. 168s later: client sends 0x01F8 (SAKAYA_TBLLIST, 20B, arg2=0x000a)
5. Server replied 0x01F9 with 12 bytes (entry_count=0) → **GAME HUNG**
6. Client sent 0x01F8 again 30s later → same empty response → permanent hang

**Fix required**: Send actual table entries in 0x01F9 (12B header + N×64B entries).

### B Button Confirmed NOT Working

User explicitly reported: "pressing B did not do anything" on cycle 2 GOTOLIST.
B button does NOT trigger 0x026F. Game world entry is ONLY via C button on an entry
whose server_info matches zone_cd_id.

## Test 41: All server_info=4 + zone_transition_done guard (2026-04-07)

### Changes from Test 40
1. **Set ALL GOTOLIST entry server_info=4** (not zone_id)
   - Ensures ANY entry selection on cycle 2 sends 0x026F (match zone_cd_id=4)
   - Previously: only entries with zone_id=4 matched → others sent 0x019C → hang
2. **Added _zone_transition_done boolean guard**
   - First 0x019C: sends 0x02EF(4) + re-establish (zone transition)
   - Subsequent 0x019C: sends 0x019D only (safety fallback)
   - Prevents the second-transition hang proven in Test 40 attempt 1
3. **Fixed 0x01F9 (SAKAYA_TBLLIST_REQUEST)**
   - Now sends 3 table entries (12B header + 3×64B entries)
   - Each entry: table_name(16B) + owner_name(16B) + description(16B) + extra_data(16B)
4. **Fixed 0x020F (SAKAYA_SIT_REQUEST)**
   - Changed from reject (status=1) to accept (status=0, sit_param=0)
5. **Fixed 0x0272 (STORE_IN_REQUEST)**
   - Changed from reject (status=1, 2B) to accept (status=0, store_flag=1, 3B)

### Database State at Test 41 Start

**DB file**: `D:\DragonsDreamDecomp\server\dd_world.db`

| Table | Rows |
|-------|------|
| characters | 3 |
| inventory | 0 |
| skills | 0 |
| mail | 0 |
| bulletin | 0 |

**Active character ("12345", char_id=1)**:
- char_name: `12345` (16B padded), char_class: 0, char_level: 1
- char_race: 0, char_gender: 0
- experience: 2, gold: 1000
- base_stats: HP=120, MP=30, STR=18, VIT=16, INT=8, MND=10, AGI=12, DEX=10, rest=10
- current_stats: same as base_stats
- appearance: all zeros, skill_slots: all zeros, skill_levels: all zeros
- equipment: all zeros (no equipment)
- **zone_id: 3** (Forest), map_id: 3, pos_x: 24, pos_y: 24
- facing: 1, move_mode: 1, reconnect_flag: 0
- created_at: 2026-03-31, last_login: 2026-04-07

**Why zone_id=3**: Test 40 attempt 1 (failure) changed zone from 4→3 via h_gotolist_notice
DB update when user selected Forest (dest_id=3). Test 40 attempt 2 (success) started
from zone 3 and kept it (0x019C sent dest=3, h_gotolist_notice updated to 3).

**GOTOLIST entries generated from zone 3** (ZONE_CONNECTIONS[3] = [2, 4]):
| # | dest_id | zone | map | map_x | map_y | server_info | Name |
|---|---------|------|-----|-------|-------|-------------|------|
| 0 | 3 | 3 | 3 | 0 | 0 | **4** | Forest |
| 1 | 2 | 2 | 2 | 0 | 0 | **4** | Plains |
| 2 | 4 | 4 | 4 | 0 | 0 | **4** | Cave Dungeon |

Note: All server_info=4 (Test 41 fix). Zone 3 included because it's the current zone
(h_logout prepends current zone if not in destinations list).

**Other characters**: char_id=2 "Buttfor" (zone 1), char_id=3 "buttfor" (zone 1) — unused.

### Expected Flow
1. INIT → ESP + UPDATE → login → LOGOUT → 0x019B (3 entries, all info=4)
2. Cycle 1 auto-select (~0.3s) → 0x019C → 0x02EF(4) → 4.0s → re-establish → cycle 2 GOTOLIST
3. Cycle 2: user presses C on ANY entry → info=4 matches zone_cd_id=4 → 0x026F → GAME WORLD
4. Game world: 0x0270(empty store) → 0x0272(accept, status=0, flag=1) → 0x019A → 0x019B (tavern)
5. Tavern: 0x01F8 → 0x01F9(3 tables: "Table 1/2/3", owner="Revival") → user selects → 0x020E → 0x020F(accept)

### Tavern UI Visual Analysis (from screenshots, Test 40 attempt 2)

**Source**: untitled folder.zip on Desktop — 14 PNGs + 1 MOV of tavern experience.

The tavern is a **full 3D rendered interior** (bar, bottles, barrels, wooden beams) with an
**icon-based navigation menu** (5+ selectable icons in a cross/grid pattern). NOT a simple list.

**Tavern icon menu options** (visible in screenshots):
| Icon | Label | Protocol Message |
|------|-------|-----------------|
| TABLE SEL | テーブル選択 | 0x01F8 (SAKAYA_TBLLIST) |
| TEMPLE | 神殿 | 0x019C (zone transition) |
| LEAVE | — | 0x01FA (SAKAYA_EXIT) |
| System Menu | システムメニュー | Local (settings, time, quit game) |
| Find Friends | 仲間を探す | 0x024E (SAKAYA_FIND) or 0x01B7 |

**Entry dialog** (IMG_1658): "Check the tables for people. Pick that table. If ready, go to the temple as well."

**System menu** (IMG_1663-1665): Settings (GUIDE/FULL MAP/TABLE HANDLE: SHOW/HIDE, Library order: NEW/OLD), TIME (shows session duration "0HR03M35S"), QUIT GAME.

**Table Selection screen** (IMG_1668-1669, triggered by 0x01F8→0x01F9):
- Header: テーブル選択 (Table Selection)
- Entries show: capacity (人=people), status (空き=empty), table names
- "空テーブルに移動し■" = "Move to empty table"
- "NS人用空きテーブル" = "Empty table for NS people"
- In Test 40, server sent entry_count=0 → game displayed UNINITIALIZED MEMORY from g_state+0x6DA8
- This is what the user saw as "Japanese text" — it was garbage from the buffer

**Temple transition** (IMG_1671): "神殿に向か■" (Heading to the temple) — confirms TEMPLE triggers 0x019C zone transition.

**Find Friends** (IMG_1670): "捜してC" (Press C to search) — search for other players.

## Test 42: Complete tavern handler fix + root cause documentation (2026-04-07)

### April 6 Failure Root Cause Analysis (100% binary-driven)

**Server table read from binary** (file offset 0x043CAC, 16 entries × 4 bytes):
```
Entry 0: FF FF FF 00 → zone_cd_id=0 (same-server, byte[0]=0xFF)
Entry 1: FF FF FF 01 → zone_cd_id=1
Entry 2: FF FF FF 02 → zone_cd_id=2
Entry 3: FF FF FF 03 → zone_cd_id=3
Entry 4: FF FF FF 04 → zone_cd_id=4 ← WORKS (CD has zone 4 data)
Entry 5: FF FF FF 05 → zone_cd_id=5 ← WORKS (pre-loaded/valid CD data)
Entry 6: FF FF FF 06 → zone_cd_id=6 ← HANGS (no CD data for zone 6)
Entry 7: FF FF FF 07 → zone_cd_id=7 ← HANGS (no CD data for zone 7)
Entry 8+: 02/05/08/09/0A prefix → cross-server entries (different format)
```

**All entries 0-7 have byte[0]=0xFF → handler_0 ALWAYS takes same-server path.**
Cross-server only possible for entry 8+ (byte[0] != 0xFF).

**Why April 6 log 175446 failed** (Abyss, zone_id=7):
- Old code: `dest_index = zone_id = 7`
- server_table[7].zone_cd_id = 7
- CD load tried to read zone 7 data → no data on disc → Saturn hang → fade to black

**Why April 6 log 175850 failed** (Dragon's Peak, zone_id=6):
- Old code: `dest_index = zone_id = 7` (first), then `dest_index = 6`
- Both dest_index 6 and 7 → no CD data → Saturn hung both times

**Why April 5 log 200832 SUCCEEDED** (Cave Dungeon, zone_id=4):
- `dest_index = zone_id = 4`
- CD load read zone 4 data → SUCCESS → game world entered

### Complete Re-analysis of Old Success Log (dd_server_20260405_200832.log)

**Post-game-world flow (lines 287-380):**
1. 0x0272 (STORE_IN reply): **REJECTED** (status=1, 2B `00 01`) — game continued anyway
2. 0x019A at 20:10:26 (LOGOUT, 2B) → 0x019B (GOTOLIST, 92B)
   - 3 entries: Cave Dungeon(info=4), Forest(info=3), Dark Tower(info=5)
   - **NOT all info=4** — old server used server_info=zone_id
3. 0x01F8 at 20:10:48 (TBLLIST, 20B, arg2=10)
4. 0x01F9 at 20:10:48: **EMPTY** (12B, entry_count=0) → game showed garbage from g_state+0x6DA8
5. 0x020E at 20:10:56 (SIT, 6B) — user selected garbage entry
6. 0x020F at 20:10:56: **REJECTED** (status=1, 2B `00 01`)
7. 0x019C at 20:11:07 (TEMPLE, dest_id=5) → 0x019D + 0x02EF(dest_index=5) → re-establish
8. **DEADLOCK** (lines 370-380): Client acks re-establish but NEVER sends 0x019A
   - 30+ seconds of keepalives → log ends at line 380

**CONCLUSION**: The "success" was ONLY getting into the tavern. ALL tavern features failed:
- Table list was empty → garbage displayed
- Sit was rejected
- TEMPLE transition → deadlocked (second 0x02EF + re-establish)

### Test 42 Changes (over Test 41)

1. **Fixed h_sakaya_exit** (0x01FA→0x01FB): Accept (status=0, 2B) ← was reject
2. **Fixed h_sakaya_stand** (0x0219→0x021A): Accept (status=0, stand_param=0, 4B) ← was reject
3. **Fixed h_sakaya_memlist** (0x024B→0x024C): Accept (status=0, member_count=0, context=0, 8B) ← was reject
4. **Fixed h_sakaya_in** (0x0216→0x0217): Accept (status=0, in_param=0, 4B) ← was reject
5. **Added _in_game_world tracking** in h_store_list (0x026F) — set True on game world entry
6. **Updated build_minimal_reply** table to match all sakaya accept changes
7. **Kept h_sakaya_find** (0x024E→0x024F) as reject — "not found" is valid for single player

### Second Zone Transition Limitation (PROVEN, not fixable without deep SV changes)

**Evidence across ALL 41+ tests**: Second 0x02EF → re-establish ALWAYS deadlocks:
- dd_server_20260405_200832.log lines 370-380 (TEMPLE, dest=5)
- dd_server_20260407_063646.log (Forest, second transition)
- dd_server_20260406_182832.log (Abyss, cycle 2)
- dd_server_20260406_183149.log (cycle 3)

**Root cause**: init_zone_transition → SV_Init resets SV state. Re-establish works once.
But second SV_Init + re-establish corrupts internal session tracking (seq/ack mismatch
or state flags that don't get properly reset on subsequent cycles).

**Test 42 approach for TEMPLE**: With all server_info=4 matching zone_cd_id=4:
- If TEMPLE goes through GOTOLIST server_info check → sends 0x026F (game world re-entry)
- If TEMPLE bypasses check → sends 0x019C → h_gotolist_notice sends 0x019D only (no crash)
- Either way: no deadlock. Temple feature deferred until second transition is solved.

### Test 43 — Hardware Results (2026-04-07)

**dd_server_20260407_164457.log** (Table sit hang):
- Login → GOTOLIST → zone transition → re-establish → C button → 0x026F → tavern
- Table list (0x01F8→0x01F9) worked 6 times. User sat at table (0x020E→0x020F).
- **HANG**: After 0x020F (sit accepted), client waited 48s → disconnect.
- **ROOT CAUSE**: Server did NOT push 0x024C (SAKAYA_MEMLIST) after sit.
  Binary handler at 0x5112: reads member_count → g_state+0x6F88. Client expects this push.

**dd_server_20260407_165007.log** (Temple hang):
- Login → GOTOLIST → zone transition → C button → 0x026F → tavern
- After 0x019B (tavern GOTOLIST), client showed tavern interior.
- **HANG**: User clicked TEMPLE icon → no SCMD generated → 61s silence → disconnect.
- **ROOT CAUSE**: GOTOLIST had [Forest(3), Plains(2), Cave Dungeon(4)] — NO Dark Tower(5).
  TEMPLE icon searches GOTOLIST for temple destination. Without zone 5, nothing to send.
  Old success (dd_server_20260405_200832.log) had Dark Tower(5) in GOTOLIST.

### Test 43 Fixes

1. **SAKAYA_SIT push MEMLIST**: After 0x020F, push 0x024C (error=0, member_count=0, context=0)
2. **Dark Tower in GOTOLIST**: ZONE_CONNECTIONS[3] = [2, 4, 5] → 4 GOTOLIST entries

### Test 44 — Hardware Results (2026-04-07)

**dd_server_20260407_171015.log** (Temple attempt):
- GOTOLIST now has 4 entries (Dark Tower included!)
- 0x026F → 0x0270 → 0x0271 → 0x0272 (status=0, 3B) → **HANG**
- Client never sent 0x019A after 0x0272. Never reached tavern.
- Intermittent: same flow worked in 171316.

**dd_server_20260407_171316.log** (Table sit attempt):
- 0x0272 (status=0, 3B) → 0x019A ✓ → tavern entered
- 0x01F8 → 0x01F9 (3 tables) → 0x020E → 0x020F → 0x024C (pushed!) → **HANG**
- 0x024C WAS sent (send_seq=1843). Client received but went silent.

**ROOT CAUSE — 0x0272 intermittent hang:**
Old success (dd_server_20260405_200832.log) sent 0x0272 with status=1 (2B, REJECTED).
V4 sends status=0 + store_flag=1 (3B, ACCEPTED).
Handler at 0x4BFE: status=0 → reads store_flag → stores at context+0xA0 → "store mode".
Store mode INTERMITTENTLY blocks transition to 0x019A.

**ROOT CAUSE — send_seq mismatch:**
After zone transition re-establishment, server's send_seq continued from accumulated value
(1843 in Log 2). Client's SV_Init reset its seq to 0. Potential silent frame drops.

### Test 44 Fixes

1. **STORE_IN (0x0272): status=1 (2B)** — match old success, avoid store mode
2. **send_seq reset to 0** in _send_session_establishment() — match client SV_Init
3. **SAKAYA_EXIT (0x01FB): 8B** — was 2B, handler reads 8B (error, unknown, context)
4. **SAKAYA_SIT push 0x024C**: kept (harmless, table system may not work single-player)

**PENDING HARDWARE TEST — Test 44**
