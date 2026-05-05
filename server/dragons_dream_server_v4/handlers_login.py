"""
Login flow handlers: 0x0035 (INIT), 0x019E (LOGIN), 0x01AA (UPDATE_CHARDATA),
0x0B6C (CHARDATA2), 0x019A (LOGOUT), 0x019C (GOTOLIST), 0x02F5 (CHANGE_PARA).
Verbatim login protocol from v3, enhanced with DB-backed character state.
"""
import struct
import asyncio
import logging
from .config import *
from .protocol import sjis_pad, build_game_msg

log = logging.getLogger("DD-Server")


async def h_init(session, msg_type, payload, param1):
    """
    0x0035 -> ESP_NOTICE (0x01E8): 51 bytes
    First game message after session establishment. Verbatim from v3.
    """
    log.info("[S%d] INIT received (%d bytes payload)", session.sid, len(payload))

    reconnect_flag = 0
    name_bytes = b'\x00' * 16
    if len(payload) >= 62:
        version_str = payload[0:8].rstrip(b'\x00').decode('ascii', errors='replace')
        name_bytes = payload[32:48]  # first 16 bytes of 24-byte name field
        reconnect_flag = struct.unpack('>H', payload[60:62])[0]
        login_mode = struct.unpack('>H', payload[62:64])[0] if len(payload) >= 64 else 0
        proto_ver = struct.unpack('>H', payload[64:66])[0] if len(payload) >= 66 else 0
        try:
            name_str = name_bytes.rstrip(b'\x00').decode('shift_jis', errors='replace')
        except Exception:
            name_str = name_bytes.hex()
        log.info("[S%d] INIT: version=%r, name=%r, reconnect=0x%04X, mode=%d, proto=%d",
                 session.sid, version_str, name_str, reconnect_flag, login_mode, proto_ver)

    # Load or create character from DB
    db = session.db
    char = db.load_character_by_name(name_bytes)
    if char is None:
        # New character — create with defaults
        char_id = db.create_character(name_bytes)
        char = db.load_character(char_id)
    char.reconnect_flag = reconnect_flag

    # Force zone_id=4 on every login. dest_index in h_gotolist_notice is always
    # 4 (hardcoded), so client always loads zone 4 data. ZONE_CONNECTIONS must
    # use zone 4's connections [3, 5] for correct GOTOLIST entries.
    # Evidence (Test 51, dd_server_20260408_173612.log): zone_id=5 persisted
    # from previous test → ZONE_CONNECTIONS[5]=[4,6] → wrong target_match=6.
    if char.zone_id != 4:
        log.info("[S%d] INIT: zone_id=%d → forcing to 4 (dest_index always 4)",
                 session.sid, char.zone_id)
        char.zone_id = 4
        char.map_id = 4
        db.save_character(char)

    session.char = char
    session.char_name = char.char_name
    session._gotolist_count = 0  # Reset loop breaker for fresh connection
    session._in_game_world = False  # Set True on 0x026F (game world entry)

    # Send ESP_NOTICE (0x01E8): 51 bytes
    esp = bytearray(51)
    struct.pack_into('>H', esp, 0, 0)                # status = 0
    struct.pack_into('>H', esp, 2, session.session_param)
    struct.pack_into('>H', esp, 4, session.connection_id)
    esp[6] = 6                                         # game_mode = 6 (field/map)
    esp[7] = 0                                         # sub_mode
    struct.pack_into('>I', esp, 8, 1)                 # server_id
    esp[12:28] = sjis_pad("DD Revival", 16)           # server_name
    await session.send_msg(MSG_ESP_NOTICE, bytes(esp))

    # Also send UPDATE_CHARDATA_REQUEST (0x019F): 24 bytes — empirically required
    resp = bytearray(24)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, 1)
    struct.pack_into('>I', resp, 4, char.char_id)
    resp[8:24] = char.char_name[:16]
    await session.send_msg(MSG_UPDATE_CHARDATA_REQ, bytes(resp))
    session.login_phase = 1


