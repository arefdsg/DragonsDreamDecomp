# Handler Payload Layouts — Detailed Decompilation Results

## Binary: `D:\DragonsDreamDecomp\extracted\0.BIN` (504,120 bytes, SH-2 big-endian)
## Wire format: 8-byte header [2B param1][2B msg_type][4B payload_size] + payload
## Date: 2026-03-11, UPDATED 2026-03-11 session 5 (ALL handlers complete)

---

## Fully Decompiled Handlers (sorted by msg_type)

### ESP_REPLY (0x006E) — 0 bytes (thin wrapper)
Handler: file 0x3EDA (mem 0x06013EDA)
No payload parsed. Calls set_state(4, 1) via 0x06028310, then tail-calls
message forwarder at 0x06011DBC with payload pointer.

### ESP_NOTICE (0x01E8) — 51 bytes — CRITICAL LOGIN
Handler: file 0x3F1C (mem 0x06013F1C)
First server message in login flow. Resets entire game state.
```
Offset  Size  Type     Field                          Destination
0       2     U16 BE   status                         g_state+0x04
2       2     U16 BE   session_param                  g_state+0x0264 (used as param1 in LOGIN_REQUEST)
4       2     U16 BE   connection_id                  g_state+0xA2
6       1     U8       game_mode                      g_state+0xA4
7       1     U8       sub_mode                       g_state+0xA5
8       4     U32 BE   server_id                      g_state+0x94
12      16    bytes    server_name (Shift-JIS)         g_state+0xA6
28      12    bytes    session_data                    g_state+0x7C88
40      11    bytes    config_bytes[0..10]             g_state+0x7C94..0x7C9F
```
Config bytes detail:
- [0x7C94]=0 (cleared), [0x7C95..97]=payload[40..42],
- [0x7C98]=payload[43]+0xFF (subtract 1 with wrap),
- [0x7C99..9F]=payload[44..50]

State cleared after parsing:
- g_state[0xAB14..15]=0, g_state[0xAD48]=0 (clock count),
- g_state[0xD044]=0 (disappear cursor), g_state[0xABA4..5]=0,
- g_state[0x6F88]=0 (mission roster), g_state[0xF4B4]=0 (battle state),
- g_state[0x8E..91]=1 (init flags), g_state[6]=0 (SV msg_type),
- 0x0605F432=0 (global flag byte)

### REGIST_HANDLE_REQUEST (0x0046) — 2 bytes
Handler: file 0x3D04 (mem 0x06013D04)
```
Offset  Size  Type     Field
0       2     U16 BE   handle_id (stored at context+4)
```
Also sets flags at context[0x8C-0x91] and calls 0x0603FBC0.

### STANDARD_REPLY (0x0048) — VARIABLE
Handler: file 0x3D80 (thin wrapper → 0x06011CA8)
Client builds with scmd_add_data(length, data_ptr) + scmd_add_byte(0).

### SPEAK_REQUEST (0x0049) — 2-4 bytes
Handler: file 0x3D42 (mem 0x06013D42)
```
Offset  Size  Type     Field
0       2     U16 BE   status (0=proceed, nonzero=skip)
--- if status == 0: ---
2       2     U16 BE   speak_data (passed to 0x06011C4E)
```

### SPEAK_NOTICE (0x0076) — VARIABLE (LF-delimited text)
Handler: file 0x3D86 (mem 0x06013D86)
LF (0x0A) delimited string fields, not fixed-width.

### INFORMATION_NOTICE (0x019D) — 2-8 bytes
Handler: file 0x3DDA (mem 0x06013DDA)
```
Offset  Size  Type     Field
0       2     U16 BE   status
--- if status == 0: ---
2       2     U16 BE   info_type
4       4     U32 BE   info_value
```

### UPDATE_CHARDATA_REQUEST (0x019F) — 24 bytes
Handler: file 0x3578 (mem 0x06013578)
```
Offset  Size  Type     Field
0       2     U16 BE   status
--- if status == 0: ---
2       2     U16 BE   char_field
4       4     U32 BE   char_id
8       16    bytes    char_data (memcpy)
```

### CHARDATA_NOTICE (0x01AB) — 76-160+N*24 bytes (VARIABLE)
Handler: file 0x3B90 (mem 0x06013B90)
```
Offset  Size  Type     Field
0       2     U16 BE   char_id
2       22    bytes    char_name (not read by handler)
24      8     struct   appearance (parse_appearance: race, hair, etc.)
32      4     U32 BE   experience
36      4     U32 BE   gold
40      16    U16[8]   stat_array (HP, MP, STR, etc.)
56      8     struct   status (parse_status: class 0-5, level 1-16)
64      1     U8       unknown_64
65      1     U8       unknown_65
66      1     U8       unknown_66
67      1     U8       has_equip_stats (0=present, nonzero=absent)
68      1     U8       unknown_68
69      1     U8       unknown_69
70      1     U8       num_equip_items
71      1     U8       has_equip_items (0=present, nonzero=absent)
72      4     bytes    padding
--- if has_equip_stats == 0: ---
76      38    U16[19]  equip_stats_base
114     38    U16[19]  equip_stats_current
152     8     5B+3pad  equip_flags
--- if has_equip_items == 0 (starts after equip stats if present, else at 76): ---
N*24    ...   items    Equipment items (16B data + 8B padding each)
```

### MOVE2_REQUEST (0x01C5) — 12 bytes
Handler: file 0x720C (mem 0x0601720C)
```
Offset  Size  Type     Field
0       1     U8       field_0 (stored at state+0x1E76)
1       1     U8       field_1 (stored at state+0x1E77)
2       1     U8       direction (validated 1-4, clamped to 1)
3       1     U8       field_3 (stored at state+0x1E79)
4       2     U16 BE   field_u16 (stored at state+0x1E74)
6       1     --       padding (skipped)
7       1     U8       field_7 (stored at state+0x1E7E)
8       4     U32 BE   field_u32 (stack temp, not persisted)
```

### BTL_GOLD_NOTICE (0x01C8) — VARIABLE (12 + groups)
Handler: file 0x83E4 (mem 0x060183E4)
```
HEADER (12 bytes):
Offset  Size  Type     Field
0       1     U8       result_flag_1
1       1     U8       result_flag_2
2       2     U16 BE   battle_gold_total
4       2     U16 BE   num_groups
6       6     --       reserved (skipped)

PER GROUP (8 + item_count*40 bytes):
0       4     U32 BE   entity_id
4       2     U16 BE   item_count
6       1     U8       action_type (0=none, 1=gold_gained, 2=gold_lost)
7       1     U8       action_param

PER ITEM (40 bytes):
0       4     U32 BE   item_gold_value
4       16    bytes    item_data
20      1     U8       item_visual_flag
21      8     struct   item_stats (equip_type 0-5, item_level 1-16)
29      8     struct   name_block (5 name bytes + 3 padding)
37      1     --       padding
38      1     U8       item_category
39      1     U8       item_bit_flags
```

### CLASS_CHANGE_REPLY (0x01C0) — 16+N bytes (CHUNKED)
Handler: file 0x69FC (mem 0x060169FC)
```
Offset  Size  Type     Field
0       2     U16 BE   result_code (0=success)
2       1     U8       new_class_id
3       1     U8       class_field_1
4       1     U8       class_field_2
5       1     U8       class_field_3
6       1     U8       class_field_4
7       1     U8       class_field_5
8       1     U8       class_field_6
9       1     U8       chunk_index (1-based)
10      1     U8       total_chunks
11      1     --       reserved (skipped)
12      4     U32 BE   data_size (bytes of chunk_data)
16      N     bytes    chunk_data (copied to 0x20200000 + (chunk_index-1)*512)
```
Chunks assembled at 0x20200000, finalized when all received.

### MAP_NOTICE (0x01DE) — VARIABLE (compressed)
Handler: file 0x6C38 (mem 0x06016C38)
4-byte header + compressed data, uses decompressor at 0x0603F694.

### PARTYID_REQUEST (0x01ED) — 2-8 bytes
Handler: file 0x401E (mem 0x0601401E)
```
Offset  Size  Type     Field
0       2     U16 BE   status
--- if status == 0: ---
2       2     U16 BE   value
4       4     U32 BE   party_id (stored at context+0x1E70)
```

### CLR_KNOWNMAP_REQUEST (0x01EF) — 4 bytes
Handler: file 0x405C (mem 0x0601405C)
```
Offset  Size  Type     Field
0       2     U16 BE   status
2       2     U16 BE   map_id
```

### PARTYEXIT_REQUEST (0x01A8) — 2-24 bytes
Handler: file 0x40C4 (mem 0x060140C4)
```
Offset  Size  Type     Field
0       2     U16 BE   status
--- if status == 0: ---
2       2     U16 BE   value
4       16    bytes    data (skipped by handler, probably name)
20      4     U32 BE   party_id
```

### BTL_CHGMODE_REPLY (0x0226) — VARIABLE (entity array)
Handler: file 0x7E64 (mem 0x06017E64)
```
HEADER (8 bytes):
0       4     U32 BE   entity_count
4       4     --       unused

PER ENTITY (12-byte header + slot data):
+0      1     U8       entity_id (0=new, nonzero=lookup)
+1      1     U8       battle_mode (0-10)
+2      1     U8       field_40
+3      1     U8       field_41
+4      2     U16 BE   slot_count (max 12)
+6      2     U16 BE   field_42
+8      4     U32 BE   data_length

PER SLOT (16 bytes):
+0      4     bytes    slot_bytes
+4      2     U16 BE   slot_u16_a
+6      2     U16 BE   slot_u16_b
+8      8     bytes    slot_entity_ids
```
Two-pass processing: validation first, then data application.

### BTL_RESULT_NOTICE (0x0227) — 44 + N*56 bytes
Handler: file 0x81B0 (mem 0x060181B0)
```
FIXED HEADER (44 bytes):
0       2     U16 BE   battle_id
2       2     U16 BE   num_combatants (loop count)
4       4     --       skipped
8       2     U16 BE   field_B
10      2     U16 BE   field_C
12      2     U16 BE   field_D
14      1     --       skipped
15      1     U8       field_E
16      8     bytes    name/identifier
24      2     U16 BE   field_F
26      2     U16 BE   field_G
28      1     U8       field_H
29      7     --       skipped
36      5     bytes    result_bytes[5]
41      3     --       skipped

PER COMBATANT (56 bytes):
+0      2     U16 BE   combatant_field_1
+2      2     U16 BE   combatant_field_2
+4      16    bytes    character_name
+20     4     U32 BE   experience/reward
+24     4     --       skipped
+28     1     U8       field_4
+29     1     U8       field_5
+30     2     U16 BE   field_6
+32     7     bytes    attribute_bytes[7]
+39     1     --       skipped
+40     16    U16[8]   stat_modifiers
```

### GIVE_ITEM_REPLY (0x0295) — 24 or 80 bytes
Handler: file 0x8E76 (mem 0x06018E76)
```
COMMON HEADER (24 bytes):
0       16    bytes    character_name (giver)
16      2     U16 BE   slot_id
18      2     U16 BE   result_code (0=fail, nonzero=success)
20      4     U32 BE   gold_amount (refunded on failure)

--- if result_code != 0 (success, +56 bytes): ---
24      4     U32 BE   transaction_id
28      2     U16 BE   item_id
30      1     U8       item_type_a
31      1     U8       item_type_b
32      16    bytes    item_name
48      2     U16 BE   equip_slot
50      8     bytes    attributes[8]
58      2     --       reserved (skipped)
60      4     U32 BE   item_price
64      16    U16[8]   stat_modifiers
```

