---
name: Complete Dragon's Dream game flow — start to tavern
description: Definitive answer to "where am I supposed to be at each point?". Maps the full architecture from offline HOME state through online tavern, with binary evidence at each step.
type: project
---

# Dragon's Dream — Complete Expected Flow (start of game → tavern)

User's questions answered (2026-05-05 session):
- **Q: "Am I supposed to be in the tavern yet?"** — YES. The flow goes HOME → dial → MAP/GOTOLIST → pick zone → that zone's TAVERN.
- **Q: "Is the TO TOWN → map transition correct?"** — YES. The "map" IS the GOTOLIST destination-selection screen. That's the intended UI for picking where to go.
- **Q: "Has some prerequisite not been satisfied?"** — NO for the tavern entry. The actual blocker is what happens when you click TEMPLE inside the tavern (it triggers a broken 2nd zone transition).

## The 7 phases — what the player sees vs. what the protocol does

### Phase 1: HOME (offline boot screen)

The Saturn boots the disc. Game shows "your home" — a single-screen offline UI with one prominent button labeled **"TO TOWN"**. Pressing it triggers modem dial.

**Protocol**: nothing — this is purely offline rendering by the game binary.

### Phase 2: DIAL & BBS handshake

Pressing TO TOWN initiates Hayes-AT modem dialing. Once the modem connects, the game sends BBS commands through the script engine at file `0x010128`:

```
Client → Server:  " P\r"            (login prompt)
Server → Client:  "*\r\n"
Client → Server:  "SET ...\r"       (configure)
Server → Client:  "*\r\n"
Client → Server:  "C NETRPG\r"      (connect to network RPG service)
Server → Client:  "COM\r\n"
```

After `COM\r\n`, the game enters **post-BBS state 3** — calls `SV_Setup` which sets the connection state to **1 (CONNECTING)**. From here all traffic is IV-framed (no more raw bytes).

**Game state**: `g_state[0x01AD]` is still 0 (no game world loaded).

### Phase 3: Session establishment + LOGIN STATE

Server sends a 256-byte session establishment IV frame with ESTABLISH flag (0x0008). Client's delivery function at `0x060423C8` sets connection state to **2 (CONNECTED)**.

Client immediately sends **`0x0035` (INIT)**. Server responds with two messages:
- **`0x01E8` ESP_NOTICE** (sets init flags `ctx[0x8E-0x91]=1` for deferred auto-sends)
- **`0x019F` UPDATE_CHARDATA_REQ** (asks client for character data)

The screen now shows a **login prompt** (real game shows character select screen). Client's `g_state[0x01AD] = 2` (LOGIN state).

User presses a button to confirm login → client sends **`0x019E` (LOGIN_REQUEST)** with character credentials.

