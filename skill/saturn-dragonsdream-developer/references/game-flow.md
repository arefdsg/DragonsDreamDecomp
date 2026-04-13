# Dragon's Dream — Complete Game Flow (Binary-Verified)

Last updated: 2026-04-08 (Test 50 — VARIED server_info fix for post-tavern GOTOLIST)

## Overview

All message formats verified against binary handlers at specific file offsets.
Client->server payloads from client-sent-payloads.md.
Server->client payloads from handler-payloads-detailed.md.

---

## 1. Login -> Game World Entry (CORRECTED 2026-04-08, Test 50)

```
Client 0x0035 (INIT)
  Server: ESP_NOTICE (0x01E8) + UPDATE_CHARDATA_REQ (0x019F)
  User presses button
  Client 0x019E (LOGIN_REQUEST)
  Server: 0x019F + 0x01AA + 0x02F9 + 0x02D2(types 1,2,3) + 0x019D
  Client 0x019A (LOGOUT) [gotolist_count=1]
  Server: 0x019B (GOTOLIST, server_info = zone's own ID per entry)
  Cycle 1: 0x019C (mismatch) -> 0x019D + 0x02EF(4) -> wait -> re-establish -> ESP+UPDATE
  Client resumes GOTOLIST (cached entries), click matching (Cave=4) -> 0x026F
  Server: 0x0270 -> Client 0x0271 -> Server 0x0272 (STORE_IN, status=1 = tavern)
  Client auto-sends 0x019A (tavern prefetch) [gotolist_count=2+]
  Server: 0x019B (VARIED server_info: Temple=4[MATCH], Cave=1, other=natural)
  GAME WORLD ENTERED (tavern interior visible)
  User clicks Temple -> server_info=4==zone_cd_id=4 -> 0x026F -> field mode!
```

**CRITICAL: ESP+UPDATE required after zone transition re-establishment.**
Client NEVER re-sends 0x0035 (connection SM bit 7 set permanently).
Evidence: Test 48 removed them -> black screen. Old success had them -> client resumed.

**CRITICAL: ALL-matching server_info causes CLIENT HANG in post-tavern context.**
Evidence:
- Test 49 (dd_server_20260408_165140.log): all [4,4,4] -> client froze instantly
- dd_server_20260408_062654.log: all [4,4,4] -> same freeze
- Old success (dd_server_20260405_200832.log): varied [4,3,5] -> client fine

**server_info rules (CORRECTED Test 50)**:
- Pre-tavern: natural server_info = zone_id. Cave(4) matches zone_cd_id=4.
- Post-tavern: VARIED. Temple(zone 5)=4 [MATCH], Cave(4)=1, others=natural.
  Exactly 1 out of 3 matching (same pattern as old success). No hang.

**0x0272 two modes**:
- 1st 0x026F: status=1 (reject, 2B) -> client sends 0x019A -> tavern.
- 2nd+ 0x026F: status=0 + store_flag=0 (3B) -> field/dungeon mode.

---

## 2. Tavern (Sakaya) Flow (UPDATED 2026-04-09)

```
TAVERN INTERIOR (3D bar scene with icon menu):
├── TABLE SEL (テーブル選択):
│   Client 0x01F8 (20B: 16B data + 2xU16)
│   → Server 0x01F9: 12B hdr + N×64B entries (3 tables: Temple/Dragon's Peak/Training)
│   → Tables show bot players (Hikaru/Ryuji/Sakura), flags=1 (occupied)
│   → User selects table with bot → Client 0x020E (6B: U32 target + U16 cmd)
│   → Server 0x020F: 4B (status=0, sit_param=0) — ACCEPT sit
│   → Server pushes 0x024D (44B): 8B hdr + 36B entry (NOT separate 0x024C+0x024D!)
│   → Entry: 16B name + 4×1B fields + 4B U32 + 8B sub-struct + 4B skip = 36B
│   → Client shows member list with bot player at table
│   → [PENDING: party formation → dungeon transition]
│
├── POST-TAVERN MAP (Cave entry → field mode):
│   After STORE_IN status=1, client gets GOTOLIST #3 (NATURAL values)
│   Cave(si=4) matches zone_cd_id=4 → 0x026F → store_count=2 → FIELD MODE
│   Forest/DT mismatch → 0x019C → zone transition (may hang on cycle 2+)
│
├── LEAVE (退出):
│   Client 0x01FA → Server 0x01FB: 8B (status=0, unknown=0, exit_context=0)
│
├── Find Friends:
│   Client 0x024E or 0x01B7 → Server 0x024F or 0x01B8 (search result)
│
└── System Menu:
    Local only (settings, time, quit game)
```

