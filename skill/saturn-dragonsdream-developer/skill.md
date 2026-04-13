# Dragon's Dream Revival Server Developer Skill

Expert in the Dragon's Dream (1997 Sega Saturn MMORPG by Fujitsu/SEGA) revival server project. Activates when the user asks about Dragon's Dream protocol, server implementation, GOTOLIST flow, login state machine, session protocol, SV framing, SCMD messages, or any aspect of the Dragon's Dream reverse engineering and server development.

## Core Principles

1. **Evidence-driven only**: Every protocol detail, handler behavior, and message format must be traced to the decompiled binary (extracted/0.BIN, 504,120 bytes, base=0x06010000) or confirmed by hardware testing logs.
2. **No guessing**: Never invent message formats, handler behaviors, or protocol sequences without binary evidence.
3. **Big-endian**: All Saturn network data is big-endian (`struct.pack('>I', ...)`).
4. **AI-RECONSTRUCTED tags**: All inferred game logic (combat math, drop rates, etc.) MUST be tagged with `# AI-RECONSTRUCTED: [Reasoning & Evidence]`.

## MANDATORY: Data-Driven Implementation Methodology (Added 2026-04-10)

**BEFORE implementing ANY handler or game flow, you MUST:**

1. **Find the handler in the dispatch table** at file 0x435D8 (8-byte entries: [msg_type:2][pad:2][handler:4]).
   DO NOT assume handler addresses from memory or previous analysis — VERIFY against the table.
2. **Disassemble the COMPLETE handler** from the verified address. Read ALL code paths, not just the first few instructions.
3. **Read the literal pool** after the function to identify ALL session_ctx offsets, helper functions, and constants.
4. **Document the full wire format** with exact byte offsets, types, and destinations.
5. **Trace the state machine** — what state does the handler put the client in? What does the client expect next?
6. **Only then implement** the server handler with the verified format.

**Anti-patterns to AVOID:**
- Claiming "100% confidence" without completing steps 1-6
- Using handler addresses from memory without verifying against the dispatch table
- Assuming message A does X because message B (at a nearby address) does X
- Implementing a fix based on partial disassembly (e.g., only the first 20 instructions)
- Guessing payload formats based on message names instead of binary evidence

**LESSON LEARNED (2026-04-10):** Five consecutive hardware test failures on tavern sit were caused by
disassembling the WRONG address (0x050D0 instead of 0x050A4 for 0x020F). The handler table at 0x435DC
is the ONLY authoritative source for handler→msg_type mappings.

## CRITICAL: Handler Dispatch Table (RE-CORRECTED 2026-04-10)
- **Location**: file 0x435D8, 197 entries, 8 bytes each: **[msg_type:2][pad:2][handler:4]**
- Previous format [handler:4][msg_type:2][pad:2] at 0x435DC was WRONG — shifted all mappings!
- **0x020F** → 0x060150D0 (file 0x050D0) — SIT REPLY: reads status, if 0: strcpy(ctx+0x74EC, ctx+0x7515)
- **0x021B** → 0x060150A4 (file 0x050A4) — actual NO-OP (was wrongly assumed to be 0x020F)
- **0x024C** → 0x06015112 (file 0x05112) — MEMBER DELTA update (checks status, NO clear)
- **0x024D** → 0x06015152 (file 0x05152) — MEMBER FULL REFRESH (clears 8 slots, ALWAYS processes)
- **0x024F** → 0x06015290 (file 0x05290) — FIND RESULT only (8B max, NO member processing!)
- **0x0247** → 0x0601533C (file 0x0533C) — memmove(ctx+0x74EC, payload+16, 40) UNCONDITIONAL

## Project Structure

- **Binary**: `extracted/0.BIN` (SH-2 big-endian, base=0x06010000)
- **Server v4**: `server/dragons_dream_server_v4/` (22 Python modules)
- **Engineering Manual**: `docs/Dragons_Dream_Engineering_Manual.md`
- **Analysis docs**: `memory/` (22 markdown files — wire format, handlers, flows)
- **Tools**: `tools/` (SH-2 disassembler, decoder)
- **Memory files**: `C:\Users\gary\.claude\projects\D--DragonsDreamDecomp\memory\`
- **Skill references**: `C:\Users\gary\.claude\skills\saturn-dragonsdream-developer\references\`
- **GitHub**: `https://github.com/likeagfeld/DragonsDreamDecomp` (branch: `revival-server-v4`)

## Protocol Stack (5 Layers)

```
Layer 5: SCMD [2B param1][2B msg_type][4B payload_size][payload] — 310 types, 197 handlers
Layer 4: Session (0x00 server→client, 0xA6 client→server) — seq byte offsets, checksums
Layer 3: SV Framing (IV + 3hex size + 3hex complement + payload) — max 4095B
Layer 2: BBS Commands (" P\r"→"*\r\n", "C NETRPG\r"→"COM\r\n")
Layer 1: TCP/Modem (NetLink or DreamPi transparent bridge)
```

## Critical Rules

1. Server MUST NOT send raw non-IV bytes while CONNECTED (causes error dialog)
2. Sequence numbers are BYTE OFFSETS, not frame counters
3. msg_type is a unique identifier, NOT a wire size
4. Server sends first (256B session establishment) after BBS phase
5. Keepalives must be IV-wrapped session ACK frames
6. ESTABLISH flag at offset [8:10] = 0x0008 for session establishment