### CHARDATA_REPLY (0x02D2) — 8 + N*entry_size bytes (MULTI-PAGE)
Handler: file 0x3858 (mem 0x06013858)
```
HEADER (8 bytes):
0       1     U8       char_type (1=char_list, 2=char_detail, 3=inventory)
1       1     U8       page_number (1-based)
2       1     U8       total_pages
3       1     U8       num_entries
4       4     U32 BE   chunk_size

CASE 1 - char_list (24 bytes per entry):
0       16    bytes    char_name (Shift-JIS)
16      2     U16 BE   experience
18      1     U8       class/job
19      1     U8       race/gender
20      1     U8       field
21      1     U8       field
22      1     U8       status_byte
23      1     --       padding

CASE 2 - char_detail (52 bytes per entry):
0       2     U16 BE   char_slot_id
2       1     U8       class
3       1     U8       sub_class
4       16    bytes    char_name
20      2     U16 BE   experience
22      8     bytes    stat_bytes[8] (STR,VIT,INT,MND,AGI,DEX,LUK,CHA)
30      2     --       padding
32      4     U32 BE   gold/HP
36      16    U16[8]   equipment_slots

CASE 3 - inventory (24 bytes per entry):
0       16    bytes    item_data
16      8     --       discarded
```
Multi-page: page_number 1 resets accumulation buffer at 0x20200000.
When page_number >= total_pages, accumulated data is parsed.

### CHARDATA_REQUEST (0x02F9) — 72 or 172 bytes
Handler: file 0x3648 (mem 0x06013648)
```
FIXED (72 bytes):
0       2     U16 BE   session_check (must be 0 to proceed)
2       2     U16 BE   char_field
4       4     U32 BE   character_id
8       16    bytes    character_name
24      8     struct   status_block (class, sub-class, race, gender, level)
32      4     U32 BE   field_A
36      4     U32 BE   field_B
40      16    U16[8]   skill_ids
56      8     struct   equipment_block (equip_type 0-5, equip_level 1-16)
64      1     --       padding
65      1     U8       skill_flag (0=invalid → clear skill area)
66      1     --       padding
67      1     U8       status_flag (nonzero=has extended data)
68      1     --       padding
69      1     U8       item_flag (0=invalid → clear item area)
70      1     --       padding
71      1     U8       license_flag (0=invalid → clear license area)

--- if status_flag != 0 (extended, +100 bytes): ---
72      38    U16[19]  base_stats
110     38    U16[19]  current_stats
148     8     5B+3pad  appearance_data
156     16    U16[8]   skill_levels
```

---

## Shop Handlers (decompiled 2026-03-11 session 3)

### SHOP_LIST_REQUEST (0x0203) — VARIABLE (8 + N*~20)
Handler: file 0x547A
```
HEADER:
Offset  Size  Type     Field
0       2     U16 BE   status (0=success)
--- if status == 0: ---
2       2     U16 BE   item_count
4       4     U32 BE   shop_id

PER ITEM (~20 bytes consumed, stored as 22 bytes at g_state+0x6C94):
+0      16    bytes    item_data (memcpy)
+16     1     U8       item_field
+17     3     --       skipped (3 bytes)
```
Shop item slots at g_state+0x6C94, 22 bytes per slot.
Clears area via 0x0603FBC0, sets g_state[0x6CA7]=11 (items per page?).
Calls 0x0603FB24 per item for 22-byte copy to slot.

### SHOP_IN_REQUEST (0x01FF) — VARIABLE (8 + N*~22)
Handler: file 0x5588
```
HEADER:
Offset  Size  Type     Field
0       2     U16 BE   status (0=success)
--- if status == 0: ---
2       2     U16 BE   item_count (stored at g_state+0x7544, clamped to max 32)
4       4     U32 BE   shop_param

PER ITEM (~22 bytes, stored at g_state+0x7948 + i*22):
+0      16    bytes    item_data (memcpy)
+16     2     U16 BE   item_field_a
+18     2     U16 BE   item_field_b
+20     ...   more fields per item
```
Items stored at g_state+0x7948, 22 bytes per entry, max 32 entries.

### SHOP_ITEM_REQUEST (0x01FD) — VARIABLE (8 + N*~22)
Handler: file 0x56B8
Same structure as SHOP_IN_REQUEST. item_count at g_state+0x7544, max 32.
Items at g_state+0x7948+i*22. Loop starts with r8=1 (1-indexed?).

### SHOP_BUY_REQUEST (0x01F3) — 8 bytes
Handler: file 0x57F6
```
Offset  Size  Type     Field
0       2     U16 BE   status (0=success)
--- if status == 0: ---
2       2     U16 BE   buy_param
4       4     U32 BE   gold_update (stored at party_entry+0x1C)
```
Computes party_entry = g_state+0x1BE0 + g_state[0x1B90]*0xA4.
Calls 0x06018FB8(result, 0) to process purchase.

### SHOP_SELL_REQUEST (0x01F5) — 8 bytes
Handler: file 0x5856
```
Offset  Size  Type     Field
0       2     U16 BE   status (0=success)
--- if status == 0: ---
2       2     U16 BE   sell_param
4       4     U32 BE   gold_update (stored at party_entry+0x1C)
```
Same party_entry calculation as SHOP_BUY. No further call after reads.

### SHOP_OUT_REQUEST (0x0201) — 2 bytes
Handler: file 0x58CC
```
Offset  Size  Type     Field
0       2     U16 BE   status
```
Trivial: reads u16 into g_state+4 and returns.

---

## Battle Handlers (decompiled 2026-03-11 session 3)

### ENCOUNTMONSTER_REQUEST (0x0244) — 2 bytes
Handler: file 0x7A2A
```
Offset  Size  Type     Field
0       2     U16 BE   status (stored at g_state+4)
```
Trivial: reads u16 and returns.

### ENCOUNTMONSTER_REPLY (0x01C9) — VARIABLE (10 + N*~32)
Handler: file 0x7A6C (mem 0x06017A6C) — Large encounter initialization
```
HEADER (10 bytes):
Offset  Size  Type     Field
0       1     U8       encounter_type_0 (→ g_state+0xAD68)
1       1     U8       encounter_type_1 (→ g_state+0xAD69)
2       2     U16 BE   encounter_id (→ g_state+0xAD6E)
4       2     U16 BE   encounter_param (→ g_state+0xAD6C)
6       2     U16 BE   battle_field (→ battle_base+0x0520)
8       2     --       skipped (2 bytes before entity loop starts)

PER ENTITY (~32 bytes):
+0      1     U8       facing/position (→ entity[0x2E])
+1      1     U8       mode_byte (→ entity[0x16])
+2      1     U8       field_36 (→ entity[0x24])
+3      1     --       skipped
+4      2     U16 BE   x_coord (→ entity[0x40] and entity[0x66])
+6      2     U16 BE   y_coord (→ entity[0x42] and entity[0x68])
+8      16    bytes    name/data (memcpy to entity[4..19])
+24     8     5B+3pad  status_block (read_5_skip_3 → entity[0x8C])
```
battle_base = g_state+0x10340. Entity count at battle_base+0x0522.
Entity stride = 0xA4 (164 bytes). Calls 0x0603FA64 to store entities.

### BATTLEMODE_NOTICE (0x021F) — VARIABLE (2 + N*~30)
Handler: file 0x7BF8 (mem 0x06017BF8)
Allocates 172 bytes of stack. First checks g_state[0xF4B4] (battle state).
```
HEADER:
Offset  Size  Type     Field
0       2     U16 BE   entity_count (loop bound)

PER ENTITY (~30 bytes):
+0      1     U8       entity_byte_0
+1      3     --       skipped (3 bytes)
+4      2     U16 BE   field_a (→ stack[72])
+6      2     U16 BE   field_b (→ stack[74], also copied to stack[110])
+8      8     5B+3pad  status (read_5_skip_3 → stack[0x94])
+16     16    bytes    name/data (memcpy to stack[12..27])
+32     ...   entity processing via 0x0601A712
```
Battle entity array at g_state+0x10864 (stride 0xA0 = 160 bytes per entity).
Init data at g_state+0x10340. Entity count at g_state+0x10862.
Max entity count at g_state+0x10FFC.

### BTL_CMD_REQUEST (0x0222) — 2 bytes + fallthrough
Handler: file 0x7D88
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ g_state+4)
```
After reading status, falls through to BTL_CMD_REPLY (0x0223) with original payload.

### BTL_CMD_REPLY (0x0223) — ~24 bytes
Handler: file 0x7DCC (mem 0x06017DCC)
Skips first 2 bytes (consumed by BTL_CMD_REQUEST on fallthrough).
```
Offset  Size  Type     Field
0       2     --       skipped (status from BTL_CMD_REQUEST)
2       1     U8       entity_index (r12, lookup key)
3       1     U8       action_byte_0 (→ temp[0])
4       1     U8       action_byte_1 (→ temp[1])
5       1     U8       action_flag (→ temp[21])
6       2     U16 BE   action_param (→ temp[2..3])
8       16    bytes    name/data (memcpy to temp[4..19])
24      ...   temp[20]=0, calls 0x0601AA3E(entity_index) for lookup
```
Uses 0x0603FB24 to copy 22-byte entity slot. Entity lookup via 0x0601AA3E.

### BTL_END_REQUEST (0x01EB) — 2 bytes
Handler: file 0x8356
```
Offset  Size  Type     Field
0       2     U16 BE   end_status (read to local stack var)
```
Trivial: reads u16 and returns immediately.

### BTL_END_REPLY (0x02F4) — 16 bytes
Handler: file 0x836E
```
Offset  Size  Type     Field
0       4     U32 BE   location_id (→ party_entry+0x1C)
4       2     U16 BE   x_coord (→ party_entry+0x66)
6       2     U16 BE   y_coord (→ party_entry+0x68)
8       8     5B+3pad  status_block (read_5_skip_3 → party_entry+0x8C)
```
Party entry = g_state+0x1BE0 + g_state[0x1B90]*0xA4.
Same format as GIVEUP_REQUEST — loads return location after battle.

### CANCEL_ENCOUNT_REQUEST (0x01E4) — 2 bytes
Handler: file 0x86C8
```
Offset  Size  Type     Field
0       2     U16 BE   status (0=success → clear battle slots)
```
If status==0: loops 5 groups × 3 slots in battle array at g_state+0x4B58
(stride 0x02A0 per group, 0xA4 per slot), marking entries as -1.

### CANCEL_ENCOUNT_REPLY (0x01E5) — 0 bytes
Handler: file 0x874C
No payload consumed. Directly manipulates battle state at g_state+0x4B58.
Same clearing loop as CANCEL_ENCOUNT_REQUEST (5 groups × 3 slots).

---

## EMPTY Handlers (22 — just rts, no payload read)
0x01B9 CURREGION_NOTICE, 0x01A1 USERLIST_REQUEST, 0x021C USERLIST_REPLY,
0x021E SAKAYA_STAND_REPLY, 0x0252 SET_SEKIBAN_REPLY, 0x0253 SET_SEKIBAN_NOTICE,
0x0249 EVENT_MAP_NOTICE, 0x024A MONSTER_MAP_NOTICE, 0x01DB VISION_NOTICE,
0x01DC OBITUARY_NOTICE, 0x0263 EQUIP_REPLY, 0x026E DISARM_REPLY,
0x0220 BTL_MEMBER_NOTICE, 0x0225 BTL_CHGMODE_REQUEST, 0x0228 BTL_END_NOTICE,
0x0229 BTL_MASK_NOTICE, 0x0297 BTL_EFFECTEND_REQUEST, 0x0236 BTLJOIN_REQUEST,
0x0237 BTLJOIN_REPLY, 0x02EC COLO_CANCEL_REPLY

---

## Movement/Map Handlers (decompiled 2026-03-11)

### MOVE2_NOTICE (0x02F3) — VARIABLE (4 + N*8)
Handler: file 0x729A (mem 0x0601729A)
```
HEADER:
Offset  Size  Type     Field
0       4     U32 BE   count (number of movement records)