**Tavern handlers:**
- 0x01F8 → 0x01F9 (TBLLIST): 12B hdr + 3×64B entries, bot flags=1
- 0x020E → 0x020F (SAKAYA_SIT): 4B, status=0 ACCEPT (bot at table)
- 0x024B → 0x024D (MEMLIST): 8B hdr + 36B/entry (CORRECTED 2026-04-10)
- 0x0216 → 0x0217 (SAKAYA_IN): 4B, status=0
- 0x01FA → 0x01FB (SAKAYA_EXIT): 8B, status=0
- 0x0219 → 0x021A (SAKAYA_STAND): 4B, status=0

**CRITICAL**: Empty 0x01F9 (count=0) → garbage from uninitialized buffer.
**CRITICAL**: 0x024C member_count=0 → client HANGS (dd_server_20260407_185831.log).
**CORRECTED 2026-04-10**: 0x024D entry is 36 bytes, NOT 24. Previous 24B caused buffer overread.
  Verified by full SH-2 disassembly (capstone) of processor at 0x060151D2:
  0x06019FD2 = read_u32(4B), 0x06019FF6 = read_u16(2B), 0x0601A1EA returns input+8.
  0x0601A18E/0x0601A1BC = bit_decode(byte->position), no stream read.
**BINARY EVIDENCE**: 0x0603FEF0 = memset, 0x0603FE68 = memcpy (from correct file offsets).

### Fixes Applied (Test 43-45, 2026-04-07):
1. **SAKAYA_SIT reject**: 0x020F status=1 (2B), NO 0x024C push. Matches old success.
2. **GOTOLIST Dark Tower**: Zone 3 connections: [2, 4, 5] → GOTOLIST includes Dark Tower
3. **0x01F9 TBLLIST format WRONG (CRITICAL)**: Binary handler at 0x4EC6:
   - Header: entry_count at [4:6]. Entry: table_id(U32) at [0:4], flags at [4:6], data at [24:64].
4. **Table flags=0 (empty)**: Was flags=1 (occupied) → "table full". Now flags=0.
5. **Temple zone transition re-enabled**: Dark Tower server_info=5 (≠zone_cd_id=4) →
   client sends 0x019C → 0x02EF(5) → re-establish. Previous 23 failures had
   send_seq reset bug (now fixed) and wrong dest_index (6-7, now only 4-5).
6. **_zone_transition_done guard removed**: Allow multiple zone transitions.
   Track _zone_cd_id and _zone_transition_count for proper server_info matching.

---

## 3. Field Mode — Movement

```
Client 0x01C1 (MOVE, 1-3B: direction 1-4)
→ Server 0x01C4 (MOVE1_REQUEST, 16B):
  [0:2] status(U16), [6] new_x, [7] new_y, [8] direction, [10:12] move_value(U16)
  Binary: handler at 0x717A, stores at g_state+0x1E74..0x1E78

→ Broadcast 0x02F3 (MOVE2_NOTICE) to other players in zone:
  [0:4] count(U32) + N×8B: y(U8), x(U8), 2B skip, pos_packed(U16), dir(U8), anim(U8)
  Binary: handler at 0x729A, entity table at g_state+0x8708

Random encounter check after each step (server-authoritative).
```

---

## 4. Combat Flow (Binary-Verified, Fixed 2026-04-07)

### 4a. Encounter Initiation

```
Client 0x0243 (MONSTERWARN, 4B: U16 arg + U16 zero)
  OR server-initiated after movement step

→ Server 0x0244 (ENCOUNTMONSTER_REQUEST, 2B: U16 status=0)
  Handler 0x7A2A: reads U16 status

→ Server 0x01C9 (ENCOUNTMONSTER_REPLY, 10+N×32B):
  Header [0:10]: type0(U8), type1=count(U8), battle_id(U16), param(U16), field(U16), 2B
  Per entity [32B]: facing(U8), mode(U8), field36(U8), pad, x(U16), y(U16),
    name(16B), status(5B+3pad via read_5_skip_3)
  Handler 0x7A6C: battle_base=g_state+0x10340, entity stride=0xA4

→ Server 0x01CA (ENCOUNTMONSTER_NOTICE, 0B)
  Handler 0x7BEC: sets g_state[0xF4B9]=0 (clears encounter flag)

→ Server 0x021F (BATTLEMODE_NOTICE, 2+N×32B):
  [0:2] entity_count(U16)
  Per entity [32B]: is_player(U8), 3B pad, hp(U16), max_hp(U16),
    status(5B+3pad), name(16B)
  Handler 0x7BF8: entity array at g_state+0x10864, stride=0xA0
  *** CORRECTED: 32B per entity, not 30B. Layout: 1+3+2+2+8+16=32 ***
```

