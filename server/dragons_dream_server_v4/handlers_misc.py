"""
Miscellaneous handlers: colosseum, dice, cards, events, teleport, store, themes,
user/area lists, and the _build_minimal_reply fallback.
"""
import struct
import logging
from .config import *
from .protocol import sjis_pad
from .game_data import ZONES, ZONE_CONNECTIONS

log = logging.getLogger("DD-Server")


# ── Colosseum ──

async def h_colo_waiting(session, msg_type, payload, param1):
    """0x02BB -> COLO_WAITING_REQUEST (0x02BC): 2 bytes."""
    await session.send_msg(MSG_COLO_WAITING_REQ, struct.pack('>H', 0))


async def h_colo_exit(session, msg_type, payload, param1):
    """0x02BE -> COLO_EXIT_REQUEST (0x02BF): 2 bytes."""
    await session.send_msg(MSG_COLO_EXIT_REQUEST, struct.pack('>H', 0))


async def h_colo_list(session, msg_type, payload, param1):
    """0x02C1 -> COLO_LIST_REQUEST (0x02C2): 8 bytes (empty list)."""
    await session.send_msg(MSG_COLO_LIST_REQUEST, struct.pack('>HHI', 0, 0, 0))


async def h_colo_entry(session, msg_type, payload, param1):
    """0x02C3 -> COLO_ENTRY_REQUEST (0x02C4): 4 bytes."""
    await session.send_msg(MSG_COLO_ENTRY_REQUEST, struct.pack('>HBB', 1, 0, 0))


async def h_colo_cancel(session, msg_type, payload, param1):
    """0x02C5 -> COLO_CANCEL_REQUEST (0x02C6): 2 bytes."""
    await session.send_msg(MSG_COLO_CANCEL_REQUEST, struct.pack('>H', 0))


async def h_colo_fldent(session, msg_type, payload, param1):
    """0x02C8 -> COLO_FLDENT_REQUEST (0x02C9): 2 bytes."""
    await session.send_msg(MSG_COLO_FLDENT_REQUEST, struct.pack('>H', 0))


async def h_colo_ranking(session, msg_type, payload, param1):
    """0x02CD -> COLO_RANKING_REQUEST (0x02CE): 8 bytes."""
    await session.send_msg(MSG_COLO_RANKING_REQ, struct.pack('>HBBI', 0, 0, 0, 0))


# ── Dice / Cards ──

async def h_cast_dice(session, msg_type, payload, param1):
    """
    0x02D4 -> CAST_DICE_REQUEST (0x02D5): 6 bytes.
    AI-RECONSTRUCTED: Random dice roll 1-6.
    """
    import random
    result = random.randint(1, 6)
    resp = bytearray(6)
    struct.pack_into('>H', resp, 0, 0)     # status
    resp[2] = result                        # dice_result
    await session.send_msg(MSG_CAST_DICE_REQUEST, bytes(resp))


async def h_card(session, msg_type, payload, param1):
    """0x02DB -> CARD_REQUEST (0x02DC): 2 bytes."""
    await session.send_msg(MSG_CARD_REQUEST, struct.pack('>H', 0))


# ── Events ──

async def h_exec_event(session, msg_type, payload, param1):
    """
    0x01CF -> EXEC_EVENT_REQUEST (0x01D0).
    Event execution — reject with status=1 to skip event data safely.
    """
    await session.send_msg(MSG_EXEC_EVENT_REQUEST, struct.pack('>H', 1))


# ── Teleport ──

async def h_teleport_list(session, msg_type, payload, param1):
    """
    0x01AF -> TELEPORTLIST_REQUEST (0x01B0): 12 + N*20 bytes.
    Return available teleport destinations.
    """
    char = session.char
    zone_id = char.zone_id if char else 1
    destinations = ZONE_CONNECTIONS.get(zone_id, [1])

    resp = bytearray(12 + len(destinations) * 20)
    struct.pack_into('>H', resp, 0, 0)                    # status
    struct.pack_into('>H', resp, 4, len(destinations))    # entry_count

    for i, dest_zid in enumerate(destinations):
        off = 12 + i * 20
        resp[off] = 0x21                                   # type (required by client validation)
        zone_def = ZONES.get(dest_zid)
        if zone_def:
            name = sjis_pad(zone_def.name, 16)
            resp[off + 1:off + 17] = name

    await session.send_msg(MSG_TELEPORTLIST_REQ, bytes(resp))