PER RECORD (8 bytes):
+0      1     U8       y_cell (entity Y grid index)
+1      1     U8       x_cell (entity X grid index)
+2      2     --       skipped
+4      2     U16 BE   position_packed (map position)
+6      1     U8       direction_byte
+7      1     U8       anim_state
```
Entity table at g_state+0x8708, 4 bytes per cell: [2B tile][1B dir][1B anim].

### SET_MOVEMODE_REQUEST (0x01E0) — 2 bytes
Handler: file 0x73B2
```
Offset  Size  Type     Field
0       2     U16 BE   move_mode
```

### SET_MOVEMODE_REPLY (0x01E1) — 3 bytes
Handler: file 0x73CE
```
Offset  Size  Type     Field
0       1     U8       move_mode (0xFF=auto, bit0: 0=stand, 1=walk)
1       1     U8       sub_mode (used when mode=0xFF)
2       1     U8       extra (used when mode=0xFF)
```
Stores: player[+18]=move_state(1/2/3), player[+20]=sub_mode, player[+21]=extra.

### GIVEUP_REQUEST (0x02F8) — 16 bytes
Handler: file 0x741A
```
Offset  Size  Type     Field
0       4     U32 BE   location_id
4       2     U16 BE   x_coord
6       2     U16 BE   y_coord
8       8     5B+3pad  status_block (via read_5_skip_3)
```
Clears party (sets count=1), copies player to slot 0, loads return location.

### SETPOS_REQUEST (0x01D4) — 2 bytes
Handler: file 0x74EE
```
Offset  Size  Type     Field
0       2     U16 BE   position_value (0=success → copy facing to party entry[+0x2E])
```

### SETPOS_REPLY (0x01D5) — 13 bytes
Handler: file 0x7532
```
Offset  Size  Type     Field
0       2     U16 BE   pos_value
2       2     U16 BE   param2
4       4     U32 BE   location_id
8       4     U32 BE   ref_data (target char ID)
12      1     U8       facing direction
```
Iterates party array (max 4 slots), sets facing on matching char ID.

### KNOWNMAP_NOTICE (0x01D2) — 2 bytes
Handler: file 0x6CDA
```
Offset  Size  Type     Field
0       2     U16 BE   map_flags (read but main effect is setting bit 2 of flag at 0x0605F432)
```

### SETCLOCK0_NOTICE (0x0248) — 4 + N*4 bytes
Handler: file 0x6CFA
```
HEADER:
Offset  Size  Type     Field
0       4     U32 BE   count (clamped to max 10)

PER ENTRY (4 bytes):
+0      1     U8       time_byte_0
+1      1     U8       time_byte_1
+2      1     U8       type (must be 1-3)
+3      1     --       padding
```
Stored at g_state+0xAD4A (3 bytes per entry), count at g_state+0xAD48.

### MONSTER_DEL_NOTICE (0x01DA) — 2 bytes
Handler: file 0x6DDC
```
Offset  Size  Type     Field
0       1     U8       (consumed but overwritten)
1       1     U8       monster_del_id (stored at g_state+0xAB10)
```

### MISSPARTY_NOTICE (0x0257) — VARIABLE (4 + member records)
Handler: file 0x6E98
```
HEADER:
Offset  Size  Type     Field
0       4     U32 BE   total_members

PER MEMBER (variable):
+0      4     U32 BE   char_id
+4      4     U32 BE   member_info (level, class, sub-count)
+8      1     U8       extra_byte
+9      var   bytes    sub_count * 16 bytes of visual data
```
Party sync notice. Display party at g_state+0x659C (76 bytes * 6 slots).

### CHAR_DISAPPEAR_NOTICE (0x01BC) — 4+ bytes
Handler: file 0x8C90
```
Offset  Size  Type     Field
0       4     U32 BE   disappear_data (char ID or position)
4+      var   bytes    additional event data
```
Ring buffer at g_state+0xD048 (max 0x400 entries), cursor at g_state+0xD044.
Only processes when game_mode (g_state+0xA4) == 6 and no transition active.

### CAMP_OUT_REQUEST (0x01B4) — 2 bytes
Handler: file 0x779A
```
Offset  Size  Type     Field
0       2     U16 BE   camp_status (0=success → trigger scene transition)
```

### CAMP_OUT_REPLY (0x01B5) — 2 bytes
Handler: file 0x77CC
```
Offset  Size  Type     Field
0       2     U16 BE   reply_data (unconditionally triggers scene transition)
```

### SETLEADER_REQUEST (0x01D7) — 2 bytes
Handler: file 0x75CC
```
Offset  Size  Type     Field
0       2     U16 BE   leader_status (0=approved → call set_leader_common)
```

### SETLEADER_REPLY (0x01D8) — 0 bytes
Handler: file 0x75FC. No payload read. Calls set_leader_common directly from state.

### SETLEADER_NOTICE (0x02D7) — 16 bytes
Handler: file 0x7608
```
Offset  Size  Type     Field
0       16    bytes    leader_data (memcpy to g_state+0xAE58)
```
Sets leader callback at 0x0605F424 = 0x0601C0A8, clears g_state+0xAE68.

### INQUIRE_LEADER_NOTICE (0x02D8) — 2 bytes
Handler: file 0x7632
```
Offset  Size  Type     Field
0       2     U16 BE   inquire_data
```

### ALLOW_SETLEADER_REQUEST (0x02DA) — 2 bytes
Handler: file 0x764E
```
Offset  Size  Type     Field
0       2     U16 BE   allow_data
```

---

## Party Member Entry Layout (164 = 0xA4 bytes)
```
Offset  Size  Field
+0      4     Character/entity ID
+4      4     Match/lookup key
+18     1     Move state (1=stand, 2=walk, 3=auto)
+20     1     Sub-mode
+21     1     Extra mode byte
+28     4     Location ID (0x1C)
+46     1     Facing direction (0x2E)
+102    2     X coordinate (0x66)
+104    2     Y coordinate (0x68)
+140    8     Status block (0x8C, 5+3 format)
```

## Key State Offsets (Movement/Map)
```
g_state+0x008A   1B  Global facing direction
g_state+0x008B   1B  Party membership flag (0=not in party)
g_state+0x00A4   1B  Game mode (6=field/map)
g_state+0x1B8C   4B  Current location ID
g_state+0x1B90   1B  Current party slot index
g_state+0x1BE0   656B Party array (4 slots * 164B)
g_state+0x1E7A   1B  Party member count
g_state+0x6598   1B  Display party count
g_state+0x659C   456B Display party (6 * 76B)
g_state+0x84B0   4B  Transition state (0=none)
g_state+0x8708   var Entity/NPC grid table (4B per cell)
g_state+0xAB10   1B  Monster deletion target
g_state+0xAD48   2B  Clock entry count
g_state+0xAD4A   30B Clock entries (10 * 3B)
g_state+0xAD78   var Local player struct
g_state+0xAE58   16B Leader info block
g_state+0xAE68   1B  Leader tracking byte
g_state+0xD044   4B  Disappear ring buffer cursor
g_state+0xD048   var Disappear ring buffer (0x400 entries)
```

---

## Common Patterns Observed

1. **Status/result gate**: Many handlers read a U16 at offset 0 and exit if non-zero
2. **16-byte names**: Character/item names are always 16 bytes, Shift-JIS, null-padded
3. **Interleaved flag bytes**: Control bytes at offsets 64-71 use skip-read-skip-read pattern
4. **parse_appearance** (0x0601A106): reads 8 bytes → char struct offsets 21-25, 46
5. **parse_status** (0x0601A1EA): reads 8 bytes → class (0-5), level (1-16)
6. **read_5_skip_3** (0x0601AAA2): reads 5 bytes + 3 padding = 8 bytes total
7. **Character struct**: 164 bytes (0xA4), array at game_state+0x1BE0
8. **Multi-page protocol**: Used for large data (CHARDATA_REPLY, CLASS_CHANGE_REPLY)

---

## Dice/Card Handlers (decompiled 2026-03-11 session 4)

### CAST_DICE_REQUEST (0x02D5) — 6 bytes
Handler: file 0x4348
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
--- if status == 0: ---
2       1     U8       dice_result (byte)
3       3     bytes    dice_data[3] (3 individual bytes)
```
Stores to party_entry+4 via local subroutine at 0x060143F6.
Sets g_state[0x90] = 1.

### CAST_DICE_REPLY (0x02D6) — 20 bytes consumed
Handler: file 0x43B0
```
Offset  Size  Type     Field
0       16    bytes    skipped (not read — possibly name/id)
16      1     U8       dice_result
17      3     bytes    dice_data[3]
```
Calls same subroutine 0x060143F6 to process dice data.
Clears target area via 0x0603FBC0 before processing.

### CARD_REQUEST (0x02DC) — 2 bytes
Handler: file 0x44CE
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
```
If status == 0: clears card area at g_state+0xF44A via 0x0603FBC0.

### CARD_REPLY (0x02DD) — 16+ bytes
Handler: file 0x4522
```
Offset  Size  Type     Field
0       16    bytes    card_data (memcpy → g_state+0xF44A)
```
Clears g_state[0xF45A] = 0. Then passes payload+16 to
continuation function at 0x0601454C for further card processing.

---

## Login/Misc Handlers (decompiled 2026-03-11 session 4)

### LOGOUT_REQUEST (0x0043) — 0 bytes
Handler: file 0x491C
No payload consumed. Clears context+16 via 0x0603FBC0.

### ACTION_CHAT_REQUEST (0x0260) — 2 bytes
Handler: file 0x428E
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
```
If status == 0: looks up party entry, modifies char[0x2C], clears g_state[0x1B91]=0xFF.

### ACTION_CHAT_REPLY (0x0261) — 17 bytes
Handler: file 0x42EE
```
Offset  Size  Type     Field
0       16    bytes    char_lookup_data (passed to 0x06019F52)
16      1     U8       action_byte (stored at found_char+44)
```
Calls char lookup at 0x06019F52 with payload[0..15], stores action byte at offset 44.

### ENCOUNTMONSTER_NOTICE (0x01CA) — 0 bytes
Handler: file 0x7BEC
No payload consumed. Sets g_state[0xF4B9] = 0.

---

## Party Handlers (decompiled 2026-03-11 session 4)