async def h_login_request(session, msg_type, payload, param1):
    """
    0x019E -> UPDATE_CHARDATA_REQUEST (0x019F): 24 bytes
    Client sends login credentials with character name and skill slots.
    """
    if len(payload) >= 20:
        name_bytes = payload[4:20]
        session.char_name = name_bytes
        if session.char:
            session.char.char_name = name_bytes
        try:
            name_str = name_bytes.rstrip(b'\x00').decode('shift_jis', errors='replace')
        except Exception:
            name_str = name_bytes.hex()
        log.info("[S%d] LOGIN: name=%r", session.sid, name_str)

    # Parse skill slots from payload if present (offsets 44-60)
    if session.char and len(payload) >= 60:
        for i in range(8):
            off = 44 + i * 2
            if off + 2 <= len(payload):
                session.char.skill_slots[i] = struct.unpack_from('>H', payload, off)[0]

    # Parse class info
    if session.char and len(payload) >= 23:
        session.char.char_class = payload[22] & 0x07  # zone_class field has class

    char = session.char
    resp = bytearray(24)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, 1)
    struct.pack_into('>I', resp, 4, char.char_id if char else 1)
    resp[8:24] = (char.char_name if char else session.char_name)[:16]
    await session.send_msg(MSG_UPDATE_CHARDATA_REQ, bytes(resp))

    # Update DB
    if char:
        char.last_login = True
        session.db.save_character(char)

    session.login_phase = 2


