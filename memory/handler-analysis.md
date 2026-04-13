# Handler Dispatch Mechanism Analysis

## Binary: `D:\DragonsDreamDecomp\extracted\0.BIN` (504,120 bytes, SH-2 big-endian)
## Base address: 0x06010000

---

## 1. Handler Table Format (file 0x0435D8, 197 entries)

Each entry is **8 bytes**:

```
Offset  Size  Field
------  ----  -----
0       2     msg_type (uint16 BE) - message type code
2       2     padding (always 0x0000)
4       4     handler_addr (uint32 BE) - SH-2 memory address of handler function
```

The table is **NOT sorted** by msg_type. It is scanned linearly until a match is found. An entry with msg_type = 0x0000 serves as a sentinel (end of table), since SELECT_REQUEST (value 0x0000) is never sent on the wire.

### Complete Handler Table (197 entries)

| # | msg_type | Name | Handler (mem) | Handler (file) |
|---|----------|------|---------------|----------------|
| 0 | 0x019F | UPDATE_CHARDATA_REQUEST | 0x06013578 | 0x003578 |
| 1 | 0x02F9 | CHARDATA_REQUEST | 0x06013648 | 0x003648 |
| 2 | 0x02D2 | CHARDATA_REPLY | 0x06013858 | 0x003858 |
| 3 | 0x01AB | CHARDATA_NOTICE | 0x06013B90 | 0x003B90 |
| 4 | 0x0046 | REGIST_HANDLE_REQUEST | 0x06013D04 | 0x003D04 |
| 5 | 0x0049 | SPEAK_REQUEST | 0x06013D42 | 0x003D42 |
| 6 | 0x004A | SPEAK_REPLY | 0x06013D80 | 0x003D80 |
| 7 | 0x0076 | SPEAK_NOTICE | 0x06013D86 | 0x003D86 |
| 8 | 0x019D | INFORMATION_NOTICE | 0x06013DDA | 0x003DDA |
| 9 | 0x01B9 | CURREGION_NOTICE | 0x06013E16 | 0x003E16 |
| 10 | 0x006F | ESP_REQUEST | 0x06013E50 | 0x003E50 |
| 11 | 0x006E | ESP_REPLY | 0x06013EDA | 0x003EDA |
| 12 | 0x01E8 | ESP_NOTICE | 0x06013F1C | 0x003F1C |
| 13 | 0x01ED | PARTYID_REQUEST | 0x0601401E | 0x00401E |
| 14 | 0x01EF | CLR_KNOWNMAP_REQUEST | 0x0601405C | 0x00405C |
| 15 | 0x01A8 | PARTYEXIT_REQUEST | 0x060140C4 | 0x0040C4 |
| 16 | 0x01A9 | PARTYEXIT_REPLY | 0x06014116 | 0x004116 |
| 17 | 0x0232 | PARTYEXIT_NOTICE | 0x06014252 | 0x004252 |
| 18 | 0x0260 | ACTION_CHAT_REQUEST | 0x0601428E | 0x00428E |
| 19 | 0x0261 | ACTION_CHAT_REPLY | 0x060142EE | 0x0042EE |
| 20 | 0x02D5 | CAST_DICE_REQUEST | 0x06014348 | 0x004348 |
| 21 | 0x02D6 | CAST_DICE_REPLY | 0x060143B0 | 0x0043B0 |
| 22 | 0x02DC | CARD_REQUEST | 0x060144CE | 0x0044CE |
| 23 | 0x02DD | CARD_REPLY | 0x06014522 | 0x004522 |
| 24 | 0x0043 | LOGOUT_REQUEST | 0x0601491C | 0x00491C |
| 25 | 0x019B | GOTOLIST_REQUEST | 0x0601492E | 0x00492E |
| 26 | 0x0215 | GOTOLIST_REPLY | 0x06014A08 | 0x004A08 |
| 27 | 0x01B8 | FINDUSER_REQUEST | 0x06014AC0 | 0x004AC0 |
| 28 | 0x0270 | STORE_LIST_REQUEST | 0x06014AF4 | 0x004AF4 |
| 29 | 0x0272 | STORE_IN_REQUEST | 0x06014BFE | 0x004BFE |
| 30 | 0x0273 | STORE_IN_REPLY | 0x06014C2C | 0x004C2C |
| 31 | 0x020D | SAKAYA_LIST_REQUEST | 0x06014C3A | 0x004C3A |
| 32 | 0x0213 | SAKAYA_LIST_REPLY | 0x06014D22 | 0x004D22 |
| 33 | 0x0211 | SAKABA_MOVE_REQUEST | 0x06014E30 | 0x004E30 |
| 34 | 0x0212 | SAKABA_MOVE_REPLY | 0x06014E60 | 0x004E60 |
| 35 | 0x0217 | SAKAYA_IN_REQUEST | 0x06014E7E | 0x004E7E |
| 36 | 0x0218 | SAKAYA_IN_REPLY | 0x06014EA6 | 0x004EA6 |
| 37 | 0x01A1 | USERLIST_REQUEST | 0x06014EBE | 0x004EBE |
| 38 | 0x021C | USERLIST_REPLY | 0x06014EC2 | 0x004EC2 |
| 39 | 0x01F9 | SAKAYA_TBLLIST_REQUEST | 0x06014EC6 | 0x004EC6 |
| 40 | 0x0214 | SAKAYA_TBLLIST_REPLY | 0x06014FCC | 0x004FCC |
| 41 | 0x01FB | SAKAYA_EXIT_REQUEST | 0x06015060 | 0x005060 |
| 42 | 0x021B | SAKAYA_EXIT_REPLY | 0x060150A4 | 0x0050A4 |
| 43 | 0x020F | SAKAYA_SIT_REQUEST | 0x060150D0 | 0x0050D0 |
| 44 | 0x024C | SAKAYA_MEMLIST_REQUEST | 0x06015112 | 0x005112 |
| 45 | 0x024D | SAKAYA_MEMLIST_REPLY | 0x06015152 | 0x005152 |
| 46 | 0x024F | SAKAYA_FIND_REQUEST | 0x06015290 | 0x005290 |
| 47 | 0x021A | SAKAYA_STAND_REQUEST | 0x060152CE | 0x0052CE |
| 48 | 0x021E | SAKAYA_STAND_REPLY | 0x060152F6 | 0x0052F6 |
| 49 | 0x0246 | SET_SIGN_REQUEST | 0x060152FA | 0x0052FA |
| 50 | 0x0247 | SET_SIGN_REPLY | 0x0601533C | 0x00533C |
| 51 | 0x0255 | MOVE_SEAT_REQUEST | 0x0601538C | 0x00538C |
| 52 | 0x0256 | MOVE_SEAT_REPLY | 0x060153B4 | 0x0053B4 |
| 53 | 0x0251 | SET_SEKIBAN_REQUEST | 0x06015436 | 0x005436 |
| 54 | 0x0252 | SET_SEKIBAN_REPLY | 0x06015472 | 0x005472 |
| 55 | 0x0253 | SET_SEKIBAN_NOTICE | 0x06015476 | 0x005476 |
| 56 | 0x0203 | SHOP_LIST_REQUEST | 0x0601547A | 0x00547A |
| 57 | 0x01FF | SHOP_IN_REQUEST | 0x06015588 | 0x005588 |
| 58 | 0x01FD | SHOP_ITEM_REQUEST | 0x060156B8 | 0x0056B8 |
| 59 | 0x01F3 | SHOP_BUY_REQUEST | 0x060157F6 | 0x0057F6 |
| 60 | 0x01F5 | SHOP_SELL_REQUEST | 0x06015856 | 0x005856 |
| 61 | 0x0201 | SHOP_OUT_REQUEST | 0x060158CC | 0x0058CC |
| 62 | 0x029E | DIR_REQUEST | 0x060158E8 | 0x0058E8 |
| 63 | 0x02A0 | SUBDIR_REQUEST | 0x060159AE | 0x0059AE |
| 64 | 0x02A2 | MEMODIR_REQUEST | 0x06015A78 | 0x005A78 |
| 65 | 0x02A4 | NEWS_READ_REQUEST | 0x06015BB0 | 0x005BB0 |
| 66 | 0x02A6 | NEWS_WRITE_REQUEST | 0x06015C4C | 0x005C4C |
| 67 | 0x02A8 | NEWS_DEL_REQUEST | 0x06015C68 | 0x005C68 |
| 68 | 0x02B2 | BB_MKDIR_REQUEST | 0x06015C84 | 0x005C84 |
| 69 | 0x02B4 | BB_RMDIR_REQUEST | 0x06015CA0 | 0x005CA0 |
| 70 | 0x02B6 | BB_MKSUBDIR_REQUEST | 0x06015CBC | 0x005CBC |
| 71 | 0x02B8 | BB_RMSUBDIR_REQUEST | 0x06015CD8 | 0x005CD8 |
| 72 | 0x01A3 | PARTYLIST_REQUEST | 0x06015D1C | 0x005D1C |
| 73 | 0x022B | PARTYENTRY_REQUEST | 0x06015E8E | 0x005E8E |
| 74 | 0x01A5 | PARTYENTRY_ACCEPT_REPLY | 0x06015EB6 | 0x005EB6 |
| 75 | 0x01A6 | PARTYENTRY_REPLY | 0x06015EFE | 0x005EFE |
| 76 | 0x025A | PARTYENTRY_NOTICE | 0x06015F36 | 0x005F36 |
| 77 | 0x01E7 | ALLOW_JOIN_REQUEST | 0x06015F90 | 0x005F90 |
| 78 | 0x025C | CANCEL_JOIN_REQUEST | 0x06015FB2 | 0x005FB2 |
| 79 | 0x025D | CANCEL_JOIN_REPLY | 0x06015FCE | 0x005FCE |
| 80 | 0x01B6 | CANCEL_JOIN_NOTICE | 0x06015FE6 | 0x005FE6 |
| 81 | 0x022F | PARTYUNITE_REQUEST | 0x060163FA | 0x0063FA |
| 82 | 0x022D | PARTYUNITE_ACCEPT_REPLY | 0x06016444 | 0x006444 |
| 83 | 0x022E | PARTYUNITE_REPLY | 0x0601648C | 0x00648C |
| 84 | 0x025E | PARTYUNITE_NOTICE | 0x06016584 | 0x006584 |
| 85 | 0x0231 | ALLOW_UNITE_REQUEST | 0x060165F4 | 0x0065F4 |
| 86 | 0x023C | AREA_LIST_REQUEST | 0x06016622 | 0x006622 |
| 87 | 0x01B0 | TELEPORTLIST_REQUEST | 0x060166FA | 0x0066FA |
| 88 | 0x023F | EXPLAIN_REQUEST | 0x060167BA | 0x0067BA |
| 89 | 0x04E1 | TELEPORT_REQUEST | 0x060167E2 | 0x0067E2 |
| 90 | 0x0234 | MIRRORDUNGEON_REQUEST | 0x06016814 | 0x006814 |
| 91 | 0x0241 | FINDUSER2_REQUEST | 0x0601685C | 0x00685C |
| 92 | 0x0299 | CLASS_LIST_REQUEST | 0x060168C0 | 0x0068C0 |
| 93 | 0x029B | CLASS_CHANGE_REQUEST | 0x060168F0 | 0x0068F0 |
| 94 | 0x01C0 | CLASS_CHANGE_REPLY | 0x060169FC | 0x0069FC |
| 95 | 0x01DE | MAP_NOTICE | 0x06016C38 | 0x006C38 |
| 96 | 0x01D2 | KNOWNMAP_NOTICE | 0x06016CDA | 0x006CDA |
| 97 | 0x0248 | SETCLOCK0_NOTICE | 0x06016CFA | 0x006CFA |
| 98 | 0x0249 | EVENT_MAP_NOTICE | 0x06016DD4 | 0x006DD4 |
| 99 | 0x024A | MONSTER_MAP_NOTICE | 0x06016DD8 | 0x006DD8 |
| 100 | 0x01DA | MONSTER_DEL_NOTICE | 0x06016DDC | 0x006DDC |
| 101 | 0x01DB | VISION_NOTICE | 0x06016DEC | 0x006DEC |
| 102 | 0x01DC | OBITUARY_NOTICE | 0x06016DF0 | 0x006DF0 |
| 103 | 0x0257 | MISSPARTY_NOTICE | 0x06016E98 | 0x006E98 |
| 104 | 0x01C4 | MOVE1_REQUEST | 0x0601717A | 0x00717A |
| 105 | 0x01C5 | MOVE2_REQUEST | 0x0601720C | 0x00720C |
| 106 | 0x02F3 | MOVE2_NOTICE | 0x0601729A | 0x00729A |
| 107 | 0x01AD | CAMP_IN_REQUEST | 0x06017360 | 0x007360 |
| 108 | 0x01AE | CAMP_IN_REPLY | 0x06017392 | 0x007392 |
| 109 | 0x01E0 | SET_MOVEMODE_REQUEST | 0x060173B2 | 0x0073B2 |
| 110 | 0x01E1 | SET_MOVEMODE_REPLY | 0x060173CE | 0x0073CE |
| 111 | 0x02F8 | GIVEUP_REQUEST | 0x0601741A | 0x00741A |
| 112 | 0x01D4 | SETPOS_REQUEST | 0x060174EE | 0x0074EE |
| 113 | 0x01D5 | SETPOS_REPLY | 0x06017532 | 0x007532 |
| 114 | 0x01D7 | SETLEADER_REQUEST | 0x060175CC | 0x0075CC |
| 115 | 0x01D8 | SETLEADER_REPLY | 0x060175FC | 0x0075FC |
| 116 | 0x02D7 | SETLEADER_NOTICE | 0x06017608 | 0x007608 |
| 117 | 0x02D8 | INQUIRE_LEADER_NOTICE | 0x06017632 | 0x007632 |
| 118 | 0x02DA | ALLOW_SETLEADER_REQUEST | 0x0601764E | 0x00764E |
| 119 | 0x01B4 | CAMP_OUT_REQUEST | 0x0601779A | 0x00779A |
| 120 | 0x01B5 | CAMP_OUT_REPLY | 0x060177CC | 0x0077CC |
| 121 | 0x0205 | EQUIP_REQUEST | 0x060177EC | 0x0077EC |
| 122 | 0x0263 | EQUIP_REPLY | 0x06017808 | 0x007808 |
| 123 | 0x026D | DISARM_REQUEST | 0x0601780C | 0x00780C |
| 124 | 0x026E | DISARM_REPLY | 0x0601782E | 0x00782E |
| 125 | 0x02E9 | USE_SKILL_REQUEST | 0x06017832 | 0x007832 |
| 126 | 0x02EA | USE_SKILL_REPLY | 0x06017870 | 0x007870 |
| 127 | 0x02F6 | CHANGE_PARA_REQUEST | 0x060179F0 | 0x0079F0 |
| 128 | 0x0242 | CHANGE_PARA_REPLY | 0x06017A0C | 0x007A0C |
| 129 | 0x0244 | ENCOUNTMONSTER_REQUEST | 0x06017A2A | 0x007A2A |
| 130 | 0x01C9 | ENCOUNTMONSTER_REPLY | 0x06017A6C | 0x007A6C |
| 131 | 0x01CA | ENCOUNTMONSTER_NOTICE | 0x06017BEC | 0x007BEC |
| 132 | 0x021F | BATTLEMODE_NOTICE | 0x06017BF8 | 0x007BF8 |
| 133 | 0x0220 | BTL_MEMBER_NOTICE | 0x06017D84 | 0x007D84 |
| 134 | 0x0222 | BTL_CMD_REQUEST | 0x06017D88 | 0x007D88 |
| 135 | 0x0223 | BTL_CMD_REPLY | 0x06017DCC | 0x007DCC |
| 136 | 0x0225 | BTL_CHGMODE_REQUEST | 0x06017E60 | 0x007E60 |
| 137 | 0x0226 | BTL_CHGMODE_REPLY | 0x06017E64 | 0x007E64 |
| 138 | 0x0227 | BTL_RESULT_NOTICE | 0x060181B0 | 0x0081B0 |
| 139 | 0x0228 | BTL_END_NOTICE | 0x0601834A | 0x00834A |
| 140 | 0x0229 | BTL_MASK_NOTICE | 0x0601834E | 0x00834E |
| 141 | 0x0297 | BTL_EFFECTEND_REQUEST | 0x06018352 | 0x008352 |
| 142 | 0x01EB | BTL_END_REQUEST | 0x06018356 | 0x008356 |
| 143 | 0x02F4 | BTL_END_REPLY | 0x0601836E | 0x00836E |
| 144 | 0x01C8 | BTL_GOLD_NOTICE | 0x060183E4 | 0x0083E4 |
| 145 | 0x01E4 | CANCEL_ENCOUNT_REQUEST | 0x060186C8 | 0x0086C8 |
| 146 | 0x01E5 | CANCEL_ENCOUNT_REPLY | 0x0601874C | 0x00874C |
| 147 | 0x0236 | BTLJOIN_REQUEST | 0x06018820 | 0x008820 |
| 148 | 0x0237 | BTLJOIN_REPLY | 0x06018824 | 0x008824 |
| 149 | 0x01C7 | BTLJOIN_NOTICE | 0x06018828 | 0x008828 |
| 150 | 0x01D0 | EXEC_EVENT_REQUEST | 0x0601887A | 0x00887A |
| 151 | 0x01D1 | EXEC_EVENT_REPLY | 0x060188EC | 0x0088EC |
| 152 | 0x02EF | EXEC_EVENT_NOTICE | 0x06018932 | 0x008932 |
| 153 | 0x02F0 | EVENT_EFFECT_NOTICE | 0x06018A78 | 0x008A78 |
| 154 | 0x02F1 | WAIT_EVENT_NOTICE | 0x06018BD4 | 0x008BD4 |
| 155 | 0x01BC | CHAR_DISAPPEAR_NOTICE | 0x06018C90 | 0x008C90 |
| 156 | 0x01C6 | EVENT_ITEM_NOTICE | 0x06018E22 | 0x008E22 |
| 157 | 0x0294 | GIVE_ITEM_REQUEST | 0x06018E5A | 0x008E5A |
| 158 | 0x0295 | GIVE_ITEM_REPLY | 0x06018E76 | 0x008E76 |
| 159 | 0x02D1 | USE_REQUEST | 0x06019090 | 0x009090 |
| 160 | 0x02D3 | USE_REPLY | 0x060190D8 | 0x0090D8 |
| 161 | 0x028D | SELL_REQUEST | 0x060192D8 | 0x0092D8 |
| 162 | 0x028C | SELL_REPLY | 0x060192F2 | 0x0092F2 |
| 163 | 0x028F | BUY_REQUEST | 0x06019358 | 0x009358 |
| 164 | 0x028A | BUY_REPLY | 0x06019372 | 0x009372 |
| 165 | 0x028B | TRADE_DONE_NOTICE | 0x060193C0 | 0x0093C0 |
| 166 | 0x0291 | TRADE_CANCEL_REQUEST | 0x060193F4 | 0x0093F4 |
| 167 | 0x0292 | TRADE_CANCEL_REPLY | 0x0601940E | 0x00940E |
| 168 | 0x02EE | COMPOUND_REQUEST | 0x06019430 | 0x009430 |
| 169 | 0x0276 | CONFIRM_LVLUP_REQUEST | 0x060195B8 | 0x0095B8 |
| 170 | 0x0278 | LEVELUP_REQUEST | 0x060195E4 | 0x0095E4 |
| 171 | 0x02BA | SKILL_LIST_REQUEST | 0x0601969C | 0x00969C |
| 172 | 0x02E1 | LEARN_SKILL_REQUEST | 0x060196C4 | 0x0096C4 |
| 173 | 0x02E3 | SKILLUP_REQUEST | 0x060196F8 | 0x0096F8 |
| 174 | 0x02E5 | EQUIP_SKILL_REQUEST | 0x06019718 | 0x009718 |
| 175 | 0x02E7 | DISARM_SKILL_REQUEST | 0x06019738 | 0x009738 |
| 176 | 0x0269 | SEL_THEME_REQUEST | 0x06019758 | 0x009758 |
| 177 | 0x026B | CHECK_THEME_REQUEST | 0x06019772 | 0x009772 |
| 178 | 0x02AA | MAIL_LIST_REQUEST | 0x0601978C | 0x00978C |
| 179 | 0x02AC | GET_MAIL_REQUEST | 0x060198AA | 0x0098AA |
| 180 | 0x02AE | SEND_MAIL_REQUEST | 0x06019986 | 0x009986 |
| 181 | 0x02B0 | DEL_MAIL_REQUEST | 0x060199A0 | 0x0099A0 |
| 182 | 0x02BC | COLO_WAITING_REQUEST | 0x06019A08 | 0x009A08 |
| 183 | 0x02BD | COLO_WAITING_REPLY | 0x06019A22 | 0x009A22 |
| 184 | 0x02BF | COLO_EXIT_REQUEST | 0x06019A38 | 0x009A38 |
| 185 | 0x02C0 | COLO_EXIT_REPLY | 0x06019A52 | 0x009A52 |
| 186 | 0x02C2 | COLO_LIST_REQUEST | 0x06019A68 | 0x009A68 |
| 187 | 0x02C4 | COLO_ENTRY_REQUEST | 0x06019B40 | 0x009B40 |
| 188 | 0x02EB | COLO_ENTRY_REPLY | 0x06019B6A | 0x009B6A |
| 189 | 0x02C6 | COLO_CANCEL_REQUEST | 0x06019B7C | 0x009B7C |
| 190 | 0x02EC | COLO_CANCEL_REPLY | 0x06019B96 | 0x009B96 |
| 191 | 0x02C7 | COLO_CANCEL_NOTICE | 0x06019B9A | 0x009B9A |
| 192 | 0x02C9 | COLO_FLDENT_REQUEST | 0x06019BE0 | 0x009BE0 |
| 193 | 0x02CF | COLO_FLDENT_REPLY | 0x06019BFA | 0x009BFA |
| 194 | 0x02CC | COLO_FLDENT_NOTICE | 0x06019C10 | 0x009C10 |
| 195 | 0x02CE | COLO_RANKING_REQUEST | 0x06019C46 | 0x009C46 |
| 196 | 0x02F2 | COLO_RANKING_REPLY | 0x06019D42 | 0x009D42 |