### PARTYEXIT_REPLY (0x01A9) — 20 bytes
Handler: file 0x4116
```
Offset  Size  Type     Field
0       16    bytes    leader_name (memcpy → g_state+0xAE58)
16      4     U32 BE   party_id (→ g_state+0x1E70)
```
Clears g_state[0xAE68] = 0. Matches name against party entry, adjusts
party state. Sets g_state[0x1E7A] = 1 (party count = 1).

### PARTYEXIT_NOTICE (0x0232) — 4 bytes
Handler: file 0x4252
```
Offset  Size  Type     Field
0       4     U32 BE   party_id (→ g_state+0x1E70 via read_u32)
```
Checks g_state[0x1E7A] > 1 (member count). Tail-calls 0x0601A2C0 for party update.

### PARTYENTRY_REQUEST (0x022B) — 4 bytes
Handler: file 0x5E8E
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   entry_param
```
Two read_u16 calls.

### PARTYENTRY_ACCEPT_REPLY (0x01A5) — 2+ bytes
Handler: file 0x5EB6
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
--- if status == 0: more processing ---
```

### PARTYENTRY_REPLY (0x01A6) — 16+ bytes
Handler: file 0x5EFE
```
Offset  Size  Type     Field
0       16    bytes    leader_name (memcpy → g_state+0xAE58)
```
Clears g_state[0xAE68] = 0. Then processes remaining payload from offset 16.

### PARTYENTRY_NOTICE (0x025A) — 16 bytes
Handler: file 0x5F36
```
Offset  Size  Type     Field
0       16    bytes    leader_name (memcpy → g_state+0xAE58)
```
Clears g_state[0xAE68] = 0. Sets callback at 0x0605F424 = 0x0601B98C.

### ALLOW_JOIN_REQUEST (0x01E7) — 2 bytes
Handler: file 0x5F90
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
```
Also stores msg_type 0x01E7 at 0x060610C2 (pending join tracking).

### CANCEL_JOIN_REQUEST (0x025C) — 2 bytes
Handler: file 0x5FB2. read_u16(context+4, payload) → rts.

### CANCEL_JOIN_REPLY (0x025D) — 2 bytes
Handler: file 0x5FCE. read_u16(stack, payload) → rts.

### CANCEL_JOIN_NOTICE (0x01B6) — VARIABLE
Handler: file 0x5FE6. Complex handler with r8-r14 pushed.
Loads g_state+0x339C and g_state+0x1BE0 (party array). Full party resync.

### PARTYUNITE_REQUEST (0x022F) — 4 bytes
Handler: file 0x63FA
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   unite_param
```

### PARTYUNITE_ACCEPT_REPLY (0x022D) — 2+ bytes
Handler: file 0x6444. read_u16(context+4, payload). If 0: more processing.

### PARTYUNITE_REPLY (0x022E) — 4+ bytes
Handler: file 0x648C
```
Offset  Size  Type     Field
0       4     U32 BE   unite_data (→ stack, via read_u32)
```
Then reads more data at g_state+0xAE7C. Complex party merge logic.

### PARTYUNITE_NOTICE (0x025E) — 4+ bytes
Handler: file 0x6584
```
Offset  Size  Type     Field
0       4     U32 BE   unite_data (→ stack, via read_u32)
```
Allocates 48 bytes stack. Complex loop with stride 0xAC (172 bytes per party member).

### ALLOW_UNITE_REQUEST (0x0231) — 4 bytes
Handler: file 0x65F4
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   unite_param
```

---

## Goto/Teleport/Area Handlers (decompiled 2026-03-11 session 4)

### GOTOLIST_REQUEST (0x019B) — VARIABLE (list)
Handler: file 0x492E. Complex handler — pushes r8-r14, reads data into
g_state+0xBC (188) area. Processes server list of available destinations.

### GOTOLIST_REPLY (0x0215) — VARIABLE (list)
Handler: file 0x4A08. Complex — pushes r8-r14, reads data at g_state+0xBC.
Reads at least u16 into stack+8, then further list processing.

### AREA_LIST_REQUEST (0x023C) — VARIABLE (list)
Handler: file 0x6622. Complex — pushes r8-r14. Processes list at g_state+0x7E6C.

### TELEPORTLIST_REQUEST (0x01B0) — VARIABLE (list)
Handler: file 0x66FA. Complex — pushes r8-r14. Processes list at g_state+0x8014.

### EXPLAIN_REQUEST (0x023F) — 4 bytes
Handler: file 0x67BA
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   explain_param
```

### TELEPORT_REQUEST (0x04E1) — 2 bytes
Handler: file 0x67E2. read_u16(context+4, payload) → rts.

### MIRRORDUNGEON_REQUEST (0x0234) — 2+ bytes
Handler: file 0x6814. Clears g_state+0x81E0 area = 0. Then read_u16(context+4, payload).
If status == 0: more processing.

### FINDUSER_REQUEST (0x01B8) — 2-6 bytes
Handler: file 0x4AC0
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
--- if status == 0: ---
2       4     U32 BE   user_data
```

### FINDUSER2_REQUEST (0x0241) — 2+ bytes
Handler: file 0x685C. read_u16(context+4, payload). If 0: processes data at
g_state+0x81B4 area with more reads.

### CLASS_LIST_REQUEST (0x0299) — 2 bytes
Handler: file 0x68C0. read_u16(context+4, payload) → rts.

### CLASS_CHANGE_REQUEST (0x029B) — VARIABLE
Handler: file 0x68F0. Complex — pushes r8-r14. Computes party entry from
g_state[0x1B90] * 0xA4 + g_state+0x1BE0. Reads g_state+0x0260 (char struct).

---

## Store/Sakaya Handlers (decompiled 2026-03-11 session 4)

### STORE_LIST_REQUEST (0x0270) — VARIABLE (list)
Handler: file 0x4AF4. Complex — pushes r8-r14, 36B stack. Reads list data.

### STORE_IN_REQUEST (0x0272) — 3 bytes
Handler: file 0x4BFE
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
--- if status == 0: ---
2       1     U8       store_flag (→ context+0xA0 as U16)
```

### STORE_IN_REPLY (0x0273) — 1 byte
Handler: file 0x4C2C
```
Offset  Size  Type     Field
0       1     U8       store_flag (→ context+0xA0 as U16)
```
Very simple: reads 1 byte, writes as u16.

### SAKAYA_LIST_REQUEST (0x020D) — VARIABLE
Handler: file 0x4C3A. Complex — clears 264-byte area (0x108) via 0x0603FEF0.
List processing handler for sakaya (tavern) room listing.

### SAKAYA_LIST_REPLY (0x0213) — VARIABLE
Handler: file 0x4D22. Same pattern as SAKAYA_LIST_REQUEST — clears 264B area.

### SAKABA_MOVE_REQUEST (0x0211) — 2+ bytes
Handler: file 0x4E30. read_u16(context+4, payload). If 0: more processing.

### SAKABA_MOVE_REPLY (0x0212) — 2 bytes
Handler: file 0x4E60
```
Offset  Size  Type     Field
0       2     U16 BE   move_data (read_u16 → context+0x6D9C)
```

### SAKAYA_IN_REQUEST (0x0217) — 4 bytes
Handler: file 0x4E7E
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   in_param
```

### SAKAYA_IN_REPLY (0x0218) — 2 bytes
Handler: file 0x4EA6. read_u16(stack, payload) → rts.

### SAKAYA_TBLLIST_REQUEST (0x01F9) — VARIABLE
Handler: file 0x4EC6. Complex — pushes r8-r14. Table list processing.

### SAKAYA_TBLLIST_REPLY (0x0214) — VARIABLE
Handler: file 0x4FCC. Complex — pushes r9-r14. Table list reply processing.

### SAKAYA_EXIT_REQUEST (0x01FB) — 2+ bytes
Handler: file 0x5060. read_u16(context+4, payload). If 0: more processing.

### SAKAYA_EXIT_REPLY (0x021B) — 4 bytes
Handler: file 0x50A4
```
Offset  Size  Type     Field
0       4     U32 BE   exit_data (via read_u32)
```

### SAKAYA_SIT_REQUEST (0x020F) — 4 bytes
Handler: file 0x50D0
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   sit_param
```

### SAKAYA_MEMLIST_REQUEST (0x024C) — 2+ bytes
Handler: file 0x5112. read_u16(context+4, payload). If 0: more processing.

### SAKAYA_MEMLIST_REPLY (0x024D) — VARIABLE
Handler: file 0x5152. Complex — pushes r8-r14. Member list processing.

### SAKAYA_FIND_REQUEST (0x024F) — 2+ bytes
Handler: file 0x5290. read_u16(context+4, payload). If 0: more processing.

### SAKAYA_STAND_REQUEST (0x021A) — 4 bytes
Handler: file 0x52CE
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   stand_param
```

### SET_SIGN_REQUEST (0x0246) — 4 bytes
Handler: file 0x52FA
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   sign_param
```

### SET_SIGN_REPLY (0x0247) — 56 bytes
Handler: file 0x533C
```
Offset  Size  Type     Field
0       16    bytes    skipped (not read by this handler)
16      40    bytes    sign_data (memcpy → g_state+0x74EC)
```
Clears g_state[0x7514] = 0.

### MOVE_SEAT_REQUEST (0x0255) — 4 bytes
Handler: file 0x538C
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   seat_param
```

### MOVE_SEAT_REPLY (0x0256) — VARIABLE
Handler: file 0x53B4. Complex — pushes r11-r14, 28B stack.
Calls 0x060402E0 then memcpy. Seat assignment processing.

### SET_SEKIBAN_REQUEST (0x0251) — 4 bytes
Handler: file 0x5436
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   sekiban_param
```

---

## BBS/News/Dir Handlers (decompiled 2026-03-11 session 4)

### DIR_REQUEST (0x029E) — VARIABLE (list)
Handler: file 0x58E8. Complex — pushes r8-r14. Directory listing.

### SUBDIR_REQUEST (0x02A0) — VARIABLE (list)
Handler: file 0x59AE. Complex — pushes r8-r14. Subdirectory listing.

### MEMODIR_REQUEST (0x02A2) — VARIABLE (list)
Handler: file 0x5A78. Complex — pushes r8-r14. Memo directory listing.

### NEWS_READ_REQUEST (0x02A4) — VARIABLE
Handler: file 0x5BB0. read_u16(context+4, payload), then list processing.

### NEWS_WRITE_REQUEST (0x02A6) — 2 bytes
Handler: file 0x5C4C. read_u16(context+4, payload) → rts.

### NEWS_DEL_REQUEST (0x02A8) — 2 bytes
Handler: file 0x5C68. read_u16(context+4, payload) → rts.

### BB_MKDIR_REQUEST (0x02B2) — 2 bytes
Handler: file 0x5C84. read_u16(context+4, payload) → rts.

### BB_RMDIR_REQUEST (0x02B4) — 2 bytes
Handler: file 0x5CA0. read_u16(context+4, payload) → rts.

### BB_MKSUBDIR_REQUEST (0x02B6) — 2 bytes
Handler: file 0x5CBC. read_u16(context+4, payload) → rts.

### BB_RMSUBDIR_REQUEST (0x02B8) — 2 bytes
Handler: file 0x5CD8. read_u16(context+4, payload) → rts.

---

## Movement/Camp Handlers (decompiled 2026-03-11 session 4)