### 4b. Turn-Based Command Loop

```
Client 0x0221 (BTL_CMD, 12B: cmd_type(U8), target(U8), action_id(U16), extra(8B))
  cmd_type: 0=attack, 1=skill, 2=defend, 3=flee

→ Server 0x0222 (BTL_CMD_REQUEST, 2B: status=0 ack)
  Handler 0x7D88: reads U16, falls through to 0x0223

→ Server 0x0223 (BTL_CMD_REPLY, 24B) per action:
  [0:2] status(U16), [2] entity_index(U8), [3] action_byte_0, [4] action_byte_1(kill?),
  [5] action_flag, [6:8] damage(U16), [8:24] name/data(16B)
  Handler 0x7DCC: stores via 0x0601AA3E lookup

→ If battle continues:
  Server 0x0227 (BTL_RESULT_NOTICE, 44+N×56B):
  Header [0:44]: battle_id(U16), num_combatants(U16), ...fields..., result_bytes(5B)
  Per combatant [56B]: field_1(U16), field_2(U16), name(16B), exp(U32),
    4B skip, field_4(U8), field_5(U8), field_6(U16), attrs(7B), pad, stat_mods(8×U16)
  Handler 0x81B0
  → Loop back to waiting for next BTL_CMD

→ If flee (cmd_type=3) succeeds:
  Server 0x01E4 (CANCEL_ENCOUNT_REQUEST, 2B: status=0)
  Handler 0x86C8: clears 5 groups × 3 slots at g_state+0x4B58
```

### 4c. Battle End

```
(After final turn when all monsters dead or player dead):
→ Server 0x0227 (BTL_RESULT_NOTICE) — final state with rewards
→ Server 0x01C8 (BTL_GOLD_NOTICE, 12B hdr + groups):
  [0] result_flag_1(U8), [1] result_flag_2(U8), [2:4] gold_total(U16),
  [4:6] num_groups(U16), [6:12] reserved
  Per group [8B]: entity_id(U32), item_count(U16), action_type(U8), param(U8)
  Handler 0x83E4

→ Client 0x01EA (BTL_EFFECTEND_REPLY, 2B: always 0) — client done processing

→ Server 0x01EB (BTL_END_REQUEST, 2B: U16 status, 0=won 1=lost)
  Handler 0x8356

→ Server 0x02F4 (BTL_END_REPLY, 16B: position restore):
  [0:4] zone_id(U32), [4:6] x(U16), [6:8] y(U16), [8:16] status(5B+3pad)
  Handler 0x836E: restores party_entry position
  → RETURN TO FIELD MODE
```

### 4d. Additional Battle Messages

```
Client 0x0224 (BTL_CHGMODE, 2B) → Server 0x0225 (2B: status=0)
Client 0x0296 (BTL_ACTIONCOUNT, 2B) → Server 0x0297 (0B empty)
Client 0x01E3 (CANCEL_ENCOUNT, 0B) → Server 0x01E4 (2B: status=0)
Server 0x01C7 (BTLJOIN_NOTICE, 16B) — multi-player battle join
```

---

## 5. Camp Mode

```
Client 0x01DF (CAMP_IN, 2B) → Server 0x01E0 (SET_MOVEMODE, 2B: move_mode)
→ Camp menu (save, status, equipment, skills, items, party)
Client 0x01B3 (CAMP_OUT, 2B) → Server 0x01B4 (2B: status=0)
→ RETURN TO FIELD
```

---

## 6. Shop Flow

```
Client 0x01FE (SHOP_IN, 2B) → Server 0x01FF (SHOP_IN_REQUEST):
  [0:2] status(U16), [2:4] item_count(U16), [4:8] shop_param(U32),
  N×22B items: 16B data + 2B price + 2B type_a + 2B type_b
  Handler 0x5588: items at g_state+0x7948, 22B/entry, max 32

Client 0x0202 (SHOP_LIST, 2B) → Server 0x0203 (SHOP_LIST):
  Same structure. Handler 0x547A: items at g_state+0x6C94

Client 0x01F2 (SHOP_BUY, 4B: U16 arg1 + U16 arg2)
→ Server 0x01F3 (8B: status(U16), param(U16), gold_update(U32))
  Handler 0x57F6

Client 0x01F4 (SHOP_SELL, 4B) → Server 0x01F5 (8B: same format)
  Handler 0x5856

Client 0x0200 (SHOP_OUT, 2B) → Server 0x0201 (2B: status=0)
  Handler 0x58CC → RETURN TO FIELD
```

