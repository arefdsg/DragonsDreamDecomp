# Paired Message Table — Complete Dump

## Source: file 0x043484 (mem 0x06053484), 84 entries, [send:2 BE][reply:2 BE]

Terminated by send_type=0x0000. Maps client→server msg_types to expected server→client replies.

| Idx | Client Sends | Server Replies | Category |
|-----|-------------|---------------|----------|
| 0 | 0x020E | 0x020F | Tavern sit |
| 1 | 0x024B | 0x024C | Tavern member list update |
| 2 | 0x024E | 0x024F | Tavern find/member list |
| 3 | 0x0219 | 0x021A | Tavern stand |
| 4 | 0x0245 | 0x0246 | Tavern sign/action |
| 5 | 0x0254 | 0x0255 | Tavern move seat |
| 6 | 0x0250 | 0x0251 | Tavern sekiban |
| 7 | 0x0202 | 0x0203 | Shop list |
| 8 | 0x01FE | 0x01FF | Shop enter |
| 9 | 0x01FC | 0x01FD | Shop item |
| 10 | 0x01F2 | 0x01F3 | Shop buy |
| 11 | 0x01F4 | 0x01F5 | Shop sell |
| 12 | 0x0200 | 0x0201 | Shop exit |
| 13 | 0x029D | 0x029E | BB directory |
| 14 | 0x029F | 0x02A0 | BB subdirectory |
| 15 | 0x02A1 | 0x02A2 | BB memo dir |
| 16 | 0x02A3 | 0x02A4 | BB read post |
| 17 | 0x02A5 | 0x02A6 | BB write post |
| 18 | 0x02A7 | 0x02A8 | BB delete post |
| 19 | 0x02B1 | 0x02B2 | BB mkdir |
| 20 | 0x02B3 | 0x02B4 | BB rmdir |
| 21 | 0x02B5 | 0x02B6 | BB mksubdir |
| 22 | 0x02B7 | 0x02B8 | BB rmsubdir |
| 23 | 0x01A2 | 0x01A3 | Party list |
| 24 | 0x01A4 | 0x022B | Party entry (non-sequential reply!) |
| 25 | 0x01E6 | 0x01E7 | Allow join |
| 26 | 0x025B | 0x025C | Cancel join |
| 27 | 0x022C | 0x022F | Party unite (gap in reply!) |
| 28 | 0x0230 | 0x0231 | Allow unite |
| 29 | 0x023B | 0x023C | Area list |
| 30 | 0x01AF | 0x01B0 | Teleport list |
| 31 | 0x023E | 0x023F | Explain/help |
| 32 | 0x04E0 | 0x0046 | Special registration |
| 33 | 0x0233 | 0x0234 | Mirror dungeon |
| 34 | 0x0240 | 0x0241 | Find user 2 |
| 35 | 0x0298 | 0x0299 | Class list |
| 36 | 0x029A | 0x029B | Class change |
| 37 | 0x01C1 | 0x01C4 | Move type 1 |
| 38 | 0x01C2 | 0x01C4 | Move type 2 (shares reply with 37!) |
| 39 | 0x01AC | 0x01AD | Camp enter |
| 40 | 0x01DF | 0x01E0 | Set move mode |
| 41 | 0x02F7 | 0x02F8 | Give up |
| 42 | 0x01D3 | 0x01D4 | Set position |
| 43 | 0x01D6 | 0x02D8 | ? (non-sequential) |
| 44 | 0x02D9 | 0x02DA | ? |
| 45 | 0x01B3 | 0x01B4 | Camp exit |
| 46 | 0x0204 | 0x0205 | Equip |
| 47 | 0x026C | 0x026D | Disarm |
| 48 | 0x02E8 | 0x02E9 | Use skill |
| 49 | 0x02F5 | 0x02F6 | Change parameters |
| 50 | 0x0243 | 0x0244 | Encounter monster |
| 51 | 0x0221 | 0x0222 | Battle command |
| 52 | 0x0224 | 0x0225 | Battle change mode |
| 53 | 0x0296 | 0x0297 | Battle effect end |
| 54 | 0x01EA | 0x01EB | Battle end |
| 55 | 0x01E3 | 0x01E4 | Cancel encounter |
| 56 | 0x0235 | 0x0236 | ? |
| 57 | 0x01CF | 0x01D0 | Exec event |
| 58 | 0x0293 | 0x0294 | Give item |
| 59 | 0x02D0 | 0x02D1 | Use item |
| 60 | 0x0289 | 0x028D | Sell (gap in reply!) |
| 61 | 0x028E | 0x028F | Buy |
| 62 | 0x0290 | 0x0291 | Trade cancel |
| 63 | 0x02ED | 0x02EE | Compound |
| 64 | 0x0275 | 0x0276 | Confirm level up |
| 65 | 0x0277 | 0x0278 | Level up |
| 66 | 0x02B9 | 0x02BA | Skill list |
| 67 | 0x02E0 | 0x02E1 | Learn skill |
| 68 | 0x02E2 | 0x02E3 | Skill up |
| 69 | 0x02E4 | 0x02E5 | Equip skill |
| 70 | 0x02E6 | 0x02E7 | Disarm skill |
| 71 | 0x0268 | 0x0269 | Select theme |
| 72 | 0x026A | 0x026B | Check theme |
| 73 | 0x02A9 | 0x02AA | Mail list |
| 74 | 0x02AB | 0x02AC | Get mail |
| 75 | 0x02AD | 0x02AE | Send mail |
| 76 | 0x02AF | 0x02B0 | Delete mail |
| 77 | 0x02BB | 0x02BC | Colosseum waiting |
| 78 | 0x02BE | 0x02BF | Colosseum exit |
| 79 | 0x02C1 | 0x02C2 | Colosseum list |
| 80 | 0x02C3 | 0x02C4 | Colosseum entry |
| 81 | 0x02C5 | 0x02C6 | Colosseum cancel |
| 82 | 0x02C8 | 0x02C9 | Colosseum field entry |
| 83 | 0x02CD | 0x02CE | Colosseum ranking |

## Additional paired entries (from PAIRED_TABLE in config.py at file 0x043424)

These entries precede the table at 0x043484 — they cover the login/session flow:

| Client Sends | Server Replies | Category |
|---|---|---|
| 0x0035 | 0x01E8 | INIT → ESP_NOTICE |
| 0x019E | 0x019F | Login request → Update chardata |
| 0x01AA | 0x02F9 | Update chardata reply → Chardata request |
| 0x0B6C | 0x02F9 | Chardata2 notice → Chardata request |
| 0x019A | 0x019B | Logout → GOTOLIST |
| 0x019C | 0x019D | GOTOLIST notice → Information notice |
| 0x01B7 | 0x01B8 | Find user → Find user reply |
| 0x026F | 0x0270 | Store list → Store enter |
| 0x0271 | 0x0272 | Game world → Store in |
| 0x020C | 0x020D | Seat list req → Seat list |
| 0x0216 | 0x0217 | Tavern entry → Tavern entry ack |
| 0x01F8 | 0x01F9 | Table list req → Table list |
| 0x02FA | 0x01F9 | Alt table list → Table list (shares reply!) |
| 0x01FA | 0x01FB | Tavern exit → Tavern exit ack |

## GBR[0] Function Pointer Table (file 0x042530, mem 0x06052530)

256 entries, 4 bytes each (function pointers). Index 160 = 0x060232DC (sends 0x020E).
Notable indices:
- [130] = 0x0602219E (SV_Init)
- [131] = 0x060221F8 (SV_Setup)
- [132] = 0x06022298 (SV polling)
- [147-255] = SCMD send command functions
