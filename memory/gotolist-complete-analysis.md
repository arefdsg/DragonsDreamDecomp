# GOTOLIST Complete Analysis (2026-04-03)

## Event Enqueue Handler Confirmed
- **msg_type 0x02EF** → handler at 0x06018932 (file 0x008932) — THIS is event enqueue
- **msg_type 0x02F0** → DIFFERENT handler at 0x06018A78 (file 0x008A78)
- Handler table has 199 entries at file 0x0435D8, 8 bytes each: [msg_type:u16][pad:u16][handler_addr:u32]

## GOTOLIST_REQUEST Handler (0x06014930) — PURE DATA PARSER
- Does NOT install callbacks, queue events, or trigger zone transitions
- ONLY parses destination entries and stores them:
  - Entry count → session_ctx+0xB8
  - Entries → session_ctx+0xBC, 28 bytes per entry
- Payload format: [status:u16][count:u16][header:u32][entries...]
- Each entry (28 bytes wire): [u32][u16][u16][u16][u8][skip][16B name at offset 11]
- Zone transition MUST be triggered separately by server sending 0x02EF

## Zone Transition Handler (0x0601AD7C) — Three Paths
Installed at g_state[0x01B4] by event dispatch when event_type=0 from 0x02EF queue.

| R12 | R11 | Path | Action |
|-----|-----|------|--------|
| !=0 | !=0 | 0x0601AE30 | Install reconnection callback (0x0601AE98) at g_state[0x01B4]. Sets g_state[0x01BD]=0. |
| !=0 | ==0 | 0x0601AE40 | Call func_B(server_table[entry][3], 1) + finish_zone_transition |
| ==0 | any | 0x0601AE54 | Just finish_zone_transition |

R11 is determined by server_table[dest_index][0]:
- byte[0] = 0xFF → sign extend = -1 → CMP/PZ fails → **R11=0** (same-server)
- byte[0] = positive value → CMP/PZ passes → **R11=1** (cross-server)

## Same-Server Zone Transition (R11=0)
1. func_B(0, 1) → CD command ring buffer → task 0 → CD subsystem
2. CD subsystem → calls init_zone_transition (0x06010554)
3. init_zone_transition: SV_Init → resets SV connection → state=0, gate_set(0), BRAM load
4. After init: SV is RESET, client waits for server re-establishment
5. **Server MUST re-establish** (send establishment IV frame)

## Cross-Server Zone Transition (R11=1)
1. Installs reconnection callback (0x0601AE98) at g_state[0x01B4]
2. Reconnection state 0: begin_connect_same_server(0x06027C50) — game-level ONLY, NO SV touch
3. Reconnection state 1: wait_connect_same_server(0x06027CD2) — polls completion
4. On complete: task_dispatch(zone_id, 1), restore SV_Poll, finish

## begin_connect_same_server (0x06027C50) — DOES NOT TOUCH SV
- Manages GAME-LEVEL server/zone data at struct 0x06066310
- Checks/sets server_id, channel, zone in connection management struct
- Calls init_connection(0x06028014) if server_id differs
- Sets g_state[0x01B0] flag for "already connected"
- **DOES NOT** call SV_Init, init_zone_transition, or modify SV session/connection state
- SV TCP connection PERSISTS through this path

## All Writers of g_state[0x01AD] (COMPLETE)
| Value | Function | File Offset | Condition |
|-------|----------|-------------|-----------|
| 0 | init_zone_transition | 0x000646 | Always |
| 0 | game_world_sm teardown | 0x02B558 | state==3 |
| 0 | gate/login_sm teardown | 0x02B72C | state==2 |
| **3** | game_world_sm PASS | 0x02B6A0 | DDFE==1 |
| **2** | gate/login_sm PASS | 0x02B874 | **E8C2==1** |

## How g_state[0x01AD] Reaches 2 (LOGIN)
The ONLY way: gate function (0x0603B6F0) with arg!=0, PASS path checks session_ctx[0xE8C2]==1.
- If E8C2==1 → writes g_state[0x01AD]=2, calls func_B(6,1)→gate_set(1)
- If E8C2==0 → FAIL, calls func_B(3,1), state stays 0

### How E8C2 Gets Set to 1
1. **BRAM load**: init_zone_transition → gate_set(0) clears to 0 → backup_ram_load overwrites from saved BRAM
   - If BRAM has saved E8C2=1 from previous session → E8C2=1 immediately
   - If no BRAM (fresh Saturn) → E8C2 stays 0
2. **gate_set(1)**: called via func_B(6,1) from game_world_sm PASS or gate PASS
3. **STILL UNKNOWN**: For fresh Saturn with no BRAM, how does E8C2 first get set to 1?
   - Boot code at file 0x00003E needs investigation
   - ESP_NOTICE handler might set it
   - Connection SM states 5-7 might set it

## CRITICAL: Why Test 13 (0x02EF) May Have Failed
Test 13 sent 0x02EF after GOTOLIST but got "dead silence." Possible causes:
1. Event data format wrong — must be [event_type:u8=0, dest_index:u8=0, byte2:u8, byte3:u8]
2. g_state[0x01B4] was already non-NULL (blocking dispatch)
3. Event dispatch not running (session_ctx[0xABAB]==0?)
4. Wrong timing — sent before client was ready to process

## Corrected GOTOLIST Server Flow (THEORY)
1. Client sends GOTOLIST_NOTICE (0x019C)
2. Server sends INFORMATION_NOTICE (0x019D) — paired response
3. Server sends EXEC_EVENT_NOTICE (0x02EF) with [0x00, 0x00, 0x00, 0x00]
4. Client queues event → dispatch → zone transition handler → same-server path
5. func_B(0,1) → CD init → init_zone_transition → SV_Init → connection RESET
6. Server waits ~500ms for client reset
7. Server sends new establishment IV frame
8. Client re-establishes, connection SM sends INIT (0x0035)
9. Server sends ESP_NOTICE + UPDATE_CHARDATA_REQ
10. Login flow restarts (BRAM provides E8C2=1 for gate PASS → state=2)

## Event Handler Table (0x06056F98, 11 entries)
| Index | Handler | Purpose |
|-------|---------|---------|
| 0 | 0x0601AD7C | Zone transition (GOTOLIST) |
| 1 | 0x0601AFC4 | Unknown |
| 2 | 0x0601B0F8 | Unknown |
| 3-10 | various | Unknown |

## Event Dispatch (0x06024864)
- If g_state[0x01B4] non-NULL → returns (already processing)
- If NULL: checks session_ctx[0xABA4] vs [0xABA5]
- If queue non-empty: reads event_type, validates <11
- Sets g_state[0x01B4] = handler_table[event_type]
- Does NOT call handler — main loop Phase 4 calls it

## Key Addresses Quick Reference
| Address | Description |
|---------|-------------|
| 0x0605F420 | g_state[0x01B4] — event handler fptr |
| 0x0605F419 | g_state[0x01AD] — game state (0/2/3) |
| 0x0605F429 | g_state[0x01BD] — SV_Poll enable |
| 0x0601AE98 | Reconnection callback function |
| 0x0601AD7C | Zone transition handler (event type 0) |
| 0x0601B94E | finish_zone_transition (cleanup) |
| 0x06024864 | Event dispatch function |
| 0x06018932 | 0x02EF handler (event enqueue) |
| 0x06018A78 | 0x02F0 handler (different!) |
