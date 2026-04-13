"""
Level-up and class change handlers.
AI-RECONSTRUCTED: EXP thresholds and stat growth tables are fabricated. Evidence: LEVELUP_REQUEST (0x0278) handler at 0x95E4 reads [0:2]=U16 result_code, [4:8]=U32 experience_threshold stored at g_state+0xAE98, [8:46]=19xU16 new_base_stats via read_19_u16 to g_state+0x260+0x1932. CONFIRM_LVLUP_REQUEST (0x0276) at 0x95B8 reads [0:2]=status, [2:6]=U32 levelup_data. Server defines all thresholds and stat values.
"""
import struct
import logging
from .config import *

log = logging.getLogger("DD-Server")


async def h_confirm_lvlup(session, msg_type, payload, param1):
    """
    0x0275 -> CONFIRM_LVLUP_REQUEST (0x0276): 6 bytes.
    Check if player has enough EXP to level up.
    Server: H(status), I(levelup_data = exp threshold)
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_CONFIRM_LVLUP_REQ, struct.pack('>HI', 1, 0))
        return

    if char.char_level >= MAX_LEVEL:
        await session.send_msg(MSG_CONFIRM_LVLUP_REQ, struct.pack('>HI', 1, 0))
        return

    next_level = char.char_level + 1
    threshold = EXP_THRESHOLDS[next_level] if next_level < len(EXP_THRESHOLDS) else 0xFFFFFFFF

    if char.experience >= threshold:
        # Can level up
        log.info("[S%d] Level up available: exp=%d >= threshold=%d (level %d->%d)",
                 session.sid, char.experience, threshold, char.char_level, next_level)
        await session.send_msg(MSG_CONFIRM_LVLUP_REQ,
                               struct.pack('>HI', 0, threshold))
    else:
        # Not enough EXP
        await session.send_msg(MSG_CONFIRM_LVLUP_REQ,
                               struct.pack('>HI', 1, threshold))


async def h_levelup(session, msg_type, payload, param1):
    """
    0x0277 -> LEVELUP_REQUEST (0x0278): 48 bytes.
    Execute level up: increment level, recalculate stats.
    Server: H(result_code), H(skip), I(exp_threshold), 19xU16(new_base_stats), H(trailing)
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_LEVELUP_REQUEST, struct.pack('>HI', 1, 0))
        return

    if char.char_level >= MAX_LEVEL:
        await session.send_msg(MSG_LEVELUP_REQUEST, struct.pack('>HI', 1, 0))
        return

    next_level = char.char_level + 1
    threshold = EXP_THRESHOLDS[next_level] if next_level < len(EXP_THRESHOLDS) else 0xFFFFFFFF

    if char.experience < threshold:
        await session.send_msg(MSG_LEVELUP_REQUEST, struct.pack('>HI', 1, threshold))
        return

    # Level up!
    char.char_level = next_level

    # Apply stat growth
    growth = STAT_GROWTH.get(char.char_class, STAT_GROWTH[0])
    for i in range(19):
        char.base_stats[i] += growth[i]
        char.current_stats[i] = char.base_stats[i]

    # Full HP/MP restore on level up
    # AI-RECONSTRUCTED: Full HP/MP restore on level-up is fabricated. Evidence: LEVELUP_REQUEST handler at 0x95E4 receives 19xU16 new_base_stats from server at payload[8:46] and copies them to char base stats. Server controls whether stats are set to max — client just stores what server sends.
    char.current_stats[0] = char.base_stats[0]
    char.current_stats[1] = char.base_stats[1]

    session.db.save_character(char)

    log.info("[S%d] LEVEL UP: %d -> %d (class %d)",
             session.sid, next_level - 1, next_level, char.char_class)

    # Build 48-byte response
    resp = bytearray(48)
    struct.pack_into('>H', resp, 0, 0)                    # result_code = 0 (success)
    # [2:4] skipped
    struct.pack_into('>I', resp, 4, threshold)             # exp_threshold
    for i in range(19):
        struct.pack_into('>H', resp, 8 + i * 2, char.base_stats[i])

    await session.send_msg(MSG_LEVELUP_REQUEST, bytes(resp))


async def h_class_list(session, msg_type, payload, param1):
    """
    0x0298 -> CLASS_LIST_REQUEST (0x0299): 2 bytes.
    List available classes for class change.
    """
    await session.send_msg(MSG_CLASS_LIST_REQUEST, struct.pack('>H', 0))


async def h_class_change(session, msg_type, payload, param1):
    """
    0x029A -> CLASS_CHANGE_REQUEST (0x029B): 68 bytes.
    Change character class. Recalculate all stats from new class base.
    AI-RECONSTRUCTED: Class change behavior is fabricated. Evidence: CLASS_CHANGE_REQUEST (0x029B) handler at 0x68F0 reads [0:2]=result_code, [4:12]=class_change_block via parse_status (new_class 0-5, new_level 1-16), [12:28]=8xU16 skill_slot_data to g_state+0x1780, [28:66]=19xU16 new_base_stats. Server controls all post-change stats.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_CLASS_CHANGE_REQ, struct.pack('>H', 1))
        return

    new_class = payload[0] if len(payload) >= 1 else 0
    if new_class > 5:
        await session.send_msg(MSG_CLASS_CHANGE_REQ, struct.pack('>H', 1))
        return

    # AI-RECONSTRUCTED: Level-1 reset on class change is fabricated. Evidence: CLASS_CHANGE_REQUEST handler at 0x68F0 applies parse_status at [4:12] which sets new_level from byte +7 of status block. Server sends the new level — could be 1 or any other value 1-16.
    old_class = char.char_class
    char.char_class = new_class
    char.char_level = 1
    char.experience = 0

    new_base = list(DEFAULT_BASE_STATS.get(new_class, DEFAULT_BASE_STATS[0]))
    char.base_stats = new_base
    char.current_stats = list(new_base)
    char.skill_slots = [0] * 8
    char.skill_levels = [0] * 8

    session.db.save_character(char)

    log.info("[S%d] Class change: %d -> %d", session.sid, old_class, new_class)

    # Build 68-byte response
    resp = bytearray(68)
    struct.pack_into('>H', resp, 0, 0)  # result_code = 0
    # [4:12] class_change_block
    resp[4] = new_class
    resp[11] = 1  # new level
    # [12:28] skill_slot_data = zeros
    # [28:66] new_base_stats (19 x U16 BE)
    for i in range(19):
        struct.pack_into('>H', resp, 28 + i * 2, char.base_stats[i])

    await session.send_msg(MSG_CLASS_CHANGE_REQ, bytes(resp))