---

## 2. Dispatch Mechanism

### 2.1 Primary Dispatch Function (file 0x003420, mem 0x06013420)

This function takes a received message buffer and looks up the handler:

```
function dispatch_handler(r4=msg_buffer_ptr, r5=data_ptr):
    r12 = msg_buffer_ptr
    r13 = handler_table_base  (0x060535D8, loaded from literal pool)
    r10 = 0  (loop counter)

    handler_count = load_from_GBR(offset=8)  ; global handler count

    for each entry in handler_table:
        entry_msg_type = entry[0:2]  (16-bit, first 2 bytes of 8B entry)
        incoming_type = msg_buffer[2:4]  (16-bit at offset 2 of recv buffer)

        if entry_msg_type == 0:
            break  ; sentinel - end of table

        if entry_msg_type == incoming_type:
            handler_addr = entry[4:8]  (32-bit function pointer)
            if handler_addr != NULL:
                call handler_addr(r4=entry_ptr+8, r5=data_ptr)
                return

    ; Special case: ACTION_CHAT_NOTICE (0x0274) handled separately
    if incoming_type == 0x0274:
        call action_chat_handler(r4=msg_buffer, r5=data_ptr)
```

**Key observations:**
- msg_type is read from **offset 2** of the receive buffer (`mov.w @(2,r12),r0`)
- The handler table is scanned linearly (not binary search)
- ACTION_CHAT_NOTICE (0x0274) has a special-case handler outside the table
- The handler receives the entry pointer + 8 as r4 (i.e., pointer to next entry)

