# Dragon's Dream — Message Flow & Paired Table

## Paired Message Table (file 0x043424, 108 entries)

Maps CLIENT-SENT msg_type → EXPECTED SERVER REPLY msg_type.
The secondary dispatch (file 0x34E4) uses this to know which reply to wait for.

### Full Table

| # | Client Sends | Server Replies | Client Name | Server Name |
|---|-------------|---------------|-------------|-------------|
| 0 | 0x0035 | 0x01E8 | (init/handshake) | ESP_NOTICE |
| 1 | 0x019E | 0x019F | LOGIN_REQUEST | UPDATE_CHARDATA_REQUEST |
| 2 | 0x01AA | 0x02F9 | UPDATE_CHARDATA_REPLY | CHARDATA_REQUEST |
| 3 | 0x0B6C | 0x02F9 | CHARDATA2_NOTICE | CHARDATA_REQUEST |
| 4 | 0x0048 | 0x0049 | STANDARD_REPLY | SPEAK_REQUEST |
| 5 | 0x006D | 0x006F | (ESP related) | ESP_REQUEST |
| 6 | 0x01EC | 0x01ED | (party) | PARTYID_REQUEST |
| 7 | 0x01EE | 0x01EF | (map) | CLR_KNOWNMAP_REQUEST |
| 8 | 0x01A7 | 0x01A8 | (party) | PARTYEXIT_REQUEST |
| 9 | 0x025F | 0x0260 | (chat) | ACTION_CHAT_REQUEST |
| 10 | 0x02D4 | 0x02D5 | CMD_BLOCK_REPLY | CAST_DICE_REQUEST |
| 11 | 0x02DB | 0x02DC | CAST_DICE_NOTICE | CARD_REQUEST |
| 12 | 0x019A | 0x019B | (logout) | GOTOLIST_REQUEST |
| 13 | 0x019C | 0x019D | (info) | INFORMATION_NOTICE |
| 14 | 0x01B7 | 0x01B8 | REGIONCHANGE_REQUEST | FINDUSER_REQUEST |
| 15 | 0x026F | 0x0270 | (store) | STORE_LIST_REQUEST |
| 16 | 0x0271 | 0x0272 | (store) | STORE_IN_REQUEST |
| 17 | 0x020C | 0x020D | (sakaya) | SAKAYA_LIST_REQUEST |
| 18 | 0x0210 | 0x0211 | (sakaba) | SAKABA_MOVE_REQUEST |
| 19 | 0x0216 | 0x0217 | (sakaya) | SAKAYA_IN_REQUEST |
| 20 | 0x01A0 | 0x01A1 | (userlist) | USERLIST_REQUEST |
| 21 | 0x01F8 | 0x01F9 | (sakaya) | SAKAYA_TBLLIST_REQUEST |
| 22 | 0x02FA | 0x01F9 | (sakaya alt) | SAKAYA_TBLLIST_REQUEST |
| 23 | 0x01FA | 0x01FB | (sakaya) | SAKAYA_EXIT_REQUEST |
| 24 | 0x020E | 0x020F | (sakaya) | SAKAYA_SIT_REQUEST |
| 25 | 0x024B | 0x024C | (sakaya) | SAKAYA_MEMLIST_REQUEST |
| 26 | 0x024E | 0x024F | (sakaya) | SAKAYA_FIND_REQUEST |
| 27 | 0x0219 | 0x021A | (sakaya) | SAKAYA_STAND_REQUEST |
| 28 | 0x0245 | 0x0246 | (sign) | SET_SIGN_REQUEST |
| 29 | 0x0254 | 0x0255 | SET_SIGN_NOTICE | MOVE_SEAT_REQUEST |
| 30 | 0x0250 | 0x0251 | (sekiban) | SET_SEKIBAN_REQUEST |
| 31 | 0x0202 | 0x0203 | (shop) | SHOP_LIST_REQUEST |
| 32 | 0x01FE | 0x01FF | (shop) | SHOP_IN_REQUEST |
| 33 | 0x01FC | 0x01FD | (shop) | SHOP_ITEM_REQUEST |
| 34 | 0x01F2 | 0x01F3 | (shop) | SHOP_BUY_REQUEST |
| 35 | 0x01F4 | 0x01F5 | (shop) | SHOP_SELL_REQUEST |
| 36 | 0x0200 | 0x0201 | SHOP_SELL_REPLY | SHOP_OUT_REQUEST |
| 37 | 0x029D | 0x029E | (dir) | DIR_REQUEST |
| 38 | 0x029F | 0x02A0 | (subdir) | SUBDIR_REQUEST |
| 39 | 0x02A1 | 0x02A2 | SUBDIR_REPLY | MEMODIR_REQUEST |
| 40 | 0x02A3 | 0x02A4 | MEMODIR_REPLY | NEWS_READ_REQUEST |
| 41 | 0x02A5 | 0x02A6 | (news) | NEWS_WRITE_REQUEST |
| 42 | 0x02A7 | 0x02A8 | (news) | NEWS_DEL_REQUEST |
| 43 | 0x02B1 | 0x02B2 | (bb) | BB_MKDIR_REQUEST |
| 44 | 0x02B3 | 0x02B4 | (bb) | BB_RMDIR_REQUEST |
| 45 | 0x02B5 | 0x02B6 | (bb) | BB_MKSUBDIR_REQUEST |
| 46 | 0x02B7 | 0x02B8 | (bb) | BB_RMSUBDIR_REQUEST |
| 47 | 0x01A2 | 0x01A3 | (party) | PARTYLIST_REQUEST |
| 48 | 0x01A4 | 0x022B | PARTYLIST_REPLY | PARTYENTRY_REQUEST |
| 49 | 0x01E6 | 0x01E7 | (party) | ALLOW_JOIN_REQUEST |
| 50 | 0x025B | 0x025C | (party) | CANCEL_JOIN_REQUEST |
| 51 | 0x022C | 0x022F | (party) | PARTYUNITE_REQUEST |
| 52 | 0x0230 | 0x0231 | (party) | ALLOW_UNITE_REQUEST |
| 53 | 0x023B | 0x023C | (area) | AREA_LIST_REQUEST |
| 54 | 0x01AF | 0x01B0 | (teleport) | TELEPORTLIST_REQUEST |
| 55 | 0x023E | 0x023F | (explain) | EXPLAIN_REQUEST |
| 56 | 0x04E0 | 0x0046 | (teleport) | REGIST_HANDLE_REQUEST |
| 57 | 0x0233 | 0x0234 | (mirror) | MIRRORDUNGEON_REQUEST |
| 58 | 0x0240 | 0x0241 | (find) | FINDUSER2_REQUEST |
| 59 | 0x0298 | 0x0299 | (class) | CLASS_LIST_REQUEST |
| 60 | 0x029A | 0x029B | (class) | CLASS_CHANGE_REQUEST |
| 61 | 0x01C1 | 0x01C4 | (move) | MOVE1_REQUEST |
| 62 | 0x01C2 | 0x01C4 | (move alt) | MOVE1_REQUEST |
| 63 | 0x01AC | 0x01AD | MAP_CHANGE_NOTICE | CAMP_IN_REQUEST |
| 64 | 0x01DF | 0x01E0 | (movemode) | SET_MOVEMODE_REQUEST |
| 65 | 0x02F7 | 0x02F8 | SET_MOVEMODE_NOTICE | GIVEUP_REQUEST |
| 66 | 0x01D3 | 0x01D4 | (setpos) | SETPOS_REQUEST |
| 67 | 0x01D6 | 0x02D8 | (leader) | INQUIRE_LEADER_NOTICE |
| 68 | 0x02D9 | 0x02DA | (leader) | ALLOW_SETLEADER_REQUEST |
| 69 | 0x01B3 | 0x01B4 | (camp) | CAMP_OUT_REQUEST |
| 70 | 0x0204 | 0x0205 | (equip) | EQUIP_REQUEST |
| 71 | 0x026C | 0x026D | (disarm) | DISARM_REQUEST |
| 72 | 0x02E8 | 0x02E9 | (skill) | USE_SKILL_REQUEST |
| 73 | 0x02F5 | 0x02F6 | (para) | CHANGE_PARA_REQUEST |
| 74 | 0x0243 | 0x0244 | (encount) | ENCOUNTMONSTER_REQUEST |
| 75 | 0x0221 | 0x0222 | (btl) | BTL_CMD_REQUEST |
| 76 | 0x0224 | 0x0225 | (btl) | BTL_CHGMODE_REQUEST |
| 77 | 0x0296 | 0x0297 | (btl) | BTL_EFFECTEND_REQUEST |
| 78 | 0x01EA | 0x01EB | (btl) | BTL_END_REQUEST |
| 79 | 0x01E3 | 0x01E4 | (cancel) | CANCEL_ENCOUNT_REQUEST |
| 80 | 0x0235 | 0x0236 | (btl) | BTLJOIN_REQUEST |
| 81 | 0x01CF | 0x01D0 | (event) | EXEC_EVENT_REQUEST |
| 82 | 0x0293 | 0x0294 | (give) | GIVE_ITEM_REQUEST |
| 83 | 0x02D0 | 0x02D1 | (use) | USE_REQUEST |
| 84 | 0x0289 | 0x028D | (trade) | SELL_REQUEST |
| 85 | 0x028E | 0x028F | (trade) | BUY_REQUEST |
| 86 | 0x0290 | 0x0291 | (trade) | TRADE_CANCEL_REQUEST |
| 87 | 0x02ED | 0x02EE | (compound) | COMPOUND_REQUEST |
| 88 | 0x0275 | 0x0276 | (level) | CONFIRM_LVLUP_REQUEST |
| 89 | 0x0277 | 0x0278 | (level) | LEVELUP_REQUEST |
| 90 | 0x02B9 | 0x02BA | (skill) | SKILL_LIST_REQUEST |
| 91 | 0x02E0 | 0x02E1 | (skill) | LEARN_SKILL_REQUEST |
| 92 | 0x02E2 | 0x02E3 | (skill) | SKILLUP_REQUEST |
| 93 | 0x02E4 | 0x02E5 | (skill) | EQUIP_SKILL_REQUEST |
| 94 | 0x02E6 | 0x02E7 | (skill) | DISARM_SKILL_REQUEST |
| 95 | 0x0268 | 0x0269 | (theme) | SEL_THEME_REQUEST |
| 96 | 0x026A | 0x026B | (theme) | CHECK_THEME_REQUEST |
| 97 | 0x02A9 | 0x02AA | (mail) | MAIL_LIST_REQUEST |
| 98 | 0x02AB | 0x02AC | (mail) | GET_MAIL_REQUEST |
| 99 | 0x02AD | 0x02AE | (mail) | SEND_MAIL_REQUEST |
| 100 | 0x02AF | 0x02B0 | (mail) | DEL_MAIL_REQUEST |
| 101 | 0x02BB | 0x02BC | (colo) | COLO_WAITING_REQUEST |
| 102 | 0x02BE | 0x02BF | (colo) | COLO_EXIT_REQUEST |
| 103 | 0x02C1 | 0x02C2 | (colo) | COLO_LIST_REQUEST |
| 104 | 0x02C3 | 0x02C4 | (colo) | COLO_ENTRY_REQUEST |
| 105 | 0x02C5 | 0x02C6 | (colo) | COLO_CANCEL_REQUEST |
| 106 | 0x02C8 | 0x02C9 | (colo) | COLO_FLDENT_REQUEST |
| 107 | 0x02CD | 0x02CE | (colo) | COLO_RANKING_REQUEST |