---

## 7. Skill & Level-Up Flow

```
SKILL LIST: Client 0x02B9 → Server 0x02BA (H status, H count, I param + skill entries)
LEARN: Client 0x02E0 → Server 0x02E1 (H status)
UPGRADE: Client 0x02E2 → Server 0x02E3 (H status)
EQUIP: Client 0x02E4 → Server 0x02E5 (H status)
UNEQUIP: Client 0x02E6 → Server 0x02E7 (H status)
USE SKILL: Client 0x02E8 → Server 0x02E9 (H status)

LEVEL UP CHECK: Client 0x0275 → Server 0x0276 (H status, I threshold)
LEVEL UP: Client 0x0277 → Server 0x0278 (H result, H skip, I threshold, 19×H stats) = 48B
CLASS LIST: Client 0x0298 → Server 0x0299 (H status)
CLASS CHANGE: Client 0x029A → Server 0x029B (H result, class_block, 8×H skills, 19×H stats) = 68B
```

---

## 8. V4 Handler Implementation Status

### Fully Implemented (binary-verified payloads):
- Login flow (handlers_login.py) — Tests 40-42 confirmed on hardware
- Movement (handlers_movement.py) — h_move, h_giveup, h_set_movemode
- Combat (handlers_combat.py) — encounter init, BTL_CMD, end sequence (**FIXED 2026-04-07**)
- Shop (handlers_shop.py) — all 6 handlers with DB operations
- Inventory (handlers_inventory.py) — equip, disarm, use_item with stat recalc
- Skills (handlers_skills.py) — all 6 handlers
- Leveling (handlers_leveling.py) — level-up, class change
- Social (handlers_social.py) — chat, mail, bulletin board, tavern
- Party (handlers_party.py) — party list, entry, join, unite

### Stubs (minimal ack only):
- h_btl_chgmode (0x0224→0x0225): 2B status=0
- h_btl_effectend (0x0296→0x0297): 0B
- h_map_change_notice (0x01AC→0x01AD): 2B status=0
- h_camp_out (0x01B3→0x01B4): 2B status=0
- h_setpos (0x01D3→0x01D4): 2B status=0
- h_give_item (0x0293→0x0294): 2B status=1 (reject)
- h_compound (0x02ED→0x02EE): 2B status=1 (reject)
- h_sell_item/h_buy_item/h_trade_cancel: P2P trading rejected
- h_class_list (0x0298→0x0299): 2B status=0

### Fixes Applied 2026-04-07:
1. **BATTLEMODE_NOTICE stride**: 30→32 bytes per entity (1+3+2+2+8+16=32)
2. **Added ENCOUNTMONSTER_NOTICE (0x01CA)**: 0B, sent between 0x01C9 and 0x021F
3. **Added BTL_GOLD_NOTICE (0x01C8)**: 12B hdr + 8B group, sent before BTL_END
4. **Added BTL_END_REPLY (0x02F4)**: 16B position restore, sent after BTL_END_REQUEST
5. **Fixed battle end sequence**: _end_battle sends 0x0227+0x01C8 only; h_btl_end sends 0x01EB+0x02F4 after client 0x01EA
6. **STORE_IN (0x0272) status=1**: Matches old success (dd_server_20260405_200832.log). Status=0 puts client in store mode (context+0xA0) which intermittently blocks 0x019A.
7. **REVERTED send_seq reset**: send_seq MUST be PRESERVED across re-establishment. Old success proves: 1201→1260, 1576→1635. Reset to 0 → garbage seq=3153728 (dd_server_20260407_172833.log).
8. **SAKAYA_EXIT (0x01FB) 8 bytes**: Handler reads error_code(U16), unknown(U16), exit_context(U32). Was sending 2B.
9. **SAKAYA_SIT push 0x024C**: After 0x020F, server pushes MEMLIST (member_count=0)
10. **GOTOLIST Dark Tower**: Zone 3 connections: [2, 4, 5] → GOTOLIST includes Dark Tower
11. **build_minimal_reply**: STORE_IN_REQUEST → status=1 (2B), SAKAYA_EXIT_REQUEST → 8B
