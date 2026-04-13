"""
Skill handlers: skill list, learn, upgrade, equip, disarm, use skill.
AI-RECONSTRUCTED: Skill system structure from client binary. Evidence: LOGIN_REQUEST at 0x012C3C sends 8xU16 skill_slots at payload offsets 44-60 from session+0x1780. CHARDATA_REQUEST (0x02F9) handler at 0x3648 reads 8xU16 skill_ids at offset 40 and 8xU16 skill_levels at offset 156. SKILL_LIST_REQUEST (0x02BA) at 0x969C, LEARN_SKILL_REQUEST (0x02E1) at 0x96C4, SKILLUP_REQUEST (0x02E3) at 0x96F8, EQUIP_SKILL_REQUEST (0x02E5) at 0x9718 all read U16 status. Max level/cost values are fabricated.
"""
import struct
import logging
from .config import *
from .game_data import SKILLS

log = logging.getLogger("DD-Server")


async def h_skill_list(session, msg_type, payload, param1):
    """
    0x02B9 -> SKILL_LIST_REQUEST (0x02BA): 8 bytes.
    Returns list of learned skills.
    Server: H(status), H(count), I(0)
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_SKILL_LIST_REQUEST, struct.pack('>HHI', 1, 0, 0))
        return

    skills = session.db.get_skills(char.char_id)
    await session.send_msg(MSG_SKILL_LIST_REQUEST,
                           struct.pack('>HHI', 0, len(skills), 0))


async def h_learn_skill(session, msg_type, payload, param1):
    """
    0x02E0 -> LEARN_SKILL_REQUEST (0x02E1): 2 bytes.
    Client wants to learn a new skill.
    Client payload: W(arg) = skill_id.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 1))
        return

    skill_id = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0
    skill_def = SKILLS.get(skill_id)

    if not skill_def:
        await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Check class requirement
    if char.char_class not in skill_def.class_req:
        log.info("[S%d] Learn skill %d: wrong class (%d not in %s)",
                 session.sid, skill_id, char.char_class, skill_def.class_req)
        await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Check gold
    if char.gold < skill_def.learn_cost:
        log.info("[S%d] Learn skill %d: insufficient gold (%d < %d)",
                 session.sid, skill_id, char.gold, skill_def.learn_cost)
        await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Learn the skill
    if not session.db.learn_skill(char.char_id, skill_id):
        log.info("[S%d] Learn skill %d: already known", session.sid, skill_id)
        await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Deduct gold
    char.gold -= skill_def.learn_cost
    session.db.save_character(char)

    log.info("[S%d] Learned skill %d (cost %d gold)", session.sid, skill_id, skill_def.learn_cost)
    await session.send_msg(MSG_LEARN_SKILL_REQUEST, struct.pack('>H', 0))


async def h_skillup(session, msg_type, payload, param1):
    """
    0x02E2 -> SKILLUP_REQUEST (0x02E3): 2 bytes.
    Upgrade a skill level.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_SKILLUP_REQUEST, struct.pack('>H', 1))
        return

    skill_id = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    # AI-RECONSTRUCTED: Upgrade cost formula is fabricated. Evidence: SKILLUP_REQUEST (0x02E3) handler at 0x96F8 reads only U16 status — no cost logic in client. Server decides success/failure and client just displays the status result.
    skills = session.db.get_skills(char.char_id)
    current_skill = None
    for s in skills:
        if s['skill_id'] == skill_id:
            current_skill = s
            break

    if not current_skill:
        await session.send_msg(MSG_SKILLUP_REQUEST, struct.pack('>H', 1))
        return

    upgrade_cost = current_skill['skill_level'] * 100
    if char.gold < upgrade_cost:
        await session.send_msg(MSG_SKILLUP_REQUEST, struct.pack('>H', 1))
        return

    if current_skill['skill_level'] >= 10:  # AI-RECONSTRUCTED: Max skill level is fabricated. Evidence: CHARDATA_REQUEST at 0x3648 reads 8xU16 skill_levels at offset 156 — U16 allows up to 65535. No level cap enforced in client binary.
        await session.send_msg(MSG_SKILLUP_REQUEST, struct.pack('>H', 1))
        return

    new_level = session.db.upgrade_skill(char.char_id, skill_id)
    char.gold -= upgrade_cost
    session.db.save_character(char)

    log.info("[S%d] Skill %d upgraded to level %d", session.sid, skill_id, new_level)
    await session.send_msg(MSG_SKILLUP_REQUEST, struct.pack('>H', 0))


async def h_equip_skill(session, msg_type, payload, param1):
    """
    0x02E4 -> EQUIP_SKILL_REQUEST (0x02E5): 2 bytes.
    Equip a skill into one of 8 active slots.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_EQUIP_SKILL_REQUEST, struct.pack('>H', 1))
        return

    skill_id = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    # Find first free slot
    skills = session.db.get_skills(char.char_id)
    used_slots = set()
    for s in skills:
        if s['equipped_slot'] is not None:
            used_slots.add(s['equipped_slot'])

    free_slot = None
    for i in range(8):
        if i not in used_slots:
            free_slot = i
            break

    if free_slot is None:
        await session.send_msg(MSG_EQUIP_SKILL_REQUEST, struct.pack('>H', 1))
        return

    session.db.equip_skill(char.char_id, skill_id, free_slot)

    # Update character skill_slots
    char.skill_slots[free_slot] = skill_id
    session.db.save_character(char)

    log.info("[S%d] Equipped skill %d in slot %d", session.sid, skill_id, free_slot)
    await session.send_msg(MSG_EQUIP_SKILL_REQUEST, struct.pack('>H', 0))


async def h_disarm_skill(session, msg_type, payload, param1):
    """
    0x02E6 -> DISARM_SKILL_REQUEST (0x02E7): 2 bytes.
    Unequip a skill from active slots.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_DISARM_SKILL_REQ, struct.pack('>H', 1))
        return

    skill_id = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0
    session.db.unequip_skill(char.char_id, skill_id)

    # Clear from skill_slots
    for i in range(8):
        if char.skill_slots[i] == skill_id:
            char.skill_slots[i] = 0
    session.db.save_character(char)

    log.info("[S%d] Disarmed skill %d", session.sid, skill_id)
    await session.send_msg(MSG_DISARM_SKILL_REQ, struct.pack('>H', 0))


async def h_use_skill(session, msg_type, payload, param1):
    """
    0x02E8 -> USE_SKILL_REQUEST (0x02E9): 2 bytes.
    Use a skill outside of combat (healing, etc).
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_USE_SKILL_REQUEST, struct.pack('>H', 1))
        return

    skill_id = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 4 else 0
    skill_def = SKILLS.get(skill_id)

    if not skill_def:
        await session.send_msg(MSG_USE_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Check MP
    if char.current_stats[1] < skill_def.mp_cost:
        await session.send_msg(MSG_USE_SKILL_REQUEST, struct.pack('>H', 1))
        return

    # Deduct MP
    char.current_stats[1] -= skill_def.mp_cost

    # Apply skill effect outside combat (healing only)
    if skill_def.target_type in (2, 3, 4):  # ally/self heal
        heal = skill_def.base_power + char.char_level * 3
        char.current_stats[0] = min(char.base_stats[0], char.current_stats[0] + heal)
        log.info("[S%d] Used skill %d: healed %d HP", session.sid, skill_id, heal)

    session.db.save_character(char)
    await session.send_msg(MSG_USE_SKILL_REQUEST, struct.pack('>H', 0))