### MOVE1_REQUEST (0x01C4) — 4+ bytes
Handler: file 0x717A. Three read_u16 calls sequentially. At minimum 6 bytes.

### CAMP_IN_REQUEST (0x01AD) — 2 bytes
Handler: file 0x7360
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
```
If status == 0: tail-calls 0x0601A4F4(r4=payload, r5=1) for camp entry.

### CAMP_IN_REPLY (0x01AE) — 2 bytes
Handler: file 0x7392. read_u16(stack, payload). Calls 0x0601A4F4(r4=result, r5=1).

---

## Equipment/Skill/Para Handlers (decompiled 2026-03-11 session 4)

### EQUIP_REQUEST (0x0205) — 2 bytes
Handler: file 0x77EC. read_u16(context+4, payload) → rts.

### DISARM_REQUEST (0x026D) — 2 bytes
Handler: file 0x780C. read_u16(context+4, payload) → rts.

### USE_SKILL_REQUEST (0x02E9) — 2 bytes
Handler: file 0x7832. read_u16(context+4, payload) → rts.

### USE_SKILL_REPLY (0x02EA) — VARIABLE
Handler: file 0x7870. Complex — pushes r8-r14, 16B stack. Full skill effect processing.

### CHANGE_PARA_REQUEST (0x02F6) — 2 bytes
Handler: file 0x79F0. read_u16(context+4, payload) → rts.

### CHANGE_PARA_REPLY (0x0242) — 4 bytes
Handler: file 0x7A0C
```
Offset  Size  Type     Field
0       1     U8       byte_0 (→ g_state+0xAD6B)
1       1     U8       byte_1 (→ g_state+0xAD6A)
2       1     U8       byte_2 (→ g_state+0xAD68)
3       1     U8       byte_3 (→ g_state+0xAD69)
```
Reads 4 individual bytes stored to non-sequential offsets (reverse order).

---

## Event Handlers (decompiled 2026-03-11 session 4)

### BTLJOIN_NOTICE (0x01C7) — 16 bytes
Handler: file 0x8828
```
Offset  Size  Type     Field
0       1     U8       btl_flag_0 (→ g_state+0xABA6)
1       1     U8       btl_flag_1 (→ g_state+0xABA7)
2       2     U16 BE   btl_param (→ stack)
4       2     U16 BE   event_type (→ g_state+0xAB18)
6       2     U16 BE   event_id (→ g_state+0xAB1A)
8       8     bytes    event_data (memcpy → g_state+0xAB1C)
```

### EXEC_EVENT_REQUEST (0x01D0) — 8+N bytes
Handler: file 0x887A
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       2     U16 BE   event_id (→ g_state+0xAB1A)
4       4     U32 BE   data_size
8       N     bytes    event_data (memcpy → g_state+0xAB1C, N=data_size)
```

### EXEC_EVENT_REPLY (0x01D1) — 8+N bytes (N clamped to max 4)
Handler: file 0x88EC
```
Offset  Size  Type     Field
0       2     U16 BE   event_id (→ g_state+0xAB1A)
2       2     --       skipped
4       4     U32 BE   data_size (clamped to max 4)
8       N     bytes    event_data (memcpy → g_state+0xAB1C, N=min(data_size,4))
```

### EXEC_EVENT_NOTICE (0x02EF) — VARIABLE
Handler: file 0x8932. Checks g_state[0xABA4] >= 32. If so: calls 0x06020EB8.
Complex event queue processing.

### EVENT_EFFECT_NOTICE (0x02F0) — VARIABLE
Handler: file 0x8A78. Complex — pushes r8-r14, 104B stack. Reads data at
g_state+0xAB1A. Full event effect processing with visual/sound triggers.

### WAIT_EVENT_NOTICE (0x02F1) — 16+ bytes
Handler: file 0x8BD4
```
Offset  Size  Type     Field
0       16    bytes    event_context (memcpy → stack, then processed)
```
Computes party_entry from g_state[0x1B90] * 0xA4 + g_state+0x1BE0.
Allocates 36B stack. Full event waiting logic.

### EVENT_ITEM_NOTICE (0x01C6) — 3 bytes
Handler: file 0x8E22
```
Offset  Size  Type     Field
0       1     U8       item_byte_0 (→ g_state+0xABA8)
1       1     U8       item_byte_1 (→ g_state+0xABA9)
2       1     U8       item_byte_2 (→ g_state+0xABAA)
```
Validates g_state[0x1E78] in range [1..4]. If invalid: sets to 1 and calls UI function.

---

## Trade/Use Handlers (decompiled 2026-03-11 session 4)

### GIVE_ITEM_REQUEST (0x0294) — 2 bytes
Handler: file 0x8E5A. read_u16(context+4, payload) → rts.

### USE_REQUEST (0x02D1) — 2 bytes
Handler: file 0x9090. bsr read_u16(context+4, payload) → rts.

### USE_REPLY (0x02D3) — VARIABLE (16+)
Handler: file 0x90D8. Complex — pushes r8-r14, 92B stack.
Copies 16 bytes from payload → g_state+0xDB8C area. Then further processing.

### SELL_REQUEST (0x028D) — 2 bytes
Handler: file 0x92D8. bsr read_u16(context+4, payload) → rts.

### SELL_REPLY (0x028C) — 39 bytes
Handler: file 0x92F2
```
Offset  Size  Type     Field
0       16    bytes    item_name_1 (memcpy → g_state+0xDB60)
16      16    bytes    item_name_2 (memcpy → g_state+0xDB71)
32      4     U32 BE   gold_amount (→ g_state+0xDB84)
36      2     U16 BE   trade_param (→ g_state+0xDB88)
38      1     U8       trade_flag (→ g_state+0xDB8A)
```
Clears g_state[0xDB70] = 0 and g_state[0xDB81] = 0.
Sets callback at 0x0605F424 = 0x0601BEC2.

### BUY_REQUEST (0x028F) — 2 bytes
Handler: file 0x9358. bsr read_u16(context+4, payload) → rts.

### BUY_REPLY (0x028A) — 2 bytes
Handler: file 0x9372. bsr read_u16(stack, payload) → rts.

### TRADE_DONE_NOTICE (0x028B) — 0 bytes
Handler: file 0x93C0. No payload consumed. Calls 0x06018FB8(0) internally.
Updates party_entry gold: party_entry[0x1C] -= g_state[0xDB84].

### TRADE_CANCEL_REQUEST (0x0291) — 2 bytes
Handler: file 0x93F4. bsr read_u16(context+4, payload) → rts.

### TRADE_CANCEL_REPLY (0x0292) — 2 bytes
Handler: file 0x940E. read_u16(stack, payload) → rts.

---

## Compound/Level/Skill Handlers (decompiled 2026-03-11 session 4)

### COMPOUND_REQUEST (0x02EE) — VARIABLE
Handler: file 0x9430. Complex — pushes r8-r14, 16B stack.
Reads g_state+0x0260. Item compounding/crafting logic.

### CONFIRM_LVLUP_REQUEST (0x0276) — 6 bytes
Handler: file 0x95B8
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       4     U32 BE   levelup_data (→ g_state+0xAE98)
```

### LEVELUP_REQUEST (0x0278) — 6+ bytes
Handler: file 0x95E4
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
2       4     U32 BE   levelup_data (→ g_state+0xAE98)
--- if status == 0: more processing via 0x06019F1C, 0x0601A3B0 ---
```
Complex: computes party_entry, calls multiple helper functions for
class/stat/skill updates. Additional bytes consumed by helper functions.

### SKILL_LIST_REQUEST (0x02BA) — 2 bytes
Handler: file 0x969C
```
Offset  Size  Type     Field
0       2     U16 BE   status (→ context+4)
```
If status == 0: calls 0x0601A5E2 for skill list rendering.

### LEARN_SKILL_REQUEST (0x02E1) — 2 bytes
Handler: file 0x96C4. read_u16(context+4, payload) → rts.

### SKILLUP_REQUEST (0x02E3) — 2 bytes
Handler: file 0x96F8. read_u16(context+4, payload) → rts.

### EQUIP_SKILL_REQUEST (0x02E5) — 2 bytes
Handler: file 0x9718. read_u16(context+4, payload) → rts.

### DISARM_SKILL_REQUEST (0x02E7) — 2 bytes
Handler: file 0x9738. read_u16(context+4, payload) → rts.

### SEL_THEME_REQUEST (0x0269) — 2 bytes
Handler: file 0x9758. read_u16(context+4, payload) → rts.

### CHECK_THEME_REQUEST (0x026B) — 2 bytes
Handler: file 0x9772. read_u16(context+4, payload) → rts.

---

## Mail/Colo Handlers (decompiled 2026-03-11 session 4)

### MAIL_LIST_REQUEST (0x02AA) — VARIABLE
Handler: file 0x978C. Complex mail list processing.

### GET_MAIL_REQUEST (0x02AC) — VARIABLE
Handler: file 0x98AA. Complex mail content retrieval.

### SEND_MAIL_REQUEST (0x02AE) — 2 bytes
Handler: file 0x9986. read_u16(context+4, payload) → rts.

### DEL_MAIL_REQUEST (0x02B0) — 2 bytes
Handler: file 0x99A0. read_u16(context+4, payload) → rts.

### COLO_WAITING_REQUEST (0x02BC) — 2 bytes
Handler: file 0x9A08. read_u16(context+4, payload) → rts.

### COLO_WAITING_REPLY (0x02BD) — 2 bytes
Handler: file 0x9A22. read_u16(context+4, payload) → rts.

### COLO_EXIT_REQUEST (0x02BF) — 2 bytes
Handler: file 0x9A38. read_u16(context+4, payload) → rts.

### COLO_EXIT_REPLY (0x02C0) — 2 bytes
Handler: file 0x9A52. read_u16(context+4, payload) → rts.

### COLO_LIST_REQUEST (0x02C2) — VARIABLE
Handler: file 0x9A68. Complex colosseum list processing.

### COLO_ENTRY_REQUEST (0x02C4) — 2+ bytes
Handler: file 0x9B40. read_u16 + more processing.

### COLO_ENTRY_REPLY (0x02EB) — 2 bytes
Handler: file 0x9B6A
```
Offset  Size  Type     Field
0       1     U8       entry_byte_0 (→ g_state+0xF123)
1       1     U8       entry_byte_1 (→ g_state+0xF122)
```

### COLO_CANCEL_REQUEST (0x02C6) — 2 bytes
Handler: file 0x9B7C. read_u16(context+4, payload) → rts.

### COLO_CANCEL_NOTICE (0x02C7) — 1 byte
Handler: file 0x9B9A
```
Offset  Size  Type     Field
0       1     U8       cancel_flag (→ g_state+0xF123)
```
Also checks g_state[0xF4B9].

### COLO_FLDENT_REQUEST (0x02C9) — 2 bytes
Handler: file 0x9BE0. read_u16(context+4, payload) → rts.

### COLO_FLDENT_REPLY (0x02CF) — VARIABLE
Handler: file 0x9BFA. Complex field entry reply.

### COLO_FLDENT_NOTICE (0x02CC) — VARIABLE
Handler: file 0x9C10. Complex field entry notice.

### COLO_RANKING_REQUEST (0x02CE) — VARIABLE
Handler: file 0x9C46. Complex ranking list processing.

### COLO_RANKING_REPLY (0x02F2) — VARIABLE
Handler: file 0x9D42. Complex ranking reply.

