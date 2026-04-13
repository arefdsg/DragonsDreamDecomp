# Client-Sent Message Payloads (Client → Server)

## Binary: `D:\DragonsDreamDecomp\extracted\0.BIN` (504,120 bytes, SH-2 big-endian)
## Date: 2026-03-11 — from 54 scmd_new_message call sites
## Total: 104 distinct client→server message types

---

## Critical Messages (Fully Decoded)

### LOGIN_REQUEST (0x019E) — ~60 bytes payload
File offset: 0x012C3C
```
Offset  Size  Type     Field
0       2     U16 BE   protocol_version (always 0)
2       2     U16 BE   login_flag (from arg)
4       16    bytes    player_name (Shift-JIS)
20      1     U8       char_field_0x15
21      1     U8       char_field_0x17
22      1     U8       zone_class (computed from 0x18)
23      1     U8       zone_field (computed from 0x16)
24      1     U8       char_field_0x19
25      1     U8       zero
26      1     U8       zero
27      1     U8       zero
28      4     U32 BE   char_data_1 (from offset 0x1C)
32      4     U32 BE   char_data_2 (from offset 0x20)
36      1     U8       zero
37      1     U8       zero
38      1     U8       char_field_0x2A
39      4     U8×4     zeros
43      1     U8       char_field_0x24
44      16    U16×8    skill_slots (from session+0x1780)
```
param1 = session[0x0264] (NOT zero)

### UPDATE_CHARDATA_REPLY (0x01AA) — 12 bytes payload
File offset: 0x012D62
```
Offset  Size  Type     Field
0       2     U16 BE   subcommand (always 1)
2       2     U16 BE   field_0 (from func result)
4       2     U16 BE   field_1
6       2     U16 BE   field_2
8       2     U16 BE   field_3
10      2     U16 BE   field_4
```

### CHARDATA2_NOTICE (0x0B6C) — 16 bytes payload
File offset: 0x012DD2
```
Offset  Size  Type     Field
0       16    bytes    identity_data
```
param1 = 0

### STANDARD_REPLY (0x0048) — variable payload
File offset: 0x012DF0
```
Offset  Size  Type     Field
0       N     bytes    data (from args)
N       1     U8       zero terminator
```
Clears session[0x008E] = 0

### MOVE (0x01C1) — 1 or 3 bytes payload
File offset: 0x013A9A (variant 1: session+param), 0x013ADC (variant 2: simple)
```
Variant 1 (full):
0       1     U8       x/direction
1       1     U8       y
2       1     U8       z/flags
param1 = session[0x0264]

Variant 2 (simple):
0       1     U8       direction
param1 = 0
```

### BTL_CMD (0x0221) — 12 bytes payload
File offset: 0x013EBE
```
Offset  Size  Type     Field
0       1     U8       command_type
1       1     U8       target
2       2     U16 BE   action_id
4       8     bytes    extra_data
```

### BTL_CHGMODE (0x0224) — 2 bytes payload
File offset: 0x013EFC
```
0       2     U16 BE   always 0
```

### EXEC_EVENT (0x01CF) — 8+ bytes payload
File offset: 0x013F72
```
0       2     U16 BE   event_type
2       2     U16 BE   event_subtype
4       4     U32 BE   event_data
8       N     bytes    event_payload (variable)
```

### CHANGE_PARA (0x02F5) — ~212 bytes payload (full char state sync)
File offset: 0x013D48
```
0       1     U8       char_field_0x15
1       1     U8       char_field_0x17
2       1     U8       zone (computed)
3       1     U8       zone2 (computed)
4       1     U8       char_field_0x19
5       3     U8×3     zeros
8       4     U32 BE   char_data_1
12      4     U32 BE   char_data_2
16      18    U16×9    stats (from chardata+0x92)
34      2     U16 BE   field_102
36      2     U16 BE   field_104
38      18    U16×9    stats (fields 64-78)
56      12    U16×6    stats (fields 84-94)
68      6     U16×3    stats (fields 96-100)
74      48    U16×24   equipment data (24 items × 2 fields)
```

---

## Simple Messages (sorted by msg_type)