# ── Area List ──

async def h_area_list(session, msg_type, payload, param1):
    """0x023B -> AREA_LIST_REQUEST (0x023C): 8 bytes."""
    await session.send_msg(MSG_AREA_LIST_REQUEST, struct.pack('>HHI', 0, 0, 0))


async def h_explain(session, msg_type, payload, param1):
    """0x023E -> EXPLAIN_REQUEST (0x023F): 4 bytes."""
    await session.send_msg(MSG_EXPLAIN_REQUEST, struct.pack('>HH', 0, 0))


# ── Store ──

async def h_store_list(session, msg_type, payload, param1):
    """0x026F -> STORE_LIST_REQUEST (0x0270): 8 bytes.

    Game world entry signal. Client sends 0x026F when GOTOLIST entry server_info
    matches zone_cd_id. First time = tavern entry. Subsequent = temple/dungeon.

    Evidence (dd_server_20260405_200832.log line 275): 0x026F received after
    GOTOLIST selection, followed by 0x0270 → 0x0271 → 0x0272 → tavern sequence.
    """
    store_count = getattr(session, '_store_list_count', 0) + 1
    session._store_list_count = store_count
    log.info("[S%d] STORE_LIST (0x026F): game world entry #%d, %d bytes",
             session.sid, store_count, len(payload))
    session._in_game_world = True
    await session.send_msg(MSG_STORE_LIST_REQUEST, struct.pack('>HHI', 0, 0, 0))


async def h_store_in(session, msg_type, payload, param1):
    """0x0271 -> STORE_IN_REQUEST (0x0272): 2 or 3 bytes.

    Handler at file 0x4BFE: reads status(U16) → context+4.
    If status==0: reads store_flag(U8) → context+0xA0 as U16.
    If status!=0: skips store_flag entirely.

    TWO MODES based on game state:
    1. First 0x026F (initial game world entry → tavern):
       status=1 (reject, 2B). Client sends 0x019A → GOTOLIST → tavern navigation.
       Evidence: old success (dd_server_20260405_200832.log) used status=1.

    2. Subsequent 0x026F (temple/dungeon from tavern GOTOLIST):
       status=0 + store_flag=0 (3B). Client enters field/dungeon mode.
       Handler sets context+0xA0=0, client does NOT send 0x019A.
       Evidence: dd_server_20260407_171316.log succeeded with status=0.
       This is the ONLY way to handle temple since 2nd zone transition (0x02EF)
       is permanently broken (45 tests confirm, last dd_server_20260408_061517.log).
    """
    store_count = getattr(session, '_store_list_count', 1)
    if store_count <= 1:
        # First entry: REJECT → triggers 0x019A → GOTOLIST → tavern
        session._last_store_mode = 'tavern'
        await session.send_msg(MSG_STORE_IN_REQUEST, struct.pack('>H', 1))
        log.info("[S%d] STORE_IN: status=1 (reject, tavern mode, entry #%d)",
                 session.sid, store_count)
    else:
        # Subsequent entry (temple/dungeon): ACCEPT → field mode
        # AI-RECONSTRUCTED: store_flag=0 enters field mode without store UI.
        # Evidence: handler at 0x4BFE stores flag at context+0xA0. Flag=0 should
        # be "no store" = field mode. Client should begin accepting movement cmds.
        session._last_store_mode = 'field'
        # Update zone to the target adventure zone
        target_zone = getattr(session, '_target_field_zone', None)
        if target_zone and session.char:
            session.char.zone_id = target_zone
            session.char.map_id = target_zone
            session.db.save_character(session.char)
            log.info("[S%d] STORE_IN: zone updated to %d (target field zone)",
                     session.sid, target_zone)
        await session.send_msg(MSG_STORE_IN_REQUEST, struct.pack('>HB', 0, 0))
        log.info("[S%d] STORE_IN: status=0 store_flag=0 (field mode, entry #%d)",
                 session.sid, store_count)


# ── Themes ──

async def h_sel_theme(session, msg_type, payload, param1):
    """0x0268 -> SEL_THEME_REQUEST (0x0269): 2 bytes."""
    await session.send_msg(MSG_SEL_THEME_REQUEST, struct.pack('>H', 0))


