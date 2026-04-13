# Server v4 Architecture & File Reference

## Package: `server/dragons_dream_server_v4/`

### Core Infrastructure
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 1 | Version string (4.0.0) |
| `__main__.py` | 97 | Entry point, argparse, asyncio server |
| `config.py` | 208 | MSG_* constants, PAIRED_TABLE (108 entries), stat tables |
| `protocol.py` | 59 | sv_encode, build_game_msg, parse_game_msg, sjis_pad (verbatim from v3) |
| `session.py` | 527 | DDSession: BBS, establishment, keepalive, dispatch (verbatim transport from v3) |
| `db.py` | 516 | SQLite CRUD: characters, inventory, skills, mail, bulletin |
| `models.py` | 154 | Data classes: Character, Item, Monster, Skill, Zone, Shop, CombatEntity |
| `game_data.py` | 222 | Static data: 20 monsters, 30 items, 16 skills, 9 zones, 5 shops |
| `world.py` | 115 | World singleton: zone players, broadcasting, encounter rolls |
| `combat_engine.py` | 316 | Turn-based combat: state machine, damage formulas, wire builders |

### Handler Modules (108 total paired handlers)
| File | Lines | Handlers |
|------|-------|----------|
| `handlers_login.py` | 443 | h_init, h_login_request, h_update_chardata_reply, h_chardata2_notice, h_logout, h_gotolist_notice, h_change_para |
| `handlers_movement.py` | 144 | h_move, h_map_change_notice, h_camp_in/out, h_setpos, h_giveup, h_set_movemode |
| `handlers_combat.py` | 202 | start_encounter, h_btl_cmd, h_btl_end, h_cancel_encount, h_encountmonster |
| `handlers_shop.py` | 219 | h_shop_in/out, h_shop_list, h_shop_item, h_shop_buy, h_shop_sell |
| `handlers_inventory.py` | 192 | h_equip, h_disarm, h_use_item, h_compound, h_give_item |
| `handlers_skills.py` | 210 | h_skill_list, h_learn_skill, h_skillup, h_equip_skill, h_disarm_skill, h_use_skill |
| `handlers_leveling.py` | 145 | h_confirm_lvlup, h_levelup, h_class_list, h_class_change |
| `handlers_party.py` | 82 | h_partylist, h_partyentry, h_allow_join, h_cancel_join, h_partyunite, h_partyexit, h_party_breakup |
| `handlers_social.py` | 356 | chat, mail (4), bulletin (8), sakaya (7), find_user |
| `handlers_misc.py` | 334 | colosseum (7), dice, cards, events, teleport, area_list, store, user_list, mirror, + build_minimal_reply fallback |

### Admin & Operations
| File | Purpose |
|------|---------|
| `admin_gui.py` | Tkinter GUI: 9 tabs for full server operator control |
| `../run_server.bat` | Windows launcher with --host/--port/--db/--log/--gui flags |

## Key Design Decisions
- **Transport code verbatim from v3** — proven BBS + SV IV + session protocol preserved exactly
- **All AI-RECONSTRUCTED comments** cite specific binary offsets (e.g., "handler at 0x7DCC reads U16 at [6:8]")
- **build_minimal_reply() fallback** — any unhandled msg_type gets safe ack, Saturn never hangs
- **SQLite WAL mode** for concurrent read during writes
- **asyncio-only** — no threads for game logic, no GIL issues

## DB Schema (dd_world.db)
- `characters`: char_id, name(16B SJIS), class, level, race, gender, exp, gold, base_stats(38B), current_stats(38B), appearance(8B), skill_slots(16B), skill_levels(16B), equipment(96B), zone/map/pos/facing
- `inventory`: char_id, slot_index, item_data(16B), item_id, type_a/b, equip_slot, price, is_equipped
- `skills`: char_id, skill_id, skill_level, equipped_slot
- `mail`: to/from char_id, from_name(16B), subject(40B), body, is_read
- `bulletin`: author_id, dir_name, subdir_name, subject(40B), body