### 2.2 Secondary Dispatch Function (file 0x0034E4, mem 0x060134E4)

A second dispatch function at 0x34E4 uses a paired message type table at file 0x043424 (mem 0x06053424). This table contains 2-byte msg_type values in pairs (4 bytes per pair), terminated by 0x0000.

This function:
1. Reads msg_type from **offset 6** of the SV context structure (GBR+8)
2. Iterates through the paired table (stride = 4 bytes = 2 entries)
3. Compares with each pair's first entry
4. On match, checks if a handler function pointer is available
5. Calls through a function dispatch mechanism

### 2.3 Global Receive Context (GBR+8)

Both dispatch functions access a global context structure via `mov.l @(8,GBR),r0`. This structure contains:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 2 | status | Connection/message status |
| 2 | 2 | field_2 | Used in dispatch (msg_type in primary) |
| 4 | 2 | result | Operation result (checked in handlers) |
| 6 | 2 | msg_type | Current message type (used in secondary dispatch) |
| ... | ... | ... | Additional state fields |

---

## 3. Wire Format Analysis

### 3.1 Application Layer Message Format

Based on the dispatch analysis:

**The receive buffer layout (after SV de-framing) is:**
```
Offset  Size  Content
------  ----  -------
0       2     [size or status field]
2       2     msg_type (uint16 BE)
4       N     payload data
```