Server responds with the full character-data cascade:
- `0x019F` (UPDATE_CHARDATA_REQ — second time, paired with 0x01AA reply)
- `0x01AA` (paired with client's 0x01AA send — but this is from server to client per memory)
- `0x02F9` CHARDATA_REQUEST (172-byte extended form with 19 base_stats + 19 current_stats + appearance + skill_levels)
- `0x02D2` CHARDATA_REPLY type 1 (char_list)
- `0x02D2` CHARDATA_REPLY type 2 (char_detail) ← **TRIGGERS BRAM SAVE on client**
- `0x02D2` CHARDATA_REPLY type 3 (inventory)
- `0x019D` (login complete acknowledgment)

After this cascade, the gate function (`0x0603B6F0`) advances `g_state[0x01AD]` from `2` to `3` (**GAME WORLD**), gated on `session_ctx[0xE8C2] == 1` (the BRAM-driven persistence flag).

### Phase 4: GOTOLIST / "the MAP screen"

In GAME WORLD state with no active zone, the client auto-sends **`0x019A` (LOGOUT/destination request)**. The "logout" name is misleading — this message also serves as "request available destinations from server".

Server replies with **`0x019B` GOTOLIST**: a destination list with up to ~7 entries, each containing dest_id, zone_id, map_id, map_x/y, server_info, and a 16-byte name (Shift-JIS).

**This is the "map" the user sees.** It is rendered by the GOTOLIST state machine at file `0x00DFB0` — it's a list/menu UI styled to look like a world map (icons positioned by `map_x` = VDP2 character selector). It is NOT the actual game world map.

User picks a destination → client sends **`0x019C` (GOTOLIST_NOTICE)** with the chosen `dest_id`.

### Phase 5: Zone transition (cycle 1)

Server's response to `0x019C`:
1. **`0x019D`** (paired ack)
2. **`0x02EF` (EXEC_EVENT_NOTICE)** with `dest_index=4` — this triggers `init_zone_transition` at `0x06010554`, which performs SV_Init (resets the SV layer)
3. **256-byte session establishment** (re-establishes session after SV_Init)
4. **`0x01E8` ESP_NOTICE** (re-arms init flags after the transition)
5. **`0x019F` UPDATE_CHARDATA_REQ**

Client's `init_zone_transition` does a 31-step reset, including loading the new zone's CD data. After re-establishment, `game_world_sm` re-enters with the new zone loaded.

**Cycle 1 works reliably** when `dest_index=4` (Cave Dungeon's table entry). Other dest_index values fail.

### Phase 6: Zone tavern entry (the user's "tavern")

Once in the loaded zone, the client immediately enters that zone's **tavern**. Tavern is the social-hub area of every zone — where players coordinate online play.

Client sends **`0x026F` (STORE_LIST)** — request to enter the tavern's store. Server replies **`0x0270`** (8-byte empty header).

Client then sends **`0x0271`** (16 bytes, mostly zero — automated handshake). Server replies **`0x0272`**:
- 1st time per session: `status=1` (REJECT, 2 bytes) — this REJECTION is intentional. It triggers the client to send `0x019A` again, which in turn shows the tavern's GOTOLIST sub-menu.
- 2nd+ time: `status=0` + `store_flag=0` (3 bytes) — accept, enter field/dungeon mode.

After the rejection cascade, the client renders the **3D tavern interior** — bar, bottles, beams, plus an **icon-based menu** with these buttons (per screenshots from real game):

| Tavern button | Japanese | Sends what? |
|---|---|---|
| **TABLE SEL** (テーブル選択) | "Table selection" | `0x01F8` (request table list) |
| **TEMPLE** (神殿) | "Shrine/temple" | `0x019C` (zone transition request to Temple) |
| **LEAVE** (退出) | "Leave" | `0x01FA` (SAKAYA_EXIT) |
| **Find Friends** (仲間を探す) | "Look for companions" | `0x024E` or `0x01B7` |
| **System Menu** (システムメニュー) | Settings / time / quit | local only (no SCMD) |

**This is where the user's "Temple" click happens.** Clicking Temple sends `0x019C` to attempt a **2nd zone transition** to the Temple zone — and this is where the documented cycle-2 freeze hits.

### Phase 7: Tavern interactions

From the tavern menu the player can:

- **Sit at a table** → `0x020E` SIT_REQUEST → server → `0x020F` SIT_REPLY + `0x0247` (table name push) + `0x024D` (member list refresh) — verified working architecture per `tavern-flow.md`.
- **Click TEMPLE** → `0x019C` zone transition → **BROKEN** (cycle 2 freeze, ~50 tests, no known fix)
- **Click LEAVE** → `0x01FA` → server → `0x01FB` (8 bytes) → exit tavern, enter actual zone (dungeon/field).
- **Find Friends** → search for online players.

## So... where IS the user supposed to be?

**Right now (per dd_server_20260505_130249.log)**: the user successfully reached the **tavern of Cave Dungeon** and clicked **TEMPLE**. That click triggered the documented broken 2nd-zone-transition.

**Their PROGRESS through the flow**:
- ✅ Phase 1-2 (HOME → dial → BBS): working
- ✅ Phase 3 (LOGIN): working
- ✅ Phase 4 (GOTOLIST/map): working — they correctly see the map
- ✅ Phase 5 (cycle 1 zone transition to Cave Dungeon): working
- ✅ Phase 6 (tavern entry, see 4-button menu): working
- ❌ Phase 7 — Temple click → 2nd zone transition: **BROKEN**

**The architecture is correct. The user IS where they're supposed to be. The bug is in Phase 7.**

## What to do next — given this map

Per `gotolist-flow.md` Test 50: the architectural fix is to send `0x019B` with **VARIED server_info** so that exactly ONE entry's server_info matches `zone_cd_id` (4 from cycle 1's dest_index=4). The matching entry triggers `0x026F` (game world re-entry, no transition) when clicked. Non-matching entries trigger `0x019C` (the broken transition).

**Currently `handlers_login.py` line 236** uses `si = dest_zid & 0xFF` (NATURAL — matches 200832 success log). For cycle 2+, **post-tavern**, we need different behavior:

The Temple zone is `dest_id=5` in the production game. To make Temple-click work, the Temple entry's `server_info` should be **4** (match zone_cd_id=4) so the client sends `0x026F` instead of `0x019C`. Other entries should keep natural server_info.

**This was tested as Test 50** (file `handlers_login.py` lines 184-189):
- Test 49 si=[4,4,4]: post-tavern HANG
- Test 52 si=[1,3,4]: post-tavern HANG
- Test 53 si=[4,3,4]: post-tavern HANG
- Test 50 (VARIED — Temple=4, Cave=1, others=natural): unknown outcome (not documented as confirmed pass)

The test history is somewhat ambiguous. The "VARIED" approach should logically work — but every variant tested either froze cycle 2 or hung post-tavern. This pattern strongly suggests **the bug is downstream**, not in server_info choice — possibly in the BRAM character data (we saw "12345" placeholder in the SYS BUP this session) or in the zone definitions.

## Where Ghidra (without MCP) helps now

For the server_info architecture question, the binary evidence is in:
- `0x0601AD7C` — handler[0] same-server zone transition
- `0x0601AFC4` — handler[1] cross-server zone transition
- The choice between these is driven by `server_info` byte at GOTOLIST entry offset 10

These functions live at the addresses but we have no decompiled source for them in `bulk/`. Manual disassembly would tell us exactly what state the same-server vs. cross-server paths leave the client in.

## Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: HOME (offline)                                          │
│  ─ Saturn boot, single-screen UI                                  │
│  ─ Player presses "TO TOWN" button                               │
└──────────────────────────────────────────────────────────────────┘
                              │  modem dial
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: BBS handshake                                           │
│  ─ " P" "*" "SET" "*" "C NETRPG" "COM" exchanges                 │
│  ─ SV_Setup → connection state = CONNECTING (1)                  │
└──────────────────────────────────────────────────────────────────┘
                              │  256B establishment frame
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: LOGIN (g_state[0x01AD]=2)                               │
│  ─ Client INIT (0x0035) → Server ESP+UPDATE                       │
│  ─ User confirms login → 0x019E LOGIN_REQUEST                    │
│  ─ Server: 0x019F + 0x01AA + 0x02F9 + 0x02D2(×3) + 0x019D         │
│  ─ Gate check (E8C2==1) → g_state[0x01AD] = 3 (GAME WORLD)       │
└──────────────────────────────────────────────────────────────────┘
                              │  client auto-sends 0x019A
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: MAP / GOTOLIST                                          │
│  ─ Server sends 0x019B with destinations                          │
│  ─ Player picks one → 0x019C dest_id                             │
│  ─ This is the "map" the user sees — destination chooser         │
└──────────────────────────────────────────────────────────────────┘
                              │  (cycle 1 zone transition)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 5: Zone transition                                         │
│  ─ Server: 0x019D + 0x02EF(dest_index=4) + 256B establish        │
│  ─ Client: SV_Init, init_zone_transition, CD load                │
│  ─ Server: 0x01E8 ESP + 0x019F UPDATE                            │
│  ─ ✅ WORKS for cycle 1 with dest_index=4                         │
└──────────────────────────────────────────────────────────────────┘
                              │  client enters new zone's tavern
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 6: Zone tavern (the place user is now)                     │
│  ─ Client: 0x026F → 0x0270 → 0x0271 → 0x0272(reject)             │
│  ─ Tavern UI renders: TABLE / TEMPLE / LEAVE / FIND / SYSTEM      │
└──────────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        │           │           │              │
        ▼           ▼           ▼              ▼
   TABLE click  TEMPLE click  LEAVE click   FIND click
        │       (0x019C)         │              │
        ▼      (✗ BROKEN —       ▼              ▼
   0x020E SIT  cycle 2          0x01FA       0x024E
   ✅ WORKS    freeze)          → exit       → search
                                  zone
```