async def h_check_theme(session, msg_type, payload, param1):
    """0x026A -> CHECK_THEME_REQUEST (0x026B): 2 bytes."""
    await session.send_msg(MSG_CHECK_THEME_REQUEST, struct.pack('>H', 0))


# ── User List ──

async def h_userlist(session, msg_type, payload, param1):
    """
    0x01A0 -> USERLIST_REQUEST (0x01A1): empty.
    Return list of online users in zone.
    """
    from .world import world
    char = session.char
    # USERLIST_REQUEST handler is empty (no reads) — just send empty
    await session.send_msg(MSG_USERLIST_REQUEST, b'')


# ── Mirror Dungeon ──

async def h_mirror_dungeon(session, msg_type, payload, param1):
    """0x0233 -> MIRRORDUNGEON_REQUEST (0x0234): reject."""
    await session.send_msg(MSG_MIRRORDUNGEON_REQ, struct.pack('>H', 1))


# ── Generic ack / remaining paired entries ──

async def h_setpos_notice(session, msg_type, payload, param1):
    """0x01D6 -> 0x02D8. SETPOS_NOTICE data frame."""
    await session.send_msg(0x02D8, struct.pack('>H', 0))


async def h_ack_generic(session, msg_type, payload, param1):
    """Generic handler for remaining paired entries — send minimal reply."""
    reply_type = PAIRED_TABLE.get(msg_type)
    if reply_type:
        await session.send_msg(reply_type, build_minimal_reply(reply_type, session))
    else:
        log.debug("[S%d] No paired reply for 0x%04X", session.sid, msg_type)


# ── Misc messages ──

async def h_set_sign(session, msg_type, payload, param1):
    """0x0245 -> SET_SIGN_REQUEST (0x0246): 4 bytes."""
    await session.send_msg(MSG_SET_SIGN_REQUEST, struct.pack('>HH', 0, 0))


async def h_move_seat(session, msg_type, payload, param1):
    """0x0254 -> MOVE_SEAT_REQUEST (0x0255): 4 bytes."""
    await session.send_msg(MSG_MOVE_SEAT_REQUEST, struct.pack('>HH', 0, 0))


async def h_set_sekiban(session, msg_type, payload, param1):
    """0x0250 -> SET_SEKIBAN_REQUEST (0x0251): 4 bytes."""
    await session.send_msg(MSG_SET_SEKIBAN_REQUEST, struct.pack('>HH', 0, 0))


async def h_regist_handle(session, msg_type, payload, param1):
    """0x04E0 -> REGIST_HANDLE_REQUEST (0x0046): 2 bytes."""
    await session.send_msg(MSG_REGIST_HANDLE_REQ, struct.pack('>H', 0))


async def h_partyid(session, msg_type, payload, param1):
    """0x01EC -> PARTYID_REQUEST (0x01ED): 8 bytes."""
    char = session.char
    char_id = char.char_id if char else 1
    await session.send_msg(MSG_PARTYID_REQUEST,
                           struct.pack('>HHI', 0, 0, char_id))


async def h_clr_knownmap(session, msg_type, payload, param1):
    """0x01EE -> CLR_KNOWNMAP_REQUEST (0x01EF): 4 bytes."""
    await session.send_msg(MSG_CLR_KNOWNMAP_REQ, struct.pack('>HH', 0, 0))


async def h_system_notice(session, msg_type, payload, param1):
    """0x006D -> ESP_REQUEST (0x006F): reject."""
    await session.send_msg(MSG_ESP_REQUEST, struct.pack('>H', 1))


# ============================================================
# Fallback minimal reply builder (verbatim from v3)
# ============================================================

