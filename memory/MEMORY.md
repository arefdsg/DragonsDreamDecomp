# Dragon's Dream Decomp Project Memory

## Project Overview
- **Game**: Dragon's Dream — Fujitsu x SEGA Saturn MMORPG (Dec 1997, Japan)
- **Product**: GS-7114, V1.003, released 1997-10-27, Japan-only
- **Goal**: Revival server restoring online functionality
- **Status**: Server v4 — login+tavern entry confirmed on HW. Tavern sit **STILL FREEZES** but **gate byte pinpointed 2026-04-29**: `*0x06067D58` must be 0 for state 0 of FUN_06036B6C to advance. **DD uses SBL 2.11**, NOT custom (prior FID conclusion was wrong). See [sit-freeze-2026-04-29-breakthrough.md](sit-freeze-2026-04-29-breakthrough.md) for the actual freeze location, SBL evidence, and 1097 SBL function names extracted. Also: [sit-freeze-2026-04-22-session.md](sit-freeze-2026-04-22-session.md) (what's been ruled out — DO NOT repeat), [sit-freeze-data-driven-conclusions.md](sit-freeze-data-driven-conclusions.md) (input gate analysis — superseded by breakthrough findings).

## CRITICAL: Handler Dispatch Table (CORRECTED 2026-04-10)
- **Location**: file 0x435D8, 197 entries, 8 bytes each: **[msg_type:2][pad:2][handler:4]**
- **NOT** [handler:4][msg_type:2][pad:2] — previous format was WRONG, caused all handler mappings to be shifted
- Tavern handlers (key corrections):
  - **0x020F** → 0x060150D0 (file 0x050D0) — SIT REPLY: reads status, if 0: strcpy(ctx+0x74EC, ctx+0x7515)
  - **0x021B** → 0x060150A4 (file 0x050A4) — NO-OP (was incorrectly assumed to be 0x020F)
  - **0x024C** → 0x06015112 (file 0x05112) — MEMBER DELTA UPDATE (paired reply for 0x024B)
  - **0x024D** → 0x06015152 (file 0x05152) — MEMBER FULL REFRESH (server push, clears 8 slots)
  - **0x024F** → 0x06015290 (file 0x05290) — FIND RESULT only (8B, NO member processing!)
  - **0x0247** → 0x0601533C (file 0x0533C) — memmove(ctx+0x74EC, payload+16, 40)
- See [tavern-flow.md](tavern-flow.md) for complete handler map and sit flow
- **Paired message table**: file 0x043484, 84 entries, [send:2][reply:2]. See [paired-messages.md](paired-messages.md)
- **Paired wait mechanism** (DECODED 2026-04-13): cooperative, not blocking. scmd_new_message sets ctx+6=msg_type, scmd_send sets ctx+14=3600 (60s timeout). Dispatch checks paired table after EVERY handler — if match, clears ctx+6. Timeout at ctx+14==0 → disconnect. See [tavern-flow.md](tavern-flow.md)

## CRITICAL: Wire Format (CORRECTED 2026-03-11)
- See [wire-format.md](wire-format.md) for full analysis with evidence
- **8-byte header**: `[2B param1][2B msg_type][4B payload_size][payload_data]`
- **msg_type is NOT wire size** — it's just a unique message identifier (uint16 BE)
- **payload_size is the ACTUAL payload byte count** (uint32 BE)
- **Total wire size = 8 + payload_size** (NOT msg_type!)
- param1 usually 0, dispatch reads msg_type from buffer[2], handlers get buffer+8

## CRITICAL: SV Framing (CORRECTED 2026-03-11)
- **IV header = 8 bytes**: `IV` + 3 hex (size) + 3 hex (~size & 0xFFF)
- **NO \r\n** between header and payload (previous analysis was WRONG)
- **NO checksum** at SV layer — the second field is size COMPLEMENT
- **NO fragmentation** at SV layer — each message = one IV frame
- Hex encoding: lowercase `"0123456789abcdef"` (decode accepts both cases)
- Max IV payload: 4095 bytes (12-bit limit), practical: ~2000B
- Keepalive: `$I'm alive!!\r\n` is CLIENT→SERVER only (separate from IV)
- **CRITICAL**: Server MUST NOT send raw non-IV bytes while client is CONNECTED!
  SV_RecvFrame state 0 at 0x0602272E: any non-'I' byte + CONNECTED → error_dialog(1)
  Server keepalive must be IV-wrapped session ACK frames (flags=0x01, copy_length=0)

## CRITICAL: SV State Machine (CORRECTED 2026-03-12, base=0x06010000)
- **SV library source**: `lib_sv.c` (from assertion strings)
- **SV_Init** at file 0x01219E: clears SV context at 0x202E4B3C
- **SV_Setup** at file 0x0121F8: registers callbacks, inits session, sets [0x202E4B3C]=1
- **SV_Poll** at file 0x0120E8: called from MAIN LOOP (0x000156), calls sv_open + SV_RecvFrame
- **sv_open** at file 0x01253E: send state machine (builds IV header, sends byte-by-byte)
- **SV_RecvFrame** at file 0x0126DA: 3-state receive parser (scan 'I'→'V'+hex→payload)
- **Send queue**: at 0x060623D8, sv_open sends when queue non-empty
- **SV context struct**: at RAM 0x202E4B3C (Work RAM-L, cache-through)
- **SV session struct**: at RAM 0x06062314
- **Connection state [0x06062374]**: offset 0x60 in session struct
  - 0 = Disconnected (set by init/teardown at 0x06041BDE, 0x06041CFC)
  - 1 = Connecting (set by 0x06041D94, called from SV_Setup)
  - 2 = Connected (set by delivery function 0x060423C8 at 0x060428CE)
- **Polling function** at 0x012298: returns 1 if [0x06062374]==2, else 0

## CRITICAL: Session Protocol Layer (CORRECTED 2026-03-12)
- **ALL post-BBS messages** go through session framing (between SV IV and SCMD)
- **Protocol stack**: SCMD → Session Protocol (0x00/0xA6) → SV IV Framing → TCP
- **0x00-type DATA frame (server→client)**: [0]=0x00, [1]=**0x03**(bit0+bit1), [2:4]=checksum,
  [4:6]=zeroed, [6:8]=unused, [8:12]=seq_byte_offset(uint32 BE), [12:16]=ack(uint32 BE), [16:18]=copy_length, [18:20]=0, [20:]=SCMD
- **FLAGS byte [1]**: bit0=has_seq_data (MUST set for seq/ack fields), bit1=has_data, bit6=alt_data
- **Without bit0**: delivery function reads stale values from session context, frame silently dropped
- **CRITICAL: Sequence numbers are BYTE OFFSETS, not frame counters!**
  Evidence: client INIT(seq=0, 74B SCMD) → next client frame seq=74. After dispatch, session[116] = seq + copy_length.
  send_seq starts at 0, incremented by SCMD size (copy_length) after each frame.
- **[12:16] ack_num**: must be > session[112] (starts 0, updated after each accepted frame via cmp/hi)
  ack = send_seq + 1 (monotonically increasing byte offset + 1)
- **ESTABLISH sub-flags**: bit3=ESTABLISH only (0x0008). Do NOT set bit4 with window=0.
- **0xA6 frame (client→server)**: escape-encoded, [6]=escape_byte(0x1C),
  from [8]: 4 escaped bytes→seq, 4 escaped bytes→val2, skip 4 raw, then SCMD data
- **Escape decoding**: if byte==escape_byte, next_byte^0x60 = original
- **Checksum**: sum all bytes with [2:6] zeroed, & 0xFFFF
- Server 0x00: checksum at [2:4] as uint16 BE; Client 0xA6: checksum at [2:6] as 4 ASCII hex
- **send_msg() must wrap SCMD** in 0x00-type session DATA frame before IV encoding

## CRITICAL: Connection Protocol (CORRECTED 2026-03-12)
- **SERVER SENDS FIRST** — Saturn deadlocks without initial server frame
- BBS: ` P\r`→`*\r\n`, `SET...\r`→`*\r\n`, `C NETRPG\r`→`COM\r\n`
- After BBS: Saturn enters post-BBS state 3, calls SV_Setup → [0x06062374]=1
- SV_Poll starts running: SV_RecvFrame scans for 'I','V' header (send queue empty)
- Post-BBS state 3 polls [0x06062374]==2 with 600-frame (~10s) timeout
- **Server must send 256-byte session establishment IV frame** to trigger delivery
- Delivery function at 0x060423C8 sets [0x06062374]=2 (CONNECTED)
- State advances 3→4, Saturn sends 0xA6 session response (18B IV frame)
- **SV_RecvFrame resets to state 0 after EACH delivery** (all frames must be IV-wrapped!)
- **NO separate ack needed** — single establishment with ESTABLISH flag sets state=2
- Server responds with 0x01E8 ESP_NOTICE to 0x0035, login flow continues
- **Session frame format** (from delivery function at 0x060423C8):
  - [0]: 0x00=server→client, 0xA6=client→server (escape-encoded)
  - [1]: frame flags: bit0=has_seq_data, bit1=has_data, bit6=alt_data
  - [2:4]: **uint16 BE checksum** (NOT ASCII hex!), computed with [2:6] zeroed
  - [8:10]: **uint16 BE session flags, bit3=ESTABLISH (0x0008) REQUIRED for state=2**
- Establishment: [0]=0x00, [1]=0x42, [2:4]=cksum, [8:10]=0x0008, rest zeros
- Saturn response: [0]=0xA6, [1]=flags, [2:4]=cksum, [6]=0x1C(escape), [8:12]=timeout_a, [16:18]=timeout_b
- **0x0035 is NOT sent via scmd** — may be the 0xA6 session msg itself or SV-layer direct

## BBS Script Engine (file 0x010128, base=0x06010000)
- Script tables: 12-byte entries [type:4][data:4][param:4]
- Type 1: SEND string, Type 2: WAIT for response, Type 3: END
- MODEM_INIT table at 0x06055D3C (AT, ATZ, user config)
- BBS_LOGIN table at 0x06055DA8 (P, SET commands, wildcard match)
- BBS_CONNECT table at 0x06055DD8 (C HRPG, expects COM response)
- Response matching: substring scan on raw byte stream, NOT line-based

## SCMD Library Functions (confirmed addresses)
| Function | File offset | Mem addr | Description |
|----------|------------|----------|-------------|
| scmd_new_message | 0x149EC | 0x060249EC | Init msg with param1+msg_type |
| scmd_add_byte | 0x14A32 | 0x06024A32 | Add 1 byte |
| scmd_add_word | 0x14B04 | 0x06024B04 | Add 2 bytes (uint16 BE) |
| scmd_add_long | 0x14BDC | 0x06024BDC | Add 4 bytes (uint32 BE) |
| scmd_add_data | 0x14CD0 | 0x06024CD0 | Add N bytes from ptr |
| scmd_send | 0x14E3C | 0x06024E3C | Set payload_size, send |
- Buffer base: 0x202E6148, nMsgSize: 0x06062498, max: 4800B

## Binary Analysis Files
- [wire-format.md](wire-format.md) — wire format proof (CORRECTED)
- [sv-framing.md](sv-framing.md) — SV library analysis (CORRECTED)
- [handler-analysis.md](handler-analysis.md) — 197 handler entries and dispatch
- [handler-payloads-detailed.md](handler-payloads-detailed.md) — **ALL 197 server→client payloads**
- [client-sent-payloads.md](client-sent-payloads.md) — **ALL 104 client→server payloads**
- [message-flow.md](message-flow.md) — 108-entry paired message table + login flow
- [game-flow.md](game-flow.md) — **COMPLETE post-login game flow** (battle, shop, skill, movement)
- [protocol-details.md](protocol-details.md) — 310 message types (NOTE: "wire size" column is WRONG)
- [esp-notice-handler.md](esp-notice-handler.md) — ESP_NOTICE (0x01E8) handler: payload, state clears, init flags
- [connection-state-machine.md](connection-state-machine.md) — Connection SM states 0-8: modem, BBS, session, disconnect, reconnect
- [backup-ram-load.md](backup-ram-load.md) — BRAM load: 3 files, defaults, fresh Saturn gate bootstrap problem
- [gotolist-complete-analysis.md](gotolist-complete-analysis.md) — GOTOLIST: zone transition, event dispatch, 3 paths
- [init-zone-transition.md](init-zone-transition.md) — init_zone_transition: 31-step reset sequence
- [event-handler-table-complete.md](event-handler-table-complete.md) — **ALL 11 event handlers** fully decoded: connection, navigation, warp

## Decompilation Progress — COMPLETE
- **197 server→client handlers**: 24 empty (rts), 173 fully decompiled
- **104 client→server messages**: all payload layouts documented
- **SV framing**: fully decompiled (send + receive state machines)
- **Checksum**: additive byte sum at 0x060429B6 (application layer)
- See handler-payloads-detailed.md and client-sent-payloads.md

## Key File Locations
- `extracted/0.BIN` — Main executable (504,120 bytes), SH-2 big-endian, base=0x06010000
- `server/dragons_dream_server_v3.py` — Revival server v3 (current)
- `server/netlink.py` — DreamPi netlink module (with do_transparent())
- `server/config.ini` — DreamPi dial-code config (handler=transparent for DD)

## Login & Post-Login Flow (CONFIRMED 2026-03-13)
- **Login states 0-7** at 0x0603C100: ALL LOCAL, no SCMD. Parent sends 0x019E after.
- **Login flow**: 0x0035→ESP_NOTICE+UPDATE_CHARDATA_REQ (BOTH required!),
  then 0x019E→0x019F(REQUIRED!)→0x01AA→0x02F9+0x02D2(types 1,2,3)+0x019D
- **CHARDATA_REPLY (0x02D2)**: TYPE 1→char_list, TYPE 2→char_detail(triggers BRAM save), TYPE 3→inventory
- **Init flags (0x8E-0x91)**: deferred-send system, set by ESP_NOTICE AND init_zone_transition
- **Post-GOTOLIST** (see [gotolist-flow.md](gotolist-flow.md)): server_info must match zone_cd_id.
  Second zone transition breaks client → `_zone_transition_done` flag fix.
  Tavern: 0x026F→0x0270→0x0272→0x019A→0x019B→0x01F8→0x01F9 (MUST have entries!)
- **gate_set** (0x0603B488): writes to session_ctx[0xDDFE]+[0xE8C2]. BRAM load overwrites.
- **Connection SM** (file 0x0103C0): states 0-7, INIT sent once (bit 7 prevents re-send)
## GBR Pointer Table (CONFIRMED 2026-04-01)
- GBR = 0x06060EBC: [0]=0x06052530 (func ptrs), [1]=0x0605F26C (g_state), [2]=0x202CB000 (session ctx)

## Main Loop & Game World (CORRECTED 2026-04-03)
- See [init-zone-transition.md](init-zone-transition.md) and [game-flow.md](game-flow.md) for details
- Phases: transition_anim → SV_Poll → event_handler_fptr (Phase 4, SKIPS Phase 6) → g_state[0x01AD] dispatch (Phase 6) → event loop → VBlank
- game_world_sm (0x0603B51C): PATH 1(teardown), PATH 2(enter, checks session_ctx[0xDDFE]==1)
- gate function (0x0603B6F0): checks session_ctx[0xE8C2]==1
- init_zone_transition (0x06010554): full reset, sets init flags [0x8E-0x91]=1, gate_set(0)
- backup_ram_load (0x06010710): loads 3 BRAM files, OVERWRITES gate flags
- Task system (0x06028310): deferred tasks, vtable[6]=gate_set, vtable[15]=game_world_sm
- Reconnection (0x0601AE98): 2-state SM for zone transitions

## GOTOLIST (CORRECTED 2026-04-01)
- Entry[8..9] position: HIGH=VDP2 char selector, LOW=display param. map_x=0→visible icon.
- Rendered as list/menu, NOT world map. Gate never clears E8C2 → GOTOLIST cycle is normal.

## NetLink Hardware (CORRECTED 2026-03-18)
- LED: board control 0x25885031 bit 7. Bus strobe 0x2582503D after every access.
- UART base: 0x25895001. Modem detect: 0x05885029→0x11.
- See [bomberman-led-patch.md](bomberman-led-patch.md) for Bomberman US patch.

## Server v4 (COMPLETE 2026-03-31)
- See [server-v4.md](server-v4.md) for full architecture
- `server/dragons_dream_server_v4/` (22 Python files), launch: `python -m dragons_dream_server_v4 --port 8020`
- 108/108 paired handlers, SQLite persistence, combat engine, admin GUI
- 30 items, 20 monsters, 16 skills, 9 zones, 5 shops

## User Preferences
- 100% working implementation from binary analysis, no stubs/guesses
- Testing with real Saturn hardware via DreamPi on local network