---

## Key State Offsets (Session 4 Additions)
```
g_state+0x0090   1B  Action flag (set by dice/ESP handlers)
g_state+0x0091   1B  ESP state flag
g_state+0x008F   1B  Action chat state flag
g_state+0x00A0   2B  Store/room ID (16-bit)
g_state+0x00BC   var  Goto/destination list data
g_state+0x1930   1B  Party slot counter (for exits)
g_state+0x1932   var  Level-up char data area
g_state+0x1E70   4B  Party ID
g_state+0x1E78   1B  Event item validation (must be 1-4)
g_state+0x339C   var  Party sync data
g_state+0x6D9C   2B  Sakaba move target
g_state+0x74EC   40B  Sign data
g_state+0x7514   1B  Sign clear flag
g_state+0x7CA0   var  Party list display data
g_state+0x7E6C   var  Area list data
g_state+0x8014   var  Teleport list data
g_state+0x81B4   var  Find user data
g_state+0x81E0   var  Mirror dungeon data
g_state+0xAB18   2B  Event type
g_state+0xAB1A   2B  Event ID
g_state+0xAB1C   var  Event data block
g_state+0xABA4   1B  Event queue count
g_state+0xABA6   1B  BTL join flag 0
g_state+0xABA7   1B  BTL join flag 1
g_state+0xABA8   1B  Event item byte 0
g_state+0xABA9   1B  Event item byte 1
g_state+0xABAA   1B  Event item byte 2
g_state+0xAD68   1B  Para byte (stored from payload[2])
g_state+0xAD69   1B  Para byte (stored from payload[3])
g_state+0xAD6A   1B  Para byte (stored from payload[1])
g_state+0xAD6B   1B  Para byte (stored from payload[0])
g_state+0xAE98   4B  Level-up data
g_state+0xDB60   16B  Trade item name 1
g_state+0xDB70   1B  Trade item clear 1
g_state+0xDB71   16B  Trade item name 2
g_state+0xDB81   1B  Trade item clear 2
g_state+0xDB84   4B  Trade gold amount
g_state+0xDB88   2B  Trade param
g_state+0xDB8A   1B  Trade flag
g_state+0xDB8C   var  Use item data
g_state+0xF122   1B  Colo entry byte 1
g_state+0xF123   1B  Colo entry/cancel byte
g_state+0xF44A   16B  Card data
g_state+0xF45A   1B  Card clear flag
g_state+0xF4B9   1B  BTL/Colo state flag
```

---

## Updated EMPTY Handlers (24 total — just rts, no payload read)
0x01B9 CURREGION_NOTICE, 0x01A1 USERLIST_REQUEST, 0x021C USERLIST_REPLY,
0x021E SAKAYA_STAND_REPLY, 0x0252 SET_SEKIBAN_REPLY, 0x0253 SET_SEKIBAN_NOTICE,
0x0249 EVENT_MAP_NOTICE, 0x024A MONSTER_MAP_NOTICE, 0x01DB VISION_NOTICE,
0x01DC OBITUARY_NOTICE, 0x0263 EQUIP_REPLY, 0x026E DISARM_REPLY,
0x0220 BTL_MEMBER_NOTICE, 0x0225 BTL_CHGMODE_REQUEST, 0x0228 BTL_END_NOTICE,
0x0229 BTL_MASK_NOTICE, 0x0297 BTL_EFFECTEND_REQUEST, 0x0236 BTLJOIN_REQUEST,
0x0237 BTLJOIN_REPLY, 0x02EC COLO_CANCEL_REPLY,
0x0043 LOGOUT_REQUEST (clears state only), 0x01CA ENCOUNTMONSTER_NOTICE (clears flag only),
0x028B TRADE_DONE_NOTICE (internal state only, no payload)

---

## Session 5 Deep-Dive: List-Processing Handlers (FULLY DECOMPILED)

### GOTOLIST_REQUEST (0x019B) — 8 + N*28 bytes
Handler: file 0x492E
```
HEADER (8 bytes):
Offset  Size  Type     Field
0       2     U16 BE   result_code (0=success, nonzero=error → exit)
2       2     U16 BE   entry_count (→ g_state+0xB8)
4       4     U32 BE   page_token (stack local)

PER ENTRY (28 bytes on wire, stored as 28 bytes at g_state+0xBC + i*28):
+0      4     U32 BE   char_id         → entry[0..3]
+4      2     U16 BE   zone_id         → entry[4..5]
+6      2     U16 BE   map_id          → entry[6..7]
+8      2     U16 BE   position        → entry[8..9]
+10     1     U8       type_flag       → entry[10]
+11     1     --       padding (skipped)
+12     16    bytes    char_name       → entry[11..26]
                                       entry[27] = 0 (null-terminated)
```
Max ~14 entries. Storage: g_state+0xBC, 28 bytes per slot.

### GOTOLIST_REPLY (0x0215) — 8 + N*28 bytes
Handler: file 0x4A08
Identical per-entry layout to GOTOLIST_REQUEST.
Difference: first u16 NOT checked (always processes). Max ~18 entries.
Same storage at g_state+0xBC.

### STORE_LIST_REQUEST (0x0270) — 8 + N*20 bytes
Handler: file 0x4AF4
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   entry_count
4       4     U32 BE   unknown (read to advance pointer)

PER ENTRY (20 bytes on wire, stored as 22 bytes):
+0      16    bytes    item_data       → slot[0..15]
+16     1     U8       slot_index      (determines which of 12 dest slots)
+17     1     U8       attribute_a     → slot[18]
+18     1     U8       packed_field    low nibble-1 → slot[19], high nibble → slot[21]
+19     1     U8       attribute_b     → slot[20]
```
Storage: g_state+0x6C94, 264 bytes total (12 slots × 22 bytes).
Cleared with memset(0, 264) before processing. No validation.

### AREA_LIST_REQUEST (0x023C) — 8 + N*20 bytes
Handler: file 0x6622
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   entry_count (total in payload)
4       4     U32 BE   unknown (stack local)

PER ENTRY (20 bytes on wire):
+0      1     U8       type/status (must be 0x21 to pass validation)
+1      19    bytes    area_data
```
Entries filtered by validation at 0x0601AB14 (checks byte[0]==0x21 + table lookup).
Storage: g_state+0x7E6C. Count at dest[0..1], entries at dest+2, 21 bytes each
(20B data + 1B null flag).

### TELEPORTLIST_REQUEST (0x01B0) — 12 + N*20 bytes
Handler: file 0x66FA
```
HEADER (12 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   field_6 (→ dest+6)
4       2     U16 BE   entry_count
6       2     --       skipped
8       4     U32 BE   unknown (stack local)

PER ENTRY (20 bytes on wire):
+0      1     U8       type (must be 0x21 for validation)
+1      17    bytes    teleport_data
+18     1     U8       extra_type (stored in separate table at dest+0x186)
+19     1     --       skipped
```
Storage: g_state+0x8014. Count at dest[8..9], entries at dest+10, 19 bytes each.
Extra type table at dest+0x186 (1 byte per accepted entry). Max 20 entries.

### PARTYLIST_REQUEST (0x01A3) — 12 + N*72 bytes
Handler: file 0x5D1C
```
HEADER (12 bytes):
0       2     U16 BE   result_code (0=success)
2       2     U16 BE   unknown_field (stack local)
4       4     U32 BE   num_members (clamped to max 6)
8       4     U32 BE   unknown_u32 (stack local)

PER MEMBER (72 bytes on wire):
+0      2     U16 BE   member_info (low byte → status)
+2      2     U16 BE   unknown (read but not stored)
+4      4     U32 BE   member_id
+8      16    bytes    name_block_0 (char name part 1)
+24     16    bytes    name_block_1 (char name part 2)
+40     16    bytes    name_block_2 (char name part 3)
+56     16    bytes    name_block_3 (char name part 4)
```
Storage: g_state+0x7CA0 (count at [0..1]), entries at +4, 76 bytes each:
[0..3]=member_id, [4]=status_byte, [5..20]=name0+null, [22..37]=name1+null,
[38..53]=name2+null, [54..69]=name3+null.
Post-loop: if g_state[0x8B] set, filters entries via string search at 0x0601AABC.

### CANCEL_JOIN_NOTICE (0x01B6) — 8 + N*128 bytes
Handler: file 0x5FE6
Complex party resync handler.
```
HEADER (8 bytes):
0       2     U16 BE   result_code (→ g_state+4)
2       2     U16 BE   num_members (remaining party size)
4       4     U32 BE   context_id (stored but unused)

PER MEMBER (128 bytes):
+0      4     U32 BE   member_id
+4      16    bytes    character_name
+20     8     bytes    char_attributes_A (via 0x0601A1EA: class, level, etc.)
+28     4     U32 BE   field_1C (exp/HP)
+32     4     U32 BE   field_20 (gold/MP)
+36     8     bytes    char_attributes_B (via 0x0601A106: appearance)
+44     8     bytes    visual_data (via read_5_skip_3)
+52     38    19×U16   stat_array_1 (base stats)
+90     38    19×U16   stat_array_2 (current stats)
```
Stores into 164-byte party entries at g_state+0x1BE0 + i*0xA4.
For own character (matching g_state[0x260]): stats go to g_state+0x1B92 first.
Post-parse: removes departing member from room table (5 rooms × 3 slots).

---

## Session 5 Deep-Dive: Sakaya/BBS Handlers (FULLY DECOMPILED)

### SAKAYA_LIST_REQUEST (0x020D) — 8 + N*20 bytes
Handler: file 0x4C3A
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   entry_count
4       4     U32 BE   unknown

PER ENTRY (20 bytes, stored as 22 bytes):
+0      16    bytes    item_data → slot[0..15]
+16     1     U8       slot_index (determines dest slot)
+17     1     U8       attr_a → slot[18]
+18     1     U8       packed (low nibble-1 → slot[19], high → slot[21])
+19     1     U8       attr_b → slot[20]
```
Storage: g_state+0x6C94, 264B (12 slots × 22B). Same as STORE_LIST.

### SAKAYA_LIST_REPLY (0x0213) — 8 + N*20 bytes
Handler: file 0x4D22. Same wire format as SAKAYA_LIST_REQUEST.
Same storage at g_state+0x6C94. Zeroes unused slots after loop.

### SAKAYA_TBLLIST_REQUEST (0x01F9) — 12 + N*64 bytes
Handler: file 0x4EC6
```
HEADER (12 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   entry_count
4       2     U16 BE   unknown_1
6       2     U16 BE   unknown_2
8       4     U32 BE   unknown

PER ENTRY (64 bytes on wire, stored as 48 bytes at g_state+0x6DA8 + i*48):
+0      16    bytes    table_name
+16     16    bytes    owner_name
+32     16    bytes    description
+48     16    bytes    extra_data
```
Max 10 entries. Storage: g_state+0x6DA8, 48 bytes per entry.

### SAKAYA_TBLLIST_REPLY (0x0214) — 8 + N*4 bytes
Handler: file 0x4FCC
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4)
2       2     U16 BE   entry_count
4       4     U32 BE   unknown

PER ENTRY (4 bytes): table ID data only, marks entry[45]=1 (occupied).
```
Storage: g_state+0x6DA8 (shared with TBLLIST_REQUEST). Max 10 entries.

### SAKAYA_MEMLIST_REPLY (0x024D) — 8 + N*~24+ bytes (VARIABLE)
Handler: file 0x5152
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4)
2       2     U16 BE   entry_count
4       4     U32 BE   unknown