async def h_update_chardata_reply(session, msg_type, payload, param1):
    """
    0x01AA -> CHARDATA_REQUEST (0x02F9) + CHARDATA_REPLY(1,2,3) + INFORMATION_NOTICE
    """
    log.info("[S%d] UPDATE_CHARDATA_REPLY (login_phase=%d)", session.sid, session.login_phase)

    if session.login_phase >= 3:
        log.info("[S%d] CHARDATA already sent, sending 0x02F9 only", session.sid)
        await _send_chardata_request(session)
        return

    await _send_chardata_request(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type1(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type2(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type3(session)
    await asyncio.sleep(0.05)
    await _send_information_notice(session)
    session.login_phase = 3

    await asyncio.sleep(0.05)
    await _send_map_notice(session)
    await asyncio.sleep(0.05)
    await _send_knownmap_notice(session)
    await asyncio.sleep(0.05)
    await _send_chardata_notice(session)
    session.login_phase = 4

    # Register in world
    from .world import world
    world.register_player(session)


async def h_chardata2_notice(session, msg_type, payload, param1):
    """0x0B6C -> CHARDATA_REQUEST + push updated char data."""
    log.info("[S%d] CHARDATA2_NOTICE (%d bytes)", session.sid, len(payload))
    await _send_chardata_request(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type1(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type2(session)
    await asyncio.sleep(0.05)
    await _send_chardata_reply_type3(session)
    session.login_phase = 4


async def h_logout(session, msg_type, payload, param1):
    """
    0x019A -> GOTOLIST_REQUEST (0x019B): destination list.
    NOT a disconnect — client shows destination selection UI (world map).

    MUST use NATURAL values: zone_cd = dest_zid, server_info = dest_zid.
    This is the ONLY approach proven to work on hardware.

    Evidence from 6 hardware tests:
      - Old success (200832): si=[4,3,5] zone_cd=[4,3,5] NATURAL → tavern OK
      - Test 49: si=[4,4,4] zone_cd=[4,3,5] FORCED → post-tavern HANG
      - Test 52: si=[1,3,4] zone_cd=[4,3,5] FORCED → post-tavern HANG
      - Test 53: si=[4,3,4] zone_cd=[4,3,5] FORCED → post-tavern HANG
      - Test 54: si=[4,4,4] zone_cd=[4,4,4] FORCED → post-tavern HANG
      - Test 55: si=[4,4,4] zone_cd=[4,4,4] FORCED → post-tavern HANG
    Rule: ANY forced values break the post-tavern GOTOLIST. Natural only.

    With natural si, only Cave(si=4) matches zone_cd_id=4 → sends 0x026F.
    Forest(si=3) and DT(si=5) send 0x019C → zone transition.
    User navigates map to tavern building → 0x01F8 (tavern table list).
    Tavern party system handles dungeon transition (no GOTOLIST zone change).
    """
    gotolist_count = getattr(session, '_gotolist_count', 0) + 1
    session._gotolist_count = gotolist_count
    log.info("[S%d] LOGOUT (destination list request, count=%d)", session.sid, gotolist_count)

    from .world import world
    from .game_data import ZONES, ZONE_CONNECTIONS

    char = session.char
    zone_id = char.zone_id if char else 1
    destinations = ZONE_CONNECTIONS.get(zone_id, [1])
    if zone_id not in destinations:
        destinations = [zone_id] + destinations

    # Track adventure zone for field mode routing
    non_self = [dz for dz in destinations if dz != zone_id]
    adventure_zone = max(non_self) if non_self else None
    session._target_field_zone = adventure_zone

    entry_count = len(destinations)
    resp = bytearray(8 + entry_count * 28)
    struct.pack_into('>H', resp, 0, 0)      # result_code = 0 (success)
    struct.pack_into('>H', resp, 2, entry_count)
    struct.pack_into('>I', resp, 4, 0)       # page_token = 0

    server_info_list = []
    for i, dest_zid in enumerate(destinations):
        off = 8 + i * 28
        struct.pack_into('>I', resp, off, dest_zid)       # dest_id
        # NATURAL values only — byte-for-byte match with old success log.
        # Old success 0x019B hex: Cave=00000004 0004 0004 0000 04 00
        #                         Forest=00000003 0003 0003 0000 03 00
        #                         DT=00000005 0005 0005 0000 05 00
        struct.pack_into('>H', resp, off + 4, dest_zid)   # zone_cd = NATURAL
        zone_def = ZONES.get(dest_zid)
        struct.pack_into('>H', resp, off + 6, zone_def.map_id if zone_def else 1)
        if zone_def:
            resp[off + 8] = zone_def.map_x & 0xFF
            resp[off + 9] = zone_def.map_y & 0xFF

        si = dest_zid & 0xFF  # server_info = NATURAL (matches zone_cd)
        resp[off + 10] = si

        server_info_list.append(si)
        resp[off + 11] = 0
        name = sjis_pad(zone_def.name if zone_def else "Unknown", 16)
        resp[off + 12:off + 28] = name

    log.info("[S%d] GOTOLIST: %d entries, si=%s (NATURAL), destinations=%s",
             session.sid, entry_count, server_info_list, destinations)
    await session.send_msg(MSG_GOTOLIST_REQUEST, bytes(resp))


async def h_gotolist_notice(session, msg_type, payload, param1):
    """
    0x019C: Client selected destination from GOTOLIST (server_info mismatch).

    Full zone transition on EVERY 0x019C, always dest_index=4.

    Evidence for this approach (Test 47, dd_server_20260408_064558.log):
      - Sending ONLY 0x019D (no zone transition) → client permanent hang.
        Client expects full transition after every 0x019C.
      - Previous "2nd transition always fails" conclusion was based on 46 tests
        that ALL used dest_index=5, 6, or 7. NONE tested dest_index=4 on cycle 2+.
      - dest_index=4 on cycle 1: ALWAYS WORKS. CD data for zone 4 already loaded.
      - dest_index=4 on cycle 2+: CD data already in RAM (no disc read needed).
        init_zone_transition resets client, SV_Init, server re-establishes.
        This should work identically to cycle 1 since no new data needs loading.
    """
    dest_id = 0
    if len(payload) >= 4:
        dest_id = struct.unpack('>I', payload[:4])[0]

    transition_count = getattr(session, '_zone_transition_count', 0) + 1
    session._zone_transition_count = transition_count
    log.info("[S%d] GOTOLIST_NOTICE: dest_id=%d, transition_count=%d",
             session.sid, dest_id, transition_count)

    # Step 1: Send 0x019D (paired ack for 0x019C)
    await session.send_msg(MSG_INFORMATION_NOTICE,
                           struct.pack('>HHI', 0, 0, 0))
    log.info("[S%d] GOTOLIST: sent 0x019D (paired ack)", session.sid)

    # DO NOT update zone_id here. dest_index is always 4 (hardcoded), so the
    # client loads zone 4 data regardless of what dest_id the user clicked.
    # Updating zone_id to dest_id would cause ZONE_CONNECTIONS to use the wrong
    # zone's connections for subsequent GOTOLISTs.
    # Evidence (Test 50, dd_server_20260408_172547.log): zone_id was set to 5
    # (dest_id), causing post-tavern target_match=6 instead of 5. Temple entry
    # got non-matching server_info, user clicked Temple → 0x019C → cycle 2 fail.
    # Zone_id will be updated in h_store_in when user actually enters field mode.
    log.info("[S%d] GOTOLIST: dest_id=%d (zone_id stays %d, dest_index always 4)",
             session.sid, dest_id,
             session.char.zone_id if session.char else -1)

    # Step 2: Send 0x02EF (EXEC_EVENT_NOTICE)
    #
    # ZONE_PAIR_TEST MATRIX (2026-05-05): dest_index is now configurable per
    # test via env var DD_DEST_INDEX_MAP="cycle:value,cycle:value,...". Default
    # behavior matches the prior hardcoded value (always 4) so production runs
    # are unchanged.
    #
    # Examples:
    #   DD_DEST_INDEX_MAP="1:4,2:3"    # cycle 1 → dest_index=4, cycle 2 → 3
    #   DD_DEST_INDEX_MAP="1:4,2:5"    # cycle 1 → dest_index=4, cycle 2 → 5
    #   DD_DEST_INDEX_MAP="2:dest_id"  # cycle 2 → use the dest_id the user picked
    #
    # See ZONE_PAIR_TEST_MATRIX.md for the systematic test plan.
    import os
    map_str = os.environ.get('DD_DEST_INDEX_MAP', '').strip()
    dest_index_override = None
    if map_str:
        for entry in map_str.split(','):
            if ':' not in entry: continue
            cyc, val = entry.split(':', 1)
            try:
                if int(cyc.strip()) == transition_count:
                    if val.strip() == 'dest_id':
                        dest_index_override = dest_id
                    else:
                        dest_index_override = int(val.strip())
                    break
            except ValueError:
                pass
    dest_index = dest_index_override if dest_index_override is not None else 4
    await session.send_msg(MSG_EXEC_EVENT_NOTICE,
                           struct.pack('>BBBB', 0x00, dest_index, 0x00, 0x00))
    log.info("[S%d] GOTOLIST: sent 0x02EF dest_index=%d (user selected dest_id=%d, transition #%d)%s",
             session.sid, dest_index, dest_id, transition_count,
             " [OVERRIDE via DD_DEST_INDEX_MAP]" if dest_index_override is not None else "")

    # Step 3: Wait for CD load then re-establish session
    # Cycle 1: 4.0s for initial CD load. Cycle 2+: 2.0s (data already cached).
    session._zone_transitioning = True
    wait_time = 4.0 if transition_count == 1 else 2.0
    await asyncio.sleep(wait_time)

    await session._send_session_establishment()
    await asyncio.sleep(0.5)
    session._zone_transitioning = False

    # Step 4: Send ESP_NOTICE + UPDATE_CHARDATA_REQ
    # CRITICAL: Client NEVER sends 0x0035 after zone transition (connection SM
    # bit 7 set permanently after first INIT). These messages are the ONLY way
    # to advance the client past the black screen into GOTOLIST mode.
    # Evidence: Old success (dd_server_20260405_200832.log) sent ESP+UPDATE
    # after re-establish → client resumed GOTOLIST → timeout → 0x026F.
    # Test 48 (dd_server_20260408_154244.log) removed them → permanent black screen.
    esp = bytearray(51)
    struct.pack_into('>H', esp, 0, 0)
    struct.pack_into('>H', esp, 2, session.session_param)
    struct.pack_into('>H', esp, 4, session.connection_id)
    esp[6] = 6
    struct.pack_into('>I', esp, 8, 1)
    esp[12:28] = sjis_pad("DD Revival", 16)
    await session.send_msg(MSG_ESP_NOTICE, bytes(esp))

    char_id = session.char.char_id if session.char else 1
    update_pay = bytearray(24)
    struct.pack_into('>I', update_pay, 0, char_id)
    struct.pack_into('>I', update_pay, 4, char_id)
    update_pay[8:24] = session.char_name[:16]
    await session.send_msg(MSG_UPDATE_CHARDATA_REQ, bytes(update_pay))

    log.info("[S%d] GOTOLIST: zone transition #%d complete (ESP+UPDATE sent)",
             session.sid, transition_count)


async def h_change_para(session, msg_type, payload, param1):
    """
    0x02F5 - Full character state sync from client.

    Wire layout (from client-sent-payloads.md, send function at file 0x013D48):
      0       U8      char_class (chardata field 0x15)
      1       U8      char_sub_field (chardata field 0x17)
      2       U8      zone
      3       U8      zone2
      4       U8      level (chardata field 0x19)
      5-7     zeros
      8       U32 BE  experience (chardata+0x1C)
      12      U32 BE  gold (chardata+0x20)
      16-33   U16x9   stats_group_A (from chardata+0x92, near end of party_entry)
      34      U16     field_102
      36      U16     field_104
      38-55   U16x9   stats_group_B (chardata fields 64-78)
      56-67   U16x6   stats_group_C (chardata fields 84-94)
      68-73   U16x3   stats_group_D (chardata fields 96-100)
      74-121  U16x24  equipment (24 values)

    Responds with CHANGE_PARA_REQUEST (0x02F6): 2 bytes status.

    # AI-RECONSTRUCTED: Stat group mapping to 19-element base_stats/current_stats.
    # Client's party_entry struct (0xA4=164 bytes) stores stats at non-contiguous
    # offsets. Groups B+C+D cover party_entry bytes 64-100 (18 U16s = main stats).
    # Group A covers chardata+0x92=146 (9 U16s near struct end = derived/current).
    # field_102 and field_104 bridge the gap. Mapping: B(9)+C(6)+D(3)+field_104 →
    # base_stats[0:19]; A(9)+field_102 → current_stats[0:10], rest mirrored.
    # Evidence: literal pool at 0x013E90 contains 0x0092 (chardata stat offset),
    # 0x00A4 (party_entry stride), 0x1BE0 (party data base in session_ctx).
    """
    log.info("[S%d] CHANGE_PARA received (%d bytes)", session.sid, len(payload))

    char = session.char
    if not char:
        await session.send_msg(MSG_CHANGE_PARA_REQUEST, struct.pack('>H', 0))
        return

    # Parse header fields
    if len(payload) >= 5:
        char.char_class = payload[0] & 0x07
        char.zone_id = payload[2] if payload[2] > 0 else char.zone_id
        char.char_level = max(1, payload[4]) if payload[4] > 0 else char.char_level

    # Parse experience and gold
    if len(payload) >= 16:
        char.experience = struct.unpack_from('>I', payload, 8)[0]
        char.gold = struct.unpack_from('>I', payload, 12)[0]

    # Parse stats — 29 U16 values across 4 groups + 2 fields
    # AI-RECONSTRUCTED: Map groups B+C+D+field_104 → base_stats[0:19],
    # groups A+field_102 → current_stats[0:10]. Ordering may not perfectly
    # match original game, but roundtrip is consistent within revival server.
    if len(payload) >= 74:
        # base_stats[0:9] ← Group B (chardata fields 64-78)
        for i in range(9):
            char.base_stats[i] = struct.unpack_from('>H', payload, 38 + i * 2)[0]
        # base_stats[9:15] ← Group C (chardata fields 84-94)
        for i in range(6):
            char.base_stats[9 + i] = struct.unpack_from('>H', payload, 56 + i * 2)[0]
        # base_stats[15:18] ← Group D (chardata fields 96-100)
        for i in range(3):
            char.base_stats[15 + i] = struct.unpack_from('>H', payload, 68 + i * 2)[0]
        # base_stats[18] ← field_104
        char.base_stats[18] = struct.unpack_from('>H', payload, 36)[0]

        # current_stats[0:9] ← Group A (chardata+0x92)
        for i in range(9):
            char.current_stats[i] = struct.unpack_from('>H', payload, 16 + i * 2)[0]
        # current_stats[9] ← field_102
        char.current_stats[9] = struct.unpack_from('>H', payload, 34)[0]
        # current_stats[10:19] ← mirror from base_stats
        for i in range(10, 19):
            char.current_stats[i] = char.base_stats[i]

    # Parse equipment (24 U16 values at offset 74, 48 bytes)
    # AI-RECONSTRUCTED: CHANGE_PARA sends 24 U16 equipment values.
    # Character model uses 48-element list (24 slots x 2 fields).
    # Stored in equipment[0:24]; equipment[24:48] preserved from DB.
    if len(payload) >= 122:
        for i in range(24):
            char.equipment[i] = struct.unpack_from('>H', payload, 74 + i * 2)[0]

    session.db.save_character(char)
    log.info("[S%d] CHANGE_PARA: class=%d level=%d zone=%d exp=%d gold=%d equip=%s",
             session.sid, char.char_class, char.char_level, char.zone_id,
             char.experience, char.gold,
             'parsed' if len(payload) >= 122 else 'short')

    await session.send_msg(MSG_CHANGE_PARA_REQUEST, struct.pack('>H', 0))


# ── Helper functions (shared with handlers) ──

async def _send_chardata_request(session):
    """Send CHARDATA_REQUEST (0x02F9): 172 bytes with full character data."""
    char = session.char
    resp = bytearray(172)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, 1)
    struct.pack_into('>I', resp, 4, char.char_id if char else 1)
    name = (char.char_name if char else session.char_name)[:16]
    resp[8:8 + len(name)] = name

    if char:
        resp[24] = 0
        resp[25] = 0
        resp[26] = char.char_race
        resp[27] = char.char_gender
        resp[28] = char.char_level
        struct.pack_into('>I', resp, 32, char.experience)
        struct.pack_into('>I', resp, 36, char.gold)
        for i in range(8):
            struct.pack_into('>H', resp, 40 + i * 2, char.skill_slots[i])
        resp[58] = char.char_class
        resp[63] = char.char_level
    resp[65] = 0  # skill_flag
    resp[67] = 1  # status_flag = has extended
    resp[69] = 0  # item_flag
    resp[71] = 0  # license_flag

    if char:
        for i in range(19):
            struct.pack_into('>H', resp, 72 + i * 2, char.base_stats[i])
            struct.pack_into('>H', resp, 110 + i * 2, char.current_stats[i])
        resp[148:156] = char.appearance[:8]
        for i in range(8):
            struct.pack_into('>H', resp, 156 + i * 2, char.skill_levels[i])

    await session.send_msg(MSG_CHARDATA_REQUEST, bytes(resp))


async def _send_chardata_reply_type1(session):
    """CHARDATA_REPLY (0x02D2) TYPE 1: char_list, 24B/entry."""
    char = session.char
    entry = bytearray(24)
    name = (char.char_name if char else session.char_name)[:16]
    entry[0:len(name)] = name
    if char:
        struct.pack_into('>H', entry, 16, char.experience & 0xFFFF)
        entry[18] = char.char_class
        entry[19] = char.char_race
        entry[20] = char.char_gender
        entry[21] = char.char_level

    header = bytearray(8)
    header[0] = 1
    header[1] = 1
    header[2] = 1
    header[3] = 1
    struct.pack_into('>I', header, 4, len(entry))
    await session.send_msg(MSG_CHARDATA_REPLY, bytes(header) + bytes(entry))


async def _send_chardata_reply_type2(session):
    """CHARDATA_REPLY (0x02D2) TYPE 2: char_detail, 52B/entry. Triggers system file save.

    Wire layout (from handler-payloads-detailed.md):
      0       U16 BE   char_slot_id
      2       U8       class
      3       U8       sub_class
      4       16B      char_name
      20      U16 BE   experience
      22      8B       stat_bytes[8] (STR,VIT,INT,MND,AGI,DEX,LUK,CHA)
      30      2B       padding
      32      U32 BE   gold
      36      U16[8]   equipment_slots
    """
    char = session.char
    entry = bytearray(52)
    struct.pack_into('>H', entry, 0, 0)
    if char:
        entry[2] = char.char_class
        entry[3] = 0
        entry[4:20] = char.char_name[:16]
        struct.pack_into('>H', entry, 20, char.experience & 0xFFFF)
        stat_map = [2, 3, 4, 5, 6, 7, 8, 9]
        for i, si in enumerate(stat_map):
            entry[22 + i] = min(char.base_stats[si], 255)
        struct.pack_into('>I', entry, 32, char.gold)
        # Equipment slots at offset 36: 8 x U16 BE (first 8 of 24 equipment values)
        for i in range(8):
            struct.pack_into('>H', entry, 36 + i * 2, char.equipment[i] & 0xFFFF)

    header = bytearray(8)
    header[0] = 2
    header[1] = 1
    header[2] = 1
    header[3] = 1
    struct.pack_into('>I', header, 4, len(entry))
    await session.send_msg(MSG_CHARDATA_REPLY, bytes(header) + bytes(entry))


async def _send_chardata_reply_type3(session):
    """CHARDATA_REPLY (0x02D2) TYPE 3: inventory, 24B/entry."""
    char = session.char
    items = session.db.get_inventory(char.char_id) if char else []

    header = bytearray(8)
    header[0] = 3
    header[1] = 1
    header[2] = 1
    header[3] = len(items) & 0xFF

    if items:
        entry_size = 24
        struct.pack_into('>I', header, 4, entry_size * len(items))
        payload = bytearray(header)
        for item in items:
            entry = bytearray(24)
            entry[0:16] = item.item_data[:16]
            payload.extend(entry)
        await session.send_msg(MSG_CHARDATA_REPLY, bytes(payload))
    else:
        struct.pack_into('>I', header, 4, 0)
        await session.send_msg(MSG_CHARDATA_REPLY, bytes(header))


async def _send_information_notice(session):
    """INFORMATION_NOTICE (0x019D): 8 bytes.

    CORRECTED 2026-04-01: Handler at file 0x3DDA stores:
      status(U16) → g_state+4, info_type(U16) → g_state+0xA0,
      info_value(U32) → g_state+0x94. Evidence: literal pool at
      0x3E22=0x00A0, 0x3E24=0x0094 (NOT 0x90/0x8E as previously claimed).

    g_state+0x94 is an echo token — client echoes it back in msg 0x01A2.
    g_state+0xA0 is write-only — never read by client code.
    Neither field affects game state transitions or init flags.
    """
    # AI-RECONSTRUCTED: INFORMATION_NOTICE is a simple ack. info_value at
    # g_state+0x94 is echoed back via 0x01A2 by 6+ message handlers.
    # No behavioral effect. Evidence: binary search found zero readers
    # that branch on g_state+0x94 value — all just echo it to server.
    await session.send_msg(MSG_INFORMATION_NOTICE, struct.pack('>HHI', 0, 0, 0))


async def _send_map_notice(session, width=48, rows=48):
    """MAP_NOTICE (0x01DE): map grid data."""
    from .game_data import ZONES
    char = session.char
    zone = ZONES.get(char.zone_id if char else 1)
    if zone:
        width, rows = zone.width, zone.height

    row_bytes = (width + 7) // 8
    total_data = row_bytes * rows

    if zone:
        map_data = zone.walkability[:total_data]
        if len(map_data) < total_data:
            map_data += b'\xff' * (total_data - len(map_data))
    else:
        map_data = b'\xff' * total_data

    payload = bytearray(8 + total_data)
    payload[0] = width & 0xFF
    payload[1] = rows & 0xFF
    struct.pack_into('>I', payload, 4, total_data)
    payload[8:8 + total_data] = map_data
    await session.send_msg(MSG_MAP_NOTICE, bytes(payload))


async def _send_knownmap_notice(session):
    """KNOWNMAP_NOTICE (0x01D2): 2 bytes."""
    await session.send_msg(MSG_KNOWNMAP_NOTICE, struct.pack('>H', 0))


async def _send_chardata_notice(session):
    """CHARDATA_NOTICE (0x01AB): 76 bytes — player character in game world."""
    char = session.char
    payload = bytearray(76)
    if char:
        struct.pack_into('>H', payload, 0, char.char_id & 0xFFFF)
        payload[2:2 + min(16, len(char.char_name))] = char.char_name[:16]
        payload[24] = 0
        payload[25] = 0
        payload[26] = char.char_race
        payload[27] = char.char_gender
        payload[28] = char.char_level
        struct.pack_into('>I', payload, 32, char.experience)
        struct.pack_into('>I', payload, 36, char.gold)
        for i in range(8):
            struct.pack_into('>H', payload, 40 + i * 2, char.current_stats[i])
        payload[58] = char.char_class
        payload[63] = char.char_level
    payload[67] = 1  # has_equip_stats = nonzero → skip
    payload[71] = 1  # has_equip_items = nonzero → skip
    await session.send_msg(MSG_CHARDATA_NOTICE, bytes(payload))
    log.info("[S%d] Sent CHARDATA_NOTICE (76B, char_id=%d)",
             session.sid, char.char_id if char else 0)
