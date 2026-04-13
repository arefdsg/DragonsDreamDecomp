# Event Handler Table (0x06056F98) — COMPLETE ANALYSIS

## Table Structure
- 11 entries × 4 bytes (function pointers) at file offset 0x046F98
- Dispatched by event_dispatch (0x06024864) when g_state[0x01B4]==NULL
- Event type from queue byte[0], validated < 11

## Complete Handler Table

| Idx | Address | File | Size | Purpose |
|-----|---------|------|------|---------|
| 0 | 0x0601AD7C | 0xAD7C | ~584B | Zone transition — CD load + SV reconnect |
| 1 | 0x0601AFC4 | 0xAFC4 | ~308B | Server reconnection — same/cross using g_state params |
| 2 | 0x0601B0F8 | 0xB0F8 | ~340B | Destination table connection — 32+ entries at 0x06053E50 |
| 3 | 0x0601B24C | 0xB24C | ~410B | Zone-transition connection mgr — session_ctx[0xA4] driven |
| 4 | 0x0601B3E6 | 0xB3E6 | ~30B | Event param remap (+200 to byte[1]) → handler 7 |
| 5 | 0x0601B404 | 0xB404 | ~4B | Trampoline → handler 8 |
| 6 | 0x0601B42C | 0xB42C | ~264B | Coordinate warp — 6B entry table, 15-bit packed |
| 7 | 0x0601B534 | 0xB534 | ~180B | Navigation setup — nav struct at session_ctx+0x6764 |
| 8 | 0x0601B5E8 | 0xB5E8 | ~28B | Navigation cancel — clear nav flags |
| 9 | 0x0601B604 | 0xB604 | ~4B | Direct → finish_zone_transition |
| 10 | 0x0601B608 | 0xB608 | ~10B | Call handler 8 + finish_zone_transition |

## Handler Categories

### Connection Handlers (0-3)
All use async per-frame callbacks installed at g_state[0x01B4].

**Handler 0 (zone transition)**: 3 paths based on dest_index lookup:
- R12!=0,R11!=0: cross-server → install reconnection callback
- R12!=0,R11==0: same-server → func_B(0,1) → CD → init_zone_transition
- R12==0: cleanup → finish_zone_transition

**Handler 1 (reconnection)**: Uses already-stored g_state[0x1B68-0x1B6B]:
- g_state[0x1B6B]==0xFF: dispatch_connection_by_state (helper at 0x0601B2B4)
- g_state[0x1B69]==0xFF: same-server → begin_connect_same_server
- else: cross-server → connect_with_server(0x1B68, 0x1B69, 0x1B6A)
- Continuation polls until complete, calls completion handler + finish

**Handler 2 (destination table)**: 2-phase state machine:
- Phase 0: lookup dest_table[idx] at 0x06053E50 → [zone,srv1,srv2,map]
  - Stores to g_state[0x1B68-0x1B6A], initiates connection
- Phase 1: polls connection, calls completion_handler(map_index)
  - Sets g_state[0x1B6B] = map_index on success
- Uses GBR[9] status byte as readiness gate

**Handler 3 (zone-transition connection)**: 4 sub-functions:
- Entry (0x0601B24C): save g_state[0x01BD], disable SV_Poll, install callback
- Callback (0x0601B266): state 0=initiate, state 1=poll
- Initiate (0x0601B2B4): switch on session_ctx[0xA4]:
  - Type 9: same-server reconnect (begin_connect_same_server, param=16)
  - Type 6, 0x8B==1: same physical server (param=40)
  - Type 6, 0x8B!=1: cross-server, decode session_ctx[0xAB0D] nibbles
    → lookup server tables at 0x06053C9C/0x06053CA4
- Poll (0x0601B316): switch on session_ctx[0xA4]:
  - Type 9: wait_connect, completion_handler(0x0097)
  - Type 6 same: wait_connect, completion_handler(0x0095)
  - Type 6 cross: poll_cross, completion_handler(table[upper_nibble])
  - On success: sets g_state[0x1B68-0x1B6B]=0xFF

### Navigation Handlers (6-8)

**Handler 6 (coordinate warp)**:
- Copies slot data from table at 0x0604CBA4 (6B/entry)
- Gets dest_index from event queue → selects entry → extracts [x,y,z] (u16 each)
- Sends zone command (0x06026AE4) with coordinates
- Packs 15-bit: (z & 0x1F)<<10 | (y & 0x1F)<<5 | (x & 0x1F)
- Submits event with mask 0x25E7FFFE
- Installs 2-frame countdown callback → sends clear command → finish

**Handler 7 (navigation setup)**:
- Inits nav struct via 0x0602A948
- Sets session_ctx[0xAB17]=1 (navigation active)
- Populates nav_entry at session_ctx+0x6764:
  - [0:4] = packed dest word, [22] = dest_index
  - [0x052A-0x052D] = flags, copies from [0xABA6-0xABA7]
  - Zeroes [36-43], sets [36]=1, [44]=0,[45]=0,[46]=1,[47]=1
- Calls 4 init functions: 0x0601333E, 0x0602A886, 0x0607071E, 0x06021214
- Tail-calls finish_zone_transition

**Handler 8 (navigation cancel)**: Leaf function, 28 bytes
- nav_entry[0x052A] = 0, nav_entry[22] = 0
- nav_entry[0:4] = 0xFFFFFFFF
- session_ctx[0xAB17] = 0
- Tail-calls finish_zone_transition

### Utility Handlers (4-5, 9-10)
- Handler 4: event_queue[consume_idx].byte[1] += 200, then BRA handler 7
- Handler 5: BRA handler 8
- Handler 9: Load session_ctx, BRA finish_zone_transition
- Handler 10: STS PR; BSR handler_8; BRA finish_zone_transition; LDS PR

## Key Data Tables
| Address | Name | Format |
|---------|------|--------|
| 0x06053E50 | Destination table | 32+ × 4B: [zone,srv1,srv2,map] |
| 0x06053CAD | Server check table | parallel to dest table, 0xFF=same-server |
| 0x06053C9C | Server param lo table | 16 entries, indexed by lower nibble |
| 0x06053CA4 | Server param hi table | 16 entries, indexed by upper nibble |
| 0x06053EE0 | Completion code table | longs, indexed by upper nibble of 0xAB0D |
| 0x0604CBA4 | Coordinate slot data | 6B/entry for coordinate warp |

## Shared State
- g_state[0x01B4] (0x0605F420): per-frame callback pointer
- g_state[0x01BD] (0x0605F429): SV_Poll enable flag (saved/restored by handlers 1,3)
- g_state[0x1B68-0x1B6B]: connection params (zone, srv1, srv2, dest_status)
- session_ctx[0xABA5]: event queue consume index
- session_ctx[0xAB24]: event queue base
- session_ctx[0xAB17]: navigation active flag
- session_ctx+0x6764: navigation entry struct (48+ bytes)
- event_state struct at 0x060610C8: [0x0C]=countdown, [0x0E]=saved_flag, [0x10]=dest_idx, [0x11]=phase