The dispatch function reads msg_type from offset 2 of the buffer. Handler functions access payload starting at offset 4 of the buffer (e.g., `add #4, r4` before calling helpers).

### 3.2 Wire Format — CORRECTED (2026-03-11)

**IMPORTANT: Sections 3.2-3.5 from earlier sessions were WRONG.**
msg_type is NOT equal to wire size. It is a unique message identifier.

See [wire-format.md](wire-format.md) for the corrected analysis with evidence.

**Correct wire format:**
```
Offset  Size  Field
0       2     param1 (usually 0x0000)
2       2     msg_type (unique identifier, uint16 BE)
4       4     payload_size (actual payload byte count, uint32 BE)
8       N     payload (N = payload_size bytes)
```

Total wire size = 8 + payload_size. NOT msg_type.

Evidence: LOGIN_REQUEST msg_type=0x019E (414), actual payload=60B, wire=68B.
CHARDATA2_NOTICE msg_type=0x0B6C (2924), actual payload=16B, wire=24B.

The dispatch reads msg_type from buffer[2] and passes buffer+8 to handlers.
The "wire size" values in section 4 below are INCORRECT legacy values.

---

## 4. Key Handler Behaviors

**NOTE: All "Wire size" values in this section are WRONG (legacy, from when we thought
msg_type = wire size). See handler-payloads-detailed.md for correct payload sizes.**