| msg_type | Name | Payload Layout | Bytes |
|----------|------|---------------|-------|
| 0x0048 | STANDARD_REPLY | D(data,N), B(0) | var |
| 0x0068 | CARD_NOTICE | W(0) | 2 |
| 0x006D | SYSTEM_NOTICE | D(id,16), D(str,len), B(0) | var |
| 0x019A | LOGOUT_NOTICE | W(0) | 2 |
| 0x019C | GOTOLIST_NOTICE | L(dest_id) | 4 |
| 0x01A0 | SAKAYA_IN_NOTICE | (empty) | 0 |
| 0x01A2 | BB_RMSUBDIR_REPLY | L(arg) | 4 |
| 0x01A4 | PARTYLIST_REPLY | L(arg) | 4 |
| 0x01A7 | CLR_KNOWNMAP_REPLY | W(0) | 2 |
| 0x01AC | MAP_CHANGE_NOTICE | W(0) | 2 |
| 0x01AF | AREA_LIST_REPLY | D(data,20), W(0), W(20) | 24 |
| 0x01B3 | ALLOW_SETLEADER_REPLY | W(0) | 2 |
| 0x01B7 | REGIONCHANGE_REQUEST | D(data,16) | 16 |
| 0x01C1 | MOVE | B(dir) or B(x),B(y),B(z) | 1-3 |
| 0x01CF | EXEC_EVENT | W(type), W(sub), L(data), D(var) | 8+ |
| 0x01D3 | GIVEUP_REPLY | W(1), W(0), L(8), L(session), B(x), B(0)×3 | 16 |
| 0x01D6 | SETPOS_NOTICE | D(data,16) + memcpy side-effect | 16 |
| 0x01DF | CAMP_IN_NOTICE | B(bitfield), B(arg) | 2 |
| 0x01E3 | ENCOUNTPARTY_NOTICE | W(0) | 2 |
| 0x01E6 | INQUIRE_JOIN_NOTICE | B(arg) | 1 |
| 0x01EA | BTL_EFFECTEND_REPLY | W(0) | 2 |
| 0x01EC | AVATA_NOID_NOTICE | L(avatar_id) | 4 |
| 0x01EE | PARTYID_REPLY | (empty) | 0 |
| 0x01F2 | SHOP_ITEM_REPLY | W(arg1), W(arg2) | 4 |
| 0x01F4 | SHOP_BUY_REPLY | W(arg1), W(arg2) | 4 |
| 0x01F8 | USERLIST_NOTICE | D(data,16), W(arg1), W(arg2) | 20 |
| 0x01FA | SAKAYA_TBLLIST2_REQUEST | W(0) | 2 |
| 0x01FC | SHOP_IN_REPLY | W(0) | 2 |
| 0x01FE | SHOP_LIST_REPLY | D(data,16) | 16 |
| 0x0200 | SHOP_SELL_REPLY | W(0) | 2 |
| 0x0202 | SEKIBAN_NOTICE | W(0) | 2 |
| 0x0204 | CAMP_OUT_NOTICE | W(arg1), B(arg2), B(0) | 4 |
| 0x020C | STORE_IN_NOTICE | W(0) | 2 |
| 0x020E | SAKAYA_EXIT_NOTICE | L(target), W(cmd) | 6 |
| 0x0210 | SAKAYA_LIST_NOTICE | W(arg) | 2 |
| 0x0216 | SAKABA_MOVE_NOTICE | D(data,16) | 16 |
| 0x0219 | SAKAYA_FIND_REPLY | W(0) | 2 |
| 0x0221 | BTL_CMD | B(cmd), B(tgt), W(action), D(extra,8) | 12 |
| 0x0224 | BTL_CHGMODE | W(0) | 2 |
| 0x022C | MEMBERDATA_NOTICE | L(arg) | 4 |
| 0x0230 | INQUIRE_UNITE_NOTICE | B(arg) | 1 |
| 0x0233 | TELEPORT_NOTICE | D(data1,20), D(data2,18) | 38 |
| 0x0235 | CANCEL_ENCOUNT_NOTICE | (empty) | 0 |
| 0x023B | ALLOW_UNITE_REPLY | W(0) | 2 |
| 0x023E | TELEPORTLIST_REPLY | D(data1,20), D(data2,18) | 38 |
| 0x0240 | MIRRORDUNGEON_REPLY | D(data,16) | 16 |
| 0x0243 | MONSTERWARN_NOTICE | W(arg), W(0) | 4 |
| 0x0245 | SAKAYA_CHARLIST_NOTICE | D(text,strlen), B(0) | var |
| 0x024B | SAKAYA_SIT_REPLY | L(arg) | 4 |
| 0x024E | SAKAYA_MEMLIST_NOTICE | D(data,16) | 16 |
| 0x0250 | MOVE_SEAT_NOTICE | D(text,strlen), B(0) | var |
| 0x0254 | SET_SIGN_NOTICE | B(arg) | 1 |
| 0x025B | ALLOW_JOIN_REPLY | W(0) | 2 |
| 0x025F | PARTY_BREAKUP_NOTICE | B(reason) | 1 |
| 0x0268 | DISARM_SKILL_REPLY | L(arg) | 4 |
| 0x026A | SEL_THEME_REPLY | L(0) | 4 |
| 0x026C | EQUIP_NOTICE | W(arg_byte), W(0) | 4 |
| 0x026F | FINDUSER_REPLY | W(0) | 2 |
| 0x0271 | STORE_LIST_REPLY | D(data,16) | 16 |
| 0x0275 | COMPOUND_REPLY | W(0) | 2 |
| 0x0277 | CONFIRM_LVLUP_REPLY | W(0) | 2 |
| 0x0289 | USE_NOTICE | D(d1,16), D(d2,16), L(arg), W(arg), B(arg) | 39 |
| 0x028E | INQUIRE_BUY_NOTICE | B(arg) | 1 |
| 0x0290 | TRADE_NOTICE | W(0) | 2 |
| 0x0293 | EVENT_MOVE_NOTICE | D(data,16), W(a1), W(a2), L(a3) | 24 |
| 0x0296 | BTL_ACTIONCOUNT_NOTICE | B(arg), B(0) | 2 |
| 0x0298 | FINDUSER2_REPLY | W(0) | 2 |
| 0x029A | CLASS_LIST_REPLY | B(arg) | 1 |
| 0x029D | SHOP_OUT_REPLY | B(a1), B(a2), W(0) | 4 |
| 0x029F | DIR_REPLY | B(a1), B(a2), B(a3), B(a4) | 4 |
| 0x02A1 | SUBDIR_REPLY | B(a1), B(a2), B(a3), B(0), W(a4), B(a5), B(0) | 8 |
| 0x02A3 | MEMODIR_REPLY | B(a1), B(a2), W(a3) | 4 |
| 0x02A5 | NEWS_READ_REPLY | B(a1), B(a2), W(0), D(subj,40), D(body,len), B(0) | var |
| 0x02A7 | NEWS_WRITE_REPLY | B(a1), B(a2), W(a3) | 4 |
| 0x02A9 | CHECK_THEME_REPLY | W(session[0x024E]) | 2 |
| 0x02AB | MAIL_LIST_REPLY | L(arg) | 4 |
| 0x02AD | GET_MAIL_REPLY | B(0), B(a), D(name,16), D(subj,40), W(a), B(a), B(0), L(a), L(len), D(body,len) | var |
| 0x02AF | SEND_MAIL_REPLY | L(arg) | 4 |
| 0x02B1 | NEWS_DEL_REPLY | D(data, strlen+1) | var |
| 0x02B3 | BB_MKDIR_REPLY | B(a), B(0), B(0), B(0) | 4 |
| 0x02B5 | BB_RMDIR_REPLY | B(a1), B(0), B(0), B(0), D(str,strlen+1) | var |
| 0x02B7 | BB_MKSUBDIR_REPLY | B(a1), B(a2), W(0) | 4 |
| 0x02B9 | LEVELUP_REPLY | B(a1), B(a2) | 2 |
| 0x02BB | DEL_MAIL_REPLY | W(0) | 2 |
| 0x02BE | COLO_WAITING_NOTICE | W(0) | 2 |
| 0x02C1 | COLO_EXIT_NOTICE | W(0) | 2 |
| 0x02C3 | COLO_LIST_REPLY | B(arg) | 1 |
| 0x02C5 | COLO_ENTRY_NOTICE | W(0) | 2 |
| 0x02C8 | COLO_BATTLE_NOTICE | W(0) | 2 |
| 0x02CD | COLO_RESULT_NOTICE | W(arg) | 2 |
| 0x02D0 | GIVE_ITEM_NOTICE | W(a1), W(0), D(data,16) | 20 |
| 0x02D4 | CMD_BLOCK_REPLY | B(arg), B(0), W(0) | 4 |
| 0x02D9 | SETLEADER_ACCEPT_REPLY | B(arg) | 1 |
| 0x02DB | CAST_DICE_NOTICE | W(action) + case-dependent (2-6 complex) | var |
| 0x02E0 | SKILL_LIST_REPLY | W(arg) | 2 |
| 0x02E2 | LEARN_SKILL_REPLY | W(arg) | 2 |
| 0x02E4 | SKILLUP_REPLY | W(arg) | 2 |
| 0x02E6 | EQUIP_SKILL_REPLY | W(arg) | 2 |
| 0x02E8 | DISARM_NOTICE | W(entity), B(count), B(count<<4), then N×D(data,16) | var |
| 0x02ED | TRADE_CANCEL_NOTICE | W(a1), W(a2) | 4 |
| 0x02F5 | CHANGE_PARA | full char state (~212B) | ~212 |
| 0x02FA | SAKAYA_TBLLIST_NOTICE | D(data,16), L(arg), W(arg) | 22 |
| 0x04E0 | EXPLAIN_REPLY | D(d1,20), D(d2,18), W(0), L(arg) | 42 |

---

## Key Findings

1. **No 0x0035 init message via scmd** — the paired table entry 0 (0x0035 → 0x01E8)
   is NOT sent through the SCMD library. It may be sent at the SV layer directly or
   handled as part of the initial connection flow.

2. **Many "REPLY" messages are client→server** — the naming convention follows the
   protocol pattern (server REQUESTs, client REPLIEs), not the network direction.

3. **param1** is usually 0. Exceptions: LOGIN_REQUEST and MOVE (variant 1) use
   session[0x0264].

4. **Most payloads are small** — majority are 1-4 bytes. Only LOGIN_REQUEST (~60B),
   CHANGE_PARA (~212B), and variable-length text messages are large.