def build_minimal_reply(reply_type: int, session=None) -> bytes:
    """
    Build a minimal valid response for any reply message type.
    Most handlers check status at offset 0 (U16 BE) and skip on nonzero.
    This is the safety net — any msg_type without a real handler falls through here.
    """
    char_id = session.char.char_id if session and session.char else 1

    special = {
        MSG_GOTOLIST_REQUEST:    struct.pack('>HHI', 0, 0, 0),
        MSG_PARTYLIST_REQUEST:   struct.pack('>HHII', 0, 0, 0, 0),
        MSG_SHOP_LIST_REQUEST:   struct.pack('>HHI', 0, 0, 0),
        MSG_SHOP_ITEM_REQUEST:   struct.pack('>HHI', 0, 0, 0),
        MSG_STORE_LIST_REQUEST:  struct.pack('>HHI', 0, 0, 0),
        MSG_SAKAYA_LIST_REQUEST: struct.pack('>HHI', 0, 0, 0),
        MSG_SAKAYA_TBLLIST_REQ:  struct.pack('>HHHHI', 0, 0, 0, 0, 0),
        MSG_AREA_LIST_REQUEST:   struct.pack('>HHI', 0, 0, 0),
        MSG_TELEPORTLIST_REQ:    struct.pack('>HHHHI', 0, 0, 0, 0, 0),
        MSG_DIR_REQUEST:         struct.pack('>HHI', 0, 0, 0),
        MSG_SUBDIR_REQUEST:      struct.pack('>HHI', 0, 0, 0),
        MSG_MEMODIR_REQUEST:     struct.pack('>HHHI', 0, 0, 0, 0),
        MSG_MAIL_LIST_REQUEST:   struct.pack('>HHIBBI', 0, 0, 0, 0, 0, 0),
        MSG_COLO_LIST_REQUEST:   struct.pack('>HHI', 0, 0, 0),
        MSG_COLO_RANKING_REQ:    struct.pack('>HBBI', 0, 0, 0, 0),
        MSG_SKILL_LIST_REQUEST:  struct.pack('>HHI', 0, 0, 0),
        MSG_SHOP_BUY_REQUEST:    struct.pack('>HHI', 0, 0, 0),
        MSG_SHOP_SELL_REQUEST:   struct.pack('>HHI', 0, 0, 0),
        MSG_PARTYID_REQUEST:     struct.pack('>HHI', 0, 0, char_id),
        MSG_SPEAK_REQUEST:       struct.pack('>HH', 0, 0),
        MSG_CLR_KNOWNMAP_REQ:    struct.pack('>HH', 0, 0),
        MSG_CONFIRM_LVLUP_REQ:   struct.pack('>HI', 0, 0),
        MSG_CAST_DICE_REQUEST:   struct.pack('>HI', 0, 0),
        MSG_SET_SIGN_REQUEST:    struct.pack('>HH', 0, 0),
        MSG_MOVE_SEAT_REQUEST:   struct.pack('>HH', 0, 0),
        MSG_SET_SEKIBAN_REQUEST: struct.pack('>HH', 0, 0),
        MSG_ALLOW_UNITE_REQUEST: struct.pack('>HH', 0, 0),
        MSG_PARTYEXIT_REQUEST:   struct.pack('>H', 1),
        MSG_ESP_REQUEST:         struct.pack('>H', 1),
        MSG_EXEC_EVENT_REQUEST:  struct.pack('>H', 1),
        MSG_FINDUSER_REQUEST:    struct.pack('>H', 1),
        MSG_SHOP_IN_REQUEST:     struct.pack('>H', 1),
        MSG_STORE_IN_REQUEST:    struct.pack('>H', 1),
        MSG_SAKAYA_IN_REQUEST:   struct.pack('>HH', 0, 0),
        MSG_SAKAYA_EXIT_REQUEST: struct.pack('>HHI', 0, 0, 0),
        MSG_SAKAYA_SIT_REQUEST:  struct.pack('>H', 1),  # status=1 reject (old success: 2B)
        MSG_SAKAYA_MEMLIST_REQ:  struct.pack('>H', 1),  # error=1, never count=0 (hangs)
        MSG_SAKAYA_FIND_REQUEST: struct.pack('>H', 1),
        MSG_SAKAYA_STAND_REQ:    struct.pack('>HH', 0, 0),
        MSG_BTL_CMD_REQUEST:     struct.pack('>H', 1),
        MSG_GIVEUP_REQUEST:      b'\x00' * 16,
        MSG_PARTYENTRY_REQUEST:  struct.pack('>HH', 1, 0),
        MSG_PARTYUNITE_REQUEST:  struct.pack('>HH', 1, 0),
        MSG_LEVELUP_REQUEST:     struct.pack('>HI', 1, 0),
        MSG_COLO_ENTRY_REQUEST:  struct.pack('>HBB', 1, 0, 0),
        MSG_CAMP_IN_REQUEST:     struct.pack('>H', 0),
        MSG_CAMP_OUT_REQUEST:    struct.pack('>H', 0),
        MSG_EQUIP_REQUEST:       struct.pack('>H', 0),
        MSG_DISARM_REQUEST:      struct.pack('>H', 0),
        MSG_SET_MOVEMODE_REQ:    struct.pack('>H', 0),
        MSG_SETPOS_REQUEST:      struct.pack('>H', 0),
        MSG_EXPLAIN_REQUEST:     struct.pack('>HH', 0, 0),
        MSG_ENCOUNTMONSTER_REQ:  struct.pack('>H', 0),
        MSG_BTL_CHGMODE_REQ:     struct.pack('>H', 0),
        MSG_BTL_EFFECTEND_REQ:   struct.pack('>H', 0),
        MSG_BTL_END_REQUEST:     struct.pack('>H', 0),
        MSG_CANCEL_ENCOUNT_REQ:  struct.pack('>H', 0),
        MSG_SHOP_OUT_REQUEST:    struct.pack('>H', 0),
        MSG_NEWS_WRITE_REQUEST:  struct.pack('>H', 0),
        MSG_NEWS_DEL_REQUEST:    struct.pack('>H', 0),
        MSG_BB_MKDIR_REQUEST:    struct.pack('>H', 0),
        MSG_BB_RMDIR_REQUEST:    struct.pack('>H', 0),
        MSG_BB_MKSUBDIR_REQUEST: struct.pack('>H', 0),
        MSG_BB_RMSUBDIR_REQUEST: struct.pack('>H', 0),
        MSG_ALLOW_JOIN_REQUEST:  struct.pack('>H', 0),
        MSG_CANCEL_JOIN_REQUEST: struct.pack('>H', 0),
        MSG_CLASS_LIST_REQUEST:  struct.pack('>H', 0),
        MSG_CHANGE_PARA_REQUEST: struct.pack('>H', 0),
        MSG_SEL_THEME_REQUEST:   struct.pack('>H', 0),
        MSG_CHECK_THEME_REQUEST: struct.pack('>H', 0),
        MSG_DEL_MAIL_REQUEST:    struct.pack('>H', 0),
        MSG_COLO_WAITING_REQ:    struct.pack('>H', 0),
        MSG_COLO_EXIT_REQUEST:   struct.pack('>H', 0),
        MSG_COLO_CANCEL_REQUEST: struct.pack('>H', 0),
        MSG_COLO_FLDENT_REQUEST: struct.pack('>H', 0),
        MSG_CARD_REQUEST:        struct.pack('>H', 0),
        MSG_ACTION_CHAT_REQUEST: struct.pack('>H', 0),
        MSG_REGIST_HANDLE_REQ:   struct.pack('>H', 0),
        MSG_TRADE_CANCEL_REQ:    struct.pack('>H', 0),
        MSG_FINDUSER2_REQUEST:   struct.pack('>H', 1),
        MSG_MIRRORDUNGEON_REQ:   struct.pack('>H', 1),
        MSG_NEWS_READ_REQUEST:   struct.pack('>H', 1),
        MSG_CLASS_CHANGE_REQ:    struct.pack('>H', 1),
        MSG_GIVE_ITEM_REQUEST:   struct.pack('>H', 1),
        MSG_USE_REQUEST:         struct.pack('>H', 1),
        MSG_SELL_REQUEST:        struct.pack('>H', 1),
        MSG_BUY_REQUEST:         struct.pack('>H', 1),
        MSG_COMPOUND_REQUEST:    struct.pack('>H', 1),
        MSG_LEARN_SKILL_REQUEST: struct.pack('>H', 1),
        MSG_SKILLUP_REQUEST:     struct.pack('>H', 1),
        MSG_EQUIP_SKILL_REQUEST: struct.pack('>H', 1),
        MSG_DISARM_SKILL_REQ:    struct.pack('>H', 1),
        MSG_USE_SKILL_REQUEST:   struct.pack('>H', 1),
        MSG_GET_MAIL_REQUEST:    struct.pack('>H', 1),
        MSG_SEND_MAIL_REQUEST:   struct.pack('>H', 1),
        MSG_USERLIST_REQUEST:    b'',
        MSG_CURREGION_NOTICE:    b'',
    }

    resp = special.get(reply_type)
    if resp is not None:
        return resp
    return struct.pack('>H', 0)