### 4.1 UPDATE_CHARDATA_REQUEST (0x019F, handler at 0x003578)

**Wire size:** ~~415 bytes~~ INCORRECT — actual payload is 24 bytes
**Function behavior:**
1. Loads SV context from GBR+8
2. Calls a helper function at 0x06019FF6 with context+4 as argument
3. Checks a status field at context+4 (16-bit)
4. If status == 0 (success): copies chardata fields from payload to game state
   - Reads multiple structure fields using indexed offsets
   - Writes to game world data structure (0x0604C5A8, 0x0604C5C0, 0x0604C5D8)
5. If status == 1: selects one handler path
6. If status != 0 and != 1: selects alternate handler path
7. Uses memcpy-like operations to transfer character data blocks

### 4.2 CHARDATA_REPLY (0x02D2, handler at 0x003858)

**Wire size:** 722 bytes (largest common message)
**Function behavior:**
1. Allocates 120+ bytes of stack space (7FF88 = add #-120, r15)
2. Loads SV context and reads status fields
3. Calls helper at 0x06019FD2 to parse initial header fields
4. Branches based on status byte at offset in recv buffer:
   - Status 1: Character creation flow
   - Status 2: Character selection/load flow
   - Status 3: Another path
5. Extracts extensive character data fields:
   - Character name (offset ~0x46-0x47 in payload)
   - Stats (at various offsets 0x58, 0x5C, 0x5D, 0x5E, 0x5F, 0x60, 0x61, 0x62)
   - Level, experience, HP, MP fields
   - Equipment slots
   - Gold value
   - Known map data
   - Inventory items (loop with 8 iterations)
6. Stores parsed data to game world structures
7. Uses function at 0x060146C4 for string copy operations

**Payload field offsets (from start of payload at buffer+4):**
- Offset 0x10: Header/result data (parsed first)
- Offset 0x14: Secondary header block
- Offset 0x2C: Tertiary data block
- Offset 0x1C: Another data block
- Offset 0x44: Character name region
- Offset 0x46-0x62: Character stats (individual bytes/words)
- Offset 0x48-onwards: Equipment/inventory blocks
- Offset 0x64+: Repeated inventory entries (8 iterations, 1 byte each index, varying stride)

### 4.3 INFORMATION_NOTICE (0x019D, handler at 0x003DDA)

**Wire size:** 413 bytes
**Function behavior:**
1. Loads SV context, calls helper to parse message
2. Checks status code
3. If successful, calls two display functions:
   - First call with literal offsets 0x0090 and 0x008E
   - Second call with offset 0xFF78
4. Likely displays server information text to the player

### 4.4 SPEAK_REQUEST (0x0049, handler at 0x003D42)

**Wire size:** 73 bytes
**Function behavior:** Minimal handler - likely just stores the speak request and forwards to local display. The actual chat text is approximately 69 bytes of payload (73 - 4 header).

### 4.5 SPEAK_NOTICE (0x0076, handler at 0x003D86)

**Wire size:** 118 bytes
**Function behavior:** Receives broadcast chat from another player. Contains:
- Speaker ID/name
- Chat text content
- Possibly chat type (normal, whisper, party, shout)

### 4.6 CHARDATA_NOTICE (0x01AB, handler at 0x003B90)

**Wire size:** 427 bytes
**Function behavior:**
1. Large handler (extends to around 0x003D04)
2. Parses character appearance data for rendering other players
3. Reads fields similar to CHARDATA_REPLY but for OTHER characters in the vicinity
4. Updates the visible character list
5. Contains character position, appearance, equipment, name data

### 4.7 Battle Handlers

**BATTLEMODE_NOTICE (0x021F):** 543 bytes - Enters battle mode, sets up battle UI
**BTL_MEMBER_NOTICE (0x0220):** 544 bytes - Lists battle participants
**BTL_CMD_REQUEST (0x0222):** 546 bytes - Player selects battle action
**BTL_CMD_REPLY (0x0223):** 547 bytes - Server confirms action
**BTL_RESULT_NOTICE (0x0227):** 551 bytes - Battle results (damage, effects)
**BTL_END_NOTICE (0x0228):** 552 bytes - Battle conclusion

### 4.8 Movement Handlers

**MOVE1_REQUEST (0x01C4):** 452 bytes - Walking movement
**MOVE2_REQUEST (0x01C5):** 453 bytes - Running movement
**MOVE2_NOTICE (0x02F3):** 755 bytes - Other player movement broadcast
**SETPOS_REQUEST (0x01D4):** 468 bytes - Set exact position
**SETPOS_REPLY (0x01D5):** 469 bytes - Position confirmed

### 4.9 Shop Handlers

**SHOP_LIST_REQUEST (0x0203):** 515 bytes - Request shop inventory
**SHOP_IN_REQUEST (0x01FF):** 511 bytes - Enter shop
**SHOP_ITEM_REQUEST (0x01FD):** 509 bytes - View item details
**SHOP_BUY_REQUEST (0x01F3):** 499 bytes - Purchase item
**SHOP_SELL_REQUEST (0x01F5):** 501 bytes - Sell item
**SHOP_OUT_REQUEST (0x0201):** 513 bytes - Leave shop

### 4.10 Equipment Handlers

**EQUIP_REQUEST (0x0205):** 517 bytes - Equip an item
**EQUIP_REPLY (0x0263):** 611 bytes - Equip confirmed
**DISARM_REQUEST (0x026D):** 621 bytes - Unequip item
**DISARM_REPLY (0x026E):** 622 bytes - Unequip confirmed

---

## 5. Message Table at 0x04612C (310 entries)

Each entry is **8 bytes**: `[4B string_ptr][4B msg_type_value]`

The string pointers reference ASCII message name strings in the range file 0x3D7FC-0x3EEC0 (memory 0x0604D7FC-0x0604EEC0). Names follow the pattern:
- `*_REQUEST` - client-to-server requests (110 entries)
- `*_REPLY` - server-to-client responses (106 entries)
- `*_NOTICE` - server-to-client broadcasts (94 entries)

### Paired Message Types Table (file 0x043424)

A secondary table at file 0x043424 contains msg_type values as 16-bit entries in pairs, terminated by 0x0000. This table has approximately 216 entries (108 pairs). Each pair associates a REQUEST with its corresponding REPLY or NOTICE, used by the secondary dispatch function.

Example pairs from the table:
```
0x0035, 0x01E8  (REGIST_HANDLE_REQUEST?, ESP_NOTICE)
0x019E, 0x019F  (LOGIN_REQUEST, UPDATE_CHARDATA_REQUEST)
0x01AA, 0x02F9  (UPDATE_CHARDATA_REPLY, CHARDATA_REQUEST)
0x0048, 0x0049  (STANDARD_REPLY, SPEAK_REQUEST)
0x006D, 0x006F  (SYSTEM_NOTICE, ESP_REQUEST)
```

---

## 6. Handler Function Patterns

All handlers follow a common prologue pattern:

```asm
mov.l r14,@-r15        ; push r14  (callee-save)
mov r4,r5              ; save first argument
mov.l @(disp,PC),r3   ; load helper function address
sts.l PR,@-r15         ; push return address
sts.l MACL,@-r15       ; push MACL (sometimes)
add #-N,r15            ; allocate stack frame
mov.l r4,@r15          ; save arg on stack
mov.l @(8,GBR),r0     ; load SV context (global)
mov r0,r14             ; r14 = SV context (used throughout)
mov r0,r4              ; r4 = SV context
jsr @r3                ; call parser/helper
add #4,r4              ; (delay) r4 = context + 4 (skip to payload)
```

After parsing:
```asm
mov.l r0,@r15          ; save parse result
mov.w @(4,r14),r0     ; check status at context+4
tst r0,r0              ; test status
bt <error_path>        ; branch if zero (no data)
```

This pattern shows that:
1. Every handler accesses the SV context from GBR+8
2. The context+4 offset is where message data begins
3. A status check at context+4 determines if the message was received successfully
4. Helper functions at 0x06019FF6 and 0x06019FD2 are called to parse headers

---

## 7. Summary of Findings

### Wire Format (Best Estimate)
```
APPLICATION LAYER:
  [2B msg_type (uint16 BE)][payload of (msg_type - 2) bytes]
  Total size on wire = msg_type value

SV FRAMING LAYER (wraps each fragment):
  [0x0A sync][15B header][0-256B data chunk]
  Messages > 256 bytes are fragmented
  16-byte fragment header includes: type, seq, total_size, offset, data_len, checksum

RECEIVE BUFFER (after SV reassembly):
  [2B SV_status][2B msg_type][payload]
  Offset 2 = msg_type (confirmed by dispatch code)
  Offset 4 = payload start (confirmed by handler code)
```

### Handler Table
- 197 entries at file 0x0435D8
- 8 bytes each: [2B msg_type][2B pad][4B handler_addr]
- Linear scan, sentinel terminated (msg_type == 0)
- One special case: ACTION_CHAT_NOTICE (0x0274) handled outside table

### Message Categories
- **110 REQUEST types** (client sends to server)
- **106 REPLY types** (server responds to client)
- **94 NOTICE types** (server broadcasts to client)
- **310 total** named message types
- **197 have client-side handlers** (all REPLY and NOTICE types, plus some REQUEST echoes)

### Key Data Structures
- SV Context: accessed via GBR+8, contains connection state, message type, status
- Character Data: ~720 bytes, includes name, stats, equipment, inventory, map knowledge
- Game World: multiple data structures at 0x0604C5xx-0x0604C6xx range