---

## Login Flow Sequence (CONFIRMED from paired table)

```
Client                              Server
  |                                    |
  |--- BBS: " P\r" ------------------>|
  |<-- "*\r\n" -----------------------|
  |--- BBS: "SET\r" ----------------->|
  |<-- "*\r\n" -----------------------|
  |--- BBS: "C HRPG\r" -------------->|
  |<-- "COM HRPG\r\n" ----------------|
  |                                    |
  |=== SV FRAMING STARTS =============|
  |                                    |
  |--- 0x0035 (init) ---------------->| Paired entry 0
  |<-- 0x01E8 ESP_NOTICE -------------|
  |                                    |
  |--- 0x019E LOGIN_REQUEST --------->| Paired entry 1
  |<-- 0x019F UPDATE_CHARDATA_REQ ----|
  |                                    |
  |--- 0x01AA UPDATE_CHARDATA_REPLY ->| Paired entry 2
  |<-- 0x02F9 CHARDATA_REQUEST -------|
  |                                    |
  |  (server also sends CHARDATA_REPLY 0x02D2 with character list) |
  |  (server sends INFORMATION_NOTICE 0x019D)                      |
  |  (server sends MAP_NOTICE 0x01DE)                               |
  |  etc.                              |
```

### Key Server-Initiated Messages (sent without client request)