## Login Flow (Confirmed)

```
0x0035 (INIT) → ESP_NOTICE (0x01E8) + UPDATE_CHARDATA_REQ (0x019F)
→ wait for button → 0x019E (LOGIN_REQUEST)
→ 0x019F + 0x01AA + 0x02F9 + 0x02D2(types 1,2,3) + 0x019D
→ 0x019A (LOGOUT) → 0x019B (GOTOLIST_REQUEST with destinations)
→ B button or timeout → GAME WORLD ENTERED (0x026F STORE_LIST)
```

## Paired Wait Mechanism (DECODED 2026-04-13)

The paired wait is **cooperative, not blocking**:
1. `scmd_new_message` sets `ctx+6 = msg_type` (the expected reply type from the paired table)
2. `scmd_send` sets `ctx+14 = 3600` (60-second timeout in frames at 60fps)
3. After EVERY handler dispatch, the dispatch loop checks the paired message table (file 0x043484, 84 entries, [send:2][reply:2])
4. If the just-dispatched msg_type matches the expected reply in `ctx+6`, it clears `ctx+6` (wait satisfied)
5. If `ctx+14` decrements to 0 before the reply arrives → disconnect

This means the server MUST reply to paired messages within 60 seconds or the client disconnects.

## Tavern Sit Flow (CORRECTED 2026-04-10)

**Confirmed handler chain for sitting at a tavern table:**
1. Client sends **0x020E** (SIT_REQUEST) with table_id
2. Server replies **0x020F** (SIT_REPLY) — handler at file 0x050D0:
   - Reads status byte at payload+8
   - If status == 0 (success): `strcpy(ctx+0x74EC, ctx+0x7515)` — blanks the player's displayed name slot
   - This STRCPY blanking is critical: it signals the client to transition to seated state
3. Server pushes **0x024D** (MEMBER_FULL_REFRESH) — clears 8 member slots, populates table occupants
4. Server pushes **0x0247** — `memmove(ctx+0x74EC, payload+16, 40)` — writes seated player data

**Key discovery**: The STRCPY blanking in 0x020F is what triggers the client state transition. Without it (wrong status byte), the client stays standing.

## GOTOLIST Flow (CORRECTED 2026-04-06)

**CRITICAL FINDING**: Zone transition via 0x02EF ALWAYS corrupts client session state on cycle 2+. The `_zone_transition_done` flag prevents the second init_zone_transition from completing.

**Working approach**: Send ONLY 0x019D (paired ack) when receiving 0x019C (destination selection). No 0x02EF, no zone transition, no SV_Init. Client enters game world via GOTOLIST:
- B button press = cancel, enters current zone
- C button on matching entry = enters game world
- ~42.6s timeout = auto-enters current zone

GOTOLIST is rendered as a **list/menu, NOT a world map**. Entry format: [8..9] HIGH=VDP2 char selector, LOW=display param, map_x=0 → visible icon.

## Key RAM Addresses

| Address | Name | Description |
|---------|------|-------------|
| 0x06062374 | Connection state | 0=disconnected, 1=connecting, 2=connected |
| 0x202E4B3C | SV context | SV library state (cache-through) |
| 0x06062314 | SV session | Session struct |
| 0x0605F26C | g_state | Game state struct (GBR[1]) |
| 0x202CB000 | session_ctx | Session/network context (GBR[2]) |
| 0x06060EBC | GBR | Global base register |

## Reference Files

**Bundled with this skill** (in `references/` subdirectory):
- `tavern-flow.md` — Complete tavern handler map, wire formats, sit flow (CORRECTED 2026-04-10)
- `wire-format.md` — Wire format proof with evidence
- `handler-payloads-detailed.md` — ALL 197 server→client payloads
- `client-sent-payloads.md` — ALL 104 client→server payloads
- `paired-messages.md` — 84-entry paired message table
- `game-flow.md` — Complete post-login game flow (battle, shop, skill, movement)
- `connection-state-machine.md` — Connection SM states 0-8
- `sv-framing.md` — SV library analysis (send + receive state machines)

**Additional analysis** (in project memory directory):
- `handler-analysis.md` — 197 handler entries and dispatch
- `message-flow.md` — 108-entry paired message table + login flow
- `gotolist-flow.md` — Complete GOTOLIST test history (36+ tests)
- `gotolist-complete-analysis.md` — GOTOLIST binary analysis
- `event-handler-table-complete.md` — ALL 11 event handlers
- `init-zone-transition.md` — 31-step reset sequence
- `esp-notice-handler.md` — ESP_NOTICE payload and init flags
- `backup-ram-load.md` — BRAM load: 3 files, defaults

## 5-Phase Master Plan

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Protocol Mapping | **COMPLETE** |
| 2 | Database & World State | **COMPLETE** |
| 3 | Multi-Client Routing | **COMPLETE** |
| 4 | Authoritative Logic | **COMPLETE** |
| 5 | Integration & Testing | **IN PROGRESS** — Login+tavern entry confirmed on HW. Tavern sit fix pending HW test |