PER ENTRY (~24+ bytes, stored as 172 bytes at g_state+0x6F8C + i*172):
Parsed by helper functions (appearance, stats, visual data).
```
Max 8 members.

### DIR_REQUEST (0x029E) — 8 + N*44 bytes
Handler: file 0x58E8
```
HEADER (8 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       1     U8       result_byte → stack (extended to u16)
3       1     --       padding
4       4     U32 BE   unknown

PER ENTRY (44 bytes on wire, stored as 46 bytes):
+0      1     U8       type (must be 0x21 for validation)
+1      43    bytes    dir_data
```
Validated by 0x0601AB14. Storage: g_state+0xB37A, 46 bytes per entry (44+flag+null).

### SUBDIR_REQUEST (0x02A0) — 8 + N*44 bytes
Handler: file 0x59AE
Nearly identical to DIR_REQUEST. Same storage at g_state+0xB37A.
Difference: header byte at offset 2 is read as u16 (not single byte).

### MEMODIR_REQUEST (0x02A2) — 12 + N*66 bytes
Handler: file 0x5A78
```
HEADER (12 bytes):
0       2     U16 BE   status (→ g_state+4, 0=success)
2       2     U16 BE   area_id (→ g_state+0xBEFA)
4       2     U16 BE   entry_count (→ g_state+0xBEFC)
6       2     --       skipped
8       4     U32 BE   data_id

PER ENTRY (66 bytes on wire, stored as 68 bytes at g_state+0xBF00 + i*68):
+0      2     U16 BE   memo_id → entry[0..1]
+2      16    bytes    sender_name → entry[2..17]
                       entry[18] = 0 (read flag)
+18     2     U16 BE   date/id → entry[20..21]
+20     1     U8       byte_0 → entry[22]
+21     1     U8       byte_1 → entry[23]
+22     1     U8       byte_2 → entry[24]
+23     1     U8       byte_3 → entry[25]
+24     2     --       skipped
+26     40    bytes    memo_subject → entry[26..65]
                       entry[66] = 0 (flag)
```

### NEWS_READ_REQUEST (0x02A4) — 64 + body_len bytes
Handler: file 0x5BB0
```
0       2     U16 BE   error_code (0=success)
2       2     U16 BE   article_id (→ g_state+0xD014)
4       1     U8       date_0 (→ g_state+0xD016)
5       1     U8       date_1 (→ g_state+0xD017)
6       1     U8       date_2 (→ g_state+0xD018)
7       1     U8       date_3 (→ g_state+0xD019)
8       16    bytes    author_name (→ g_state+0xD002, null at g_state+0xD012)
24      40    bytes    subject (→ g_state+0xD01A, null at g_state+0xD042)
64      N     bytes    body_text (→ g_state+0xD048, byte-by-byte, max 799, null-terminated)
```

---

## Session 5 Deep-Dive: Complex Handlers (FULLY DECOMPILED)

### ESP_REQUEST (0x006F) — 36+ bytes
Handler: file 0x3E50
```
0       2     U16 BE   result_code (→ g_state+4)
2       2     U16 BE   unknown (→ stack local)
4       16    bytes    name/text (memcpy, null-terminated at byte 15)
20      18+   bytes    additional data (→ sub-handler at 0x06011D8A → 0x0601218C)
```
Sets g_state[0x91]=1. Branch: if result_code==0: success path (ESP process).
If nonzero: error path (display 16-byte name as error message).

### USE_SKILL_REPLY (0x02EA) — 24 + N*28 bytes
Handler: file 0x7870
```
HEADER (24 bytes):
0       2     U16 BE   result_code (→ g_state+4)
2       2     U16 BE   target_entity_id (→ g_state+0xF45C)
4       16    bytes    skill_visual_data (→ g_state+0xF45F, null at g_state+0xF46F)
20      2     U16 BE   num_targets (byte → g_state+0xF45E)
22      2     U16 BE   unknown

PER TARGET (28 bytes):
+0      16    bytes    target_id_data (→ g_state+0xF470 + slot*17)
+16     2     U16 BE   stat_value_1 (→ target+102)
+18     2     U16 BE   stat_value_2 (→ target+104)
+20     8     bytes    stat_block (5+3 via read_5_skip_3 → target+140)
```

### USE_REPLY (0x02D3) — 44 + N*64 bytes
Handler: file 0x90D8
```
HEADER (44 bytes):
0       16    bytes    item_base_data (→ g_state+0xDB8C[0..15])
16      16    bytes    item_ext_data (→ g_state+0xDB8C[17..32])
32      1     U8       field_34 → item_state[34]
33      1     U8       field_35 → item_state[35]
34      1     U8       num_slots (loop count) → item_state[40]
35      1     U8       field_36 → item_state[36]
36      2     U16 BE   field_38 → item_state[38..39]
38      6     --       skipped

PER SLOT (64 bytes):
+0      16    bytes    slot_base_data
+16     1     U8       slot_type_1 → slot+17
+17     1     U8       slot_type_2 → slot+18
+18     38    19×U16   stat_values → slot+24..slot+61
+56     8     bytes    extended_stats (5+3 via read_5_skip_3 → slot+19..23)
```
Slots stored at item_state+42 + i*62 (62 bytes per slot).

### COMPOUND_REQUEST (0x02EE) — 56 bytes (active portion)
Handler: file 0x9430
```
0       2     U16 BE   result_code (0=success)
2       2     U16 BE   item_id
4       2     U16 BE   item_param (byte from high byte)
6       2     U16 BE   quantity
8       16    bytes    item_name_data (→ inventory slot[4..19])
24      4     U32 BE   compound_value (→ compound struct)
28      1     U8       compound_type_1 → slot[3]
29      1     U8       compound_type_2 → compound_data+8
30      2     U16 BE   compound_stat
32      1     U8       attr_1 → data+3
33      1     U8       attr_2 → data+2
34      1     U8       attr_3 → data+4
35      1     U8       attr_4 → data+6
36      1     U8       attr_5 → data+5
37      1     U8       attr_6 → data+7
38      2     --       skipped
40      16    8×U16    compound_stats[0..7]
```
Inventory at g_state+0x260+0x0C88, 22 bytes per slot, max 100 slots.
Uses item lookup helper at 0x0601A374.

### LEVELUP_REQUEST (0x0278) — 48 bytes (active portion)
Handler: file 0x95E4
```
0       2     U16 BE   result_code (0=success)
2       2     --       skipped
4       4     U32 BE   experience_threshold (→ g_state+0xAE98)
8       38    19×U16   new_base_stats (via read_19_u16 → g_state+0x260+0x1932)
46      2     --       trailing (consumed by helper)
```
After parse: calls stat recalc (0x0601A3B0), recompute (0x0601A328),
copies 19 stats from char_base+102 to char_base+64, increments level at char_base+25.

### CLASS_CHANGE_REQUEST (0x029B) — 68 bytes (active portion)
Handler: file 0x68F0
```
0       2     U16 BE   result_code (0=success)
2       2     --       skipped
4       8     bytes    class_change_block (via 0x0601A1EA):
                       [+2]=new_class(0-5), [+7]=new_level(1-16)
12      16    8×U16    skill_slot_data (→ g_state+0x1780)
28      38    19×U16   new_base_stats (via read_19_u16 → g_state+0x260+0x1932)
66      2     --       trailing
```
After parse: recalc stats, copies effective stats, tail-calls finalization at 0x0603AD2C.

---

## Session 5 Deep-Dive: Mail/Colo Handlers (FULLY DECOMPILED)

### MAIL_LIST_REQUEST (0x02AA) — 12 + N*19 bytes
Handler: file 0x978C
```
HEADER (12 bytes):
0       2     U16 BE   error_code (→ g_state+4, nonzero → store 0 at g_state+0xD44A)
2       2     U16 BE   mail_count (→ g_state+0xD44A)
4       1     U8       page_indicator
5       1     U8       has_more_flag
6       2     U16 BE   unknown
8       4     U32 BE   unknown

PER ENTRY (19 bytes, stored at g_state+0xD450 + i*19):
+0      1     U8       status_byte_0
+1      1     U8       status_byte_1
+2      16    bytes    sender/subject
+18     1     --       null terminator (cleared to 0)
```
Pagination: if page_indicator >= has_more_flag → done (state=2), else more (state=1).
Cumulative count at g_state+0xD44C. Max ~4 entries per page.

### GET_MAIL_REQUEST (0x02AC) — 94 + body_len bytes
Handler: file 0x98AA
```
0       2     U16 BE   error_code
2       1     U8       mail_type_0 (→ g_state+0xDB00)
3       1     U8       mail_type_1 (→ g_state+0xDB01)
4       16    bytes    sender_name (→ g_state+0xDB02, null at +0xDB12)
20      2     U16 BE   timestamp (hi*100+lo → g_state+0xDB14)
22      1     U8       date_0 (→ g_state+0xDB16)
23      1     U8       date_1 (→ g_state+0xDB17)
24      1     U8       date_2 (→ g_state+0xDB18)
25      1     U8       date_3 (→ g_state+0xDB19)
26      40    bytes    subject (→ g_state+0xDB1A, null at +0xDB42)
66      1     U8       attachment_flag (→ g_state+0xDB46)
67      2     U16 BE   unknown
69      1     --       skip
70      16    bytes    attachment_name (→ g_state+0xDB47, null at +0xDB57)
86      4     U32 BE   body_offset (→ g_state+0xDB58)
90      4     U32 BE   body_length (→ g_state+0xDB5C)
94      N     bytes    body_text (memcpy N bytes → g_state+0xD048)
```

### COLO_LIST_REQUEST (0x02C2) — 8 + N*38 bytes
Handler: file 0x9A68
```
HEADER (8 bytes):
0       2     U16 BE   error_code (→ g_state+4)
2       1     U8       entry_count (→ g_state+0xEE00)
3       1     --       padding
4       4     U32 BE   unknown

PER ENTRY (38 bytes on wire, stored as 40 bytes at g_state+0xEE02 + i*40):
+0      1     U8       flag_0 → entry[0]
+1      1     U8       flag_1 → entry[1]
+2      1     U8       type_0 → entry[2]
+3      1     U8       type_1 → entry[3]
+4      16    bytes    name1 → entry[4..19], entry[20]=0
+20     16    bytes    name2 → entry[21..36], entry[37]=0
+36     2     U16 BE   score → entry[38..39]
```

### COLO_FLDENT_REPLY (0x02CF) — 2 bytes
Handler: file 0x9BFA. Just read_u16 to stack local. Acknowledgement only.

### COLO_FLDENT_NOTICE (0x02CC) — 6 bytes
Handler: file 0x9C10
```
0       1     U8       byte0 → g_state+0xF124
1       1     U8       byte1 → g_state+0xF125
2       2     U16 BE   field_a → g_state+0xF126
4       2     U16 BE   field_b → g_state+0xF128
```

### COLO_RANKING_REQUEST (0x02CE) — 8 + N*72 bytes
Handler: file 0x9C46
```
HEADER (8 bytes):
0       2     U16 BE   error_code (→ g_state+4)
2       1     U8       ranking_type (→ g_state+0xF12A)
3       1     U8       entry_count (→ g_state+0xF12B)
4       4     --       padding

PER ENTRY (72 bytes on wire, stored as 74 bytes at g_state+0xF12C + i*74):
+0      16    bytes    player_name → entry[0..15], entry[16]=0
+16     16    bytes    guild_name → entry[17..32], entry[33]=0
+32     16    bytes    title → entry[34..49], entry[50]=0
+48     16    bytes    class_name → entry[51..66], entry[67]=0
+64     2     U16 BE   rank_value → entry[68..69]
+66     1     U8       flag_0 → entry[70]
+67     1     U8       flag_1 → entry[71]
+68     1     U8       flag_2 → entry[72]
+69     3     --       padding (skipped)
```

### COLO_RANKING_REPLY (0x02F2) — 6 + N*~164 bytes
Handler: file 0x9D42
```
0       4     U32 BE   session_id (compared to g_state+0x1E70)
4       2     U16 BE   entry_count
6       1     U8       count_indicator
```
If session_id matches, exits early. Otherwise parses entries via subroutine
at 0x9E38 into 164-byte structs at g_state+0x10340. Complex battle ranking data.

---

## Session 5 Deep-Dive: Event Handlers (FULLY DECOMPILED)

### EXEC_EVENT_NOTICE (0x02EF) — 4 bytes
Handler: file 0x8932
```
0       1     U8       event_byte_0 → g_state+0xAB24[slot*4+0]
1       1     U8       event_byte_1 → g_state+0xAB24[slot*4+1]
2       1     U8       event_byte_2 → g_state+0xAB24[slot*4+2]
3       1     U8       event_byte_3 → g_state+0xAB24[slot*4+3]
```
Slot = g_state+0xABA4 (event counter, incremented after store).
Event buffer: g_state+0xAB24 (32 slots × 4 bytes = 128 bytes max).
If counter >= 32: performs screen init before processing.

### EVENT_EFFECT_NOTICE (0x02F0) — 12 + (N1+N2)*36 bytes
Handler: file 0x8A78
```
HEADER (12 bytes):
0       2     U16 BE   event_id (→ g_state+0xAB1A)
2       2     U16 BE   line_count_1 (clamped to max 10)
4       2     U16 BE   line_count_2
6       2     U16 BE   unknown
8       4     U32 BE   unknown

PHASE 1 — TEXT LINES (line_count_1 × 36 bytes each):
+0      32    bytes    line_text
+32     4     --       padding/flags

PHASE 2 — EFFECT DATA (line_count_2 × 36 bytes each):
+0      4     --       header (skipped in memcpy)
+4      32    bytes    effect_data
```
Only processes when event_id == 11 (0x0B). Skips for event_id == 13 or others.
Phase 1 text stored at g_state+0xABAD area.
Phase 2 effects stored at g_state+0xABFE[i*17] (17 bytes per effect entry).

---

## Session 5 Deep-Dive: Remaining Handlers (FULLY DECOMPILED)

### MOVE1_REQUEST (0x01C4) — 16 bytes
Handler: file 0x717A
```
0       2     U16 BE   status → g_state+4
2       2     U16 BE   unknown → temp
4       2     --       skipped (pointer advance from read)
6       1     U8       move_byte_0 → g_state+0x1E76
7       1     U8       move_byte_1 → g_state+0x1E77
8       1     U8       move_byte_2 → g_state+0x1E78
9       1     --       skipped
10      2     U16 BE   move_value → g_state+0x1E74
12      4     U32 BE   trailing (→ temp, discarded)
```
Also clears g_state[0x1E7E] = 0.

### PARTYENTRY_ACCEPT_REPLY (0x01A5) — 8 bytes
Handler: file 0x5EB6
```
0       2     U16 BE   error_code → g_state+4 (0=success)
--- if error == 0: ---
2       2     U16 BE   unknown → temp
4       4     U32 BE   party_id → g_state+0x1E70 (via party_update_slots)
```
On success: calls party_update_slots(party_id) at 0x060164C6 which searches
5 party slots (stride 672, base g_state+0x4B58) and updates g_state+0x1E76..1E7D.

### PARTYENTRY_REPLY (0x01A6) — 20 bytes
Handler: file 0x5EFE
```
0       16    bytes    party_data → g_state+0xAE58
16      4     U32 BE   party_value → g_state+0xAE7C
```
Clears g_state[0xAE68]=0. Sets *(u16*)0x060610C2 = 0x01A6 (message register).

### PARTYUNITE_ACCEPT_REPLY (0x022D) — 8 bytes
Handler: file 0x6444. Identical layout to PARTYENTRY_ACCEPT_REPLY.
```
0       2     U16 BE   error_code (0=success)
--- if 0: ---
2       2     U16 BE   unknown
4       4     U32 BE   party_id → g_state+0x1E70
```

### PARTYUNITE_REPLY (0x022E) — 8 bytes
Handler: file 0x648C
```
0       4     U32 BE   party_id → g_state+0x1E70 (via party_update_slots)
4       4     U32 BE   unite_value → g_state+0xAE7C
```
No error check. Always processes. Sets message register to 0x022E.

### PARTYUNITE_NOTICE (0x025E) — 4 bytes
Handler: file 0x6584
```
0       4     U32 BE   departing_id → g_state+0xAE7C
```
Searches 8 member slots (stride 172, base g_state+0x6F8C) for matching ID.
On match: clears slot. If g_state[0xF4B4]==0: sets callback at 0x0605F424=0x0601BC32.

### MOVE_SEAT_REPLY (0x0256) — VARIABLE (N + data@+16)
Handler: file 0x53B4
Calls init function at 0x060402E0 to get search key length N.
Copies N bytes from payload for seat matching.
Searches 8 seats (stride 172, base g_state+0x6F8C) via 0x0603FB5C.
On match: copies data from payload+16 into found seat slot.

### FINDUSER2_REQUEST (0x0241) — 48 bytes
Handler: file 0x685C
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       2     --       skipped
4       20    bytes    user_name → g_state+0x81B4 (null at +20)
24      18    bytes    second_string → g_state+0x81C9 (null at +39)
44      4     U32 BE   user_id → g_state+0x81DC
```
Note: wire pointer advances by 20 after 18B copy (2 extra skip bytes).

### MIRRORDUNGEON_REQUEST (0x0234) — 8 bytes
Handler: file 0x6814
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       1     U8       dungeon_type → g_state+0x81E0
3       1     --       skipped
4       4     U32 BE   dungeon_id → g_state+0x81E4
```
Clears g_state+0x81E0 and +0x81E4 before reading.

### SAKABA_MOVE_REQUEST (0x0211) — 4 bytes
Handler: file 0x4E30
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       2     U16 BE   destination → g_state+0x6D9C
```

### SAKAYA_EXIT_REQUEST (0x01FB) — 8 bytes
Handler: file 0x5060
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       2     U16 BE   unknown → temp
4       4     U32 BE   exit_context → temp (passed to 0x0601A2C0 cleanup)
```

### SAKAYA_MEMLIST_REQUEST (0x024C) — 8 bytes
Handler: file 0x5112
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       2     U16 BE   member_count → g_state+0x6F88
4       4     U32 BE   context (passed to 0x060151D2 member list processor)
```

### SAKAYA_FIND_REQUEST (0x024F) — 8 bytes
Handler: file 0x5290
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       2     U16 BE   unknown → temp
4       4     U32 BE   find_result → g_state+0x9C
```

### COLO_ENTRY_REQUEST (0x02C4) — 3 bytes
Handler: file 0x9B40
```
0       2     U16 BE   error_code (→ g_state+4, 0=success)
--- if 0: ---
2       1     U8       colo_entry_type → g_state+0xF122
```

### CARD_REPLY continuation (0x02DD) — 10+N*1 + variable
Handler: sub at file 0x454C (called after initial 16B memcpy in CARD_REPLY handler)
```
0       2     U16 BE   card_status (1-7) → g_state+0xF414
2       2     U16 BE   card_count (loop iterations)
4       2     U16 BE   card_field → g_state+0xF448
6       4     --       skipped
10      N     N×U8     packed_cards (1 byte each, bit6=active, bits5-4=category, bits3-0=subtype)
10+N    var   --       case-dependent: additional u16 values per card_status
```
Card entries decoded and insertion-sorted into 3-byte entries at g_state+0xF418 array.
Card_status switches behavior (1-7): display, comparison, serialization paths.

---

## g_state Field Map (Session 5 Additions)
```
g_state+0x009C   4B  Sakaya find result (u32)
g_state+0x00B8   2B  Goto list entry count
g_state+0x00BC   var Goto list entries (28B × max 18)
g_state+0x1780   16B Skill slot data (8 × u16)
g_state+0x1790   var Character validation table
g_state+0x1930   1B  Class sub-type byte
g_state+0x1932   38B New base stats (19 × u16)
g_state+0x6C94   264B Store/Sakaya item list (12 × 22B)
g_state+0x6DA8   480B Sakaya table list (10 × 48B)
g_state+0x6F88   2B  Sakaya member count
g_state+0x6F8C   1376B Sakaya member table (8 × 172B)
g_state+0x7CA0   460B Party list display (2B count + 6 × 76B)
g_state+0x7E6C   var Area list (2B count + entries × 21B)
g_state+0x8014   var Teleport list (field at +6, count at +8, entries at +10)
g_state+0x81B4   42B  Finduser2 data (20B name + null + 18B str + null + 4B id)
g_state+0x81E0   8B  Mirror dungeon data (1B type + 3B pad + 4B id)
g_state+0xAB24   128B Event buffer (32 slots × 4B)
g_state+0xABAC   1B  Event effect header byte
g_state+0xABAD   var Event effect lines
g_state+0xABFE   var Event effect entries (17B each)
g_state+0xB37A   var Directory entries (46B each)
g_state+0xBEFA   2B  Memo area ID
g_state+0xBEFC   2B  Memo entry count
g_state+0xBF00   var Memo entries (68B each)
g_state+0xD002   16B News author name
g_state+0xD014   2B  News article ID
g_state+0xD016   4B  News date bytes
g_state+0xD01A   40B News subject
g_state+0xD048   800B News/Mail body text
g_state+0xD44A   2B  Mail count
g_state+0xD44C   2B  Mail cumulative count
g_state+0xD44E   2B  Mail pagination state (0=init,1=more,2=done)
g_state+0xD450   90B Mail entries (4-5 × 19B)
g_state+0xDB00   2B  Mail type bytes
g_state+0xDB02   16B Mail sender name
g_state+0xDB14   2B  Mail timestamp
g_state+0xDB16   4B  Mail date fields
g_state+0xDB1A   40B Mail subject
g_state+0xDB46   1B  Mail attachment flag
g_state+0xDB47   16B Mail attachment name
g_state+0xDB58   4B  Mail body offset
g_state+0xDB5C   4B  Mail body length
g_state+0xEE00   1B  Colo entry count
g_state+0xEE02   var Colo entries (40B each)
g_state+0xF12A   1B  Colo ranking type
g_state+0xF12B   1B  Colo ranking entry count
g_state+0xF12C   var Colo ranking entries (74B each)
g_state+0xF414   2B  Card status (u16)
g_state+0xF418   var Card entries (3B each, sorted)
g_state+0xF448   2B  Card field/context
```