These are NOTICE messages the server pushes to clients:
- CHARDATA_NOTICE (0x01AB) — other player data
- SPEAK_NOTICE (0x0076) — chat messages
- MAP_NOTICE (0x01DE) — map data
- MOVE2_NOTICE (0x02F3) — other player movement
- BATTLEMODE_NOTICE (0x021F) — battle mode changes
- BTL_RESULT_NOTICE (0x0227) — battle results
- BTL_GOLD_NOTICE (0x01C8) — battle gold/loot
- ENCOUNTMONSTER_NOTICE (0x01CA) — random encounters
- CHAR_DISAPPEAR_NOTICE (0x01BC) — player leaves area
- EVENT_EFFECT_NOTICE (0x02F0) — event effects
- WAIT_EVENT_NOTICE (0x02F1) — event wait signals

### Key Client→Server Messages (from SCMD send sites)

- 0x0035: Init/handshake
- 0x019E: LOGIN_REQUEST (60 byte payload)
- 0x01AA: UPDATE_CHARDATA_REPLY (~20 byte payload)
- 0x0B6C: CHARDATA2_NOTICE (16 byte payload)
- 0x0048: STANDARD_REPLY (variable)
- 0x0010: Internal control
- 0x0014: Internal control
- 0x02D4: CMD_BLOCK_REPLY
- 0x02DB: CAST_DICE_NOTICE
- 0x01B7: REGIONCHANGE_REQUEST
- 0x0254: SET_SIGN_NOTICE
- 0x0200: SHOP_SELL_REPLY
- 0x02A1: SUBDIR_REPLY
- 0x02A3: MEMODIR_REPLY
- 0x01A4: PARTYLIST_REPLY
- 0x01AC: MAP_CHANGE_NOTICE
- 0x02F7: SET_MOVEMODE_NOTICE
