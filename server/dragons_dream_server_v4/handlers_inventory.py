"""
Inventory handlers: equip, disarm, give item, use item, compound.
"""
import struct
import logging
from .config import *
from .game_data import ITEMS, get_item_data_blob

log = logging.getLogger("DD-Server")


async def h_equip(session, msg_type, payload, param1):
    """
    0x0204 -> EQUIP_REQUEST (0x0205): 2 bytes.
    Client equips item from inventory.
    Client payload: W(arg_byte), W(0) = slot_index.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_EQUIP_REQUEST, struct.pack('>H', 1))
        return

    slot_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    items = session.db.get_inventory(char.char_id)
    target = None
    for item in items:
        if item.slot_index == slot_idx:
            target = item
            break

    if not target:
        await session.send_msg(MSG_EQUIP_REQUEST, struct.pack('>H', 1))
        return

    item_def = ITEMS.get(target.item_id)
    if not item_def or item_def.equip_slot == 0:
        # Can't equip this item type
        await session.send_msg(MSG_EQUIP_REQUEST, struct.pack('>H', 1))
        return

    # Unequip anything currently in that slot
    for item in items:
        if item.is_equipped and item.equip_slot == item_def.equip_slot and item.slot_index != slot_idx:
            session.db.unequip_item(char.char_id, item.slot_index)

    # Equip the new item
    session.db.equip_item(char.char_id, slot_idx, item_def.equip_slot)

    # Apply stat modifiers
    _recalc_equipment_stats(session)

    log.info("[S%d] Equipped item_id=%d in slot %d", session.sid, target.item_id, item_def.equip_slot)
    await session.send_msg(MSG_EQUIP_REQUEST, struct.pack('>H', 0))


async def h_disarm(session, msg_type, payload, param1):
    """
    0x026C -> DISARM_REQUEST (0x026D): 2 bytes.
    Client unequips an item.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_DISARM_REQUEST, struct.pack('>H', 1))
        return

    slot_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    items = session.db.get_inventory(char.char_id)
    target = None
    for item in items:
        if item.slot_index == slot_idx:
            target = item
            break

    if not target or not target.is_equipped:
        await session.send_msg(MSG_DISARM_REQUEST, struct.pack('>H', 1))
        return

    session.db.unequip_item(char.char_id, slot_idx)
    _recalc_equipment_stats(session)

    log.info("[S%d] Disarmed item_id=%d from slot %d", session.sid, target.item_id, slot_idx)
    await session.send_msg(MSG_DISARM_REQUEST, struct.pack('>H', 0))


async def h_use_item(session, msg_type, payload, param1):
    """
    0x02D0 -> USE_REQUEST (0x02D1): 2 bytes.
    Client uses a consumable item.
    Client payload: W(a1), W(0), D(data, 16) = 20 bytes.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_USE_REQUEST, struct.pack('>H', 1))
        return

    slot_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    items = session.db.get_inventory(char.char_id)
    target = None
    for item in items:
        if item.slot_index == slot_idx:
            target = item
            break

    if not target:
        await session.send_msg(MSG_USE_REQUEST, struct.pack('>H', 1))
        return

    item_def = ITEMS.get(target.item_id)
    if not item_def or item_def.type_a != 5:  # Only consumables
        await session.send_msg(MSG_USE_REQUEST, struct.pack('>H', 1))
        return

    # Apply consumable effect
    # AI-RECONSTRUCTED: Consumable effect mapping is fabricated. Evidence: USE_REQUEST (0x02D1) handler at 0x9090 reads only U16 status. USE_REPLY (0x02EA) at 0x90D8 is complex (92B stack) and copies 16B from payload to g_state+0xDB8C. Server controls all item use effects — client just applies the resulting state update.
    hp_restore = item_def.stat_modifiers[0] if item_def.stat_modifiers else 0
    mp_restore = item_def.stat_modifiers[1] if len(item_def.stat_modifiers) > 1 else 0

    if hp_restore > 0:
        char.current_stats[0] = min(char.base_stats[0], char.current_stats[0] + hp_restore)
    if mp_restore > 0:
        char.current_stats[1] = min(char.base_stats[1], char.current_stats[1] + mp_restore)

    # Remove consumed item
    session.db.remove_item(char.char_id, slot_idx)
    session.db.save_character(char)

    log.info("[S%d] Used item_id=%d: +%dHP +%dMP",
             session.sid, target.item_id, hp_restore, mp_restore)
    await session.send_msg(MSG_USE_REQUEST, struct.pack('>H', 0))


async def h_give_item(session, msg_type, payload, param1):
    """
    0x0293 -> GIVE_ITEM_REQUEST (0x0294): 2 bytes.
    NPC gives item to player (event trigger).
    """
    await session.send_msg(MSG_GIVE_ITEM_REQUEST, struct.pack('>H', 1))  # reject for now


async def h_compound(session, msg_type, payload, param1):
    """
    0x02ED -> COMPOUND_REQUEST (0x02EE): 56 bytes.
    Item compounding/crafting.
    """
    # AI-RECONSTRUCTED: Compound system is stubbed. Evidence: COMPOUND_REQUEST (0x02EE) handler at 0x9430 reads 56B active portion: [0:2]=result_code, [2:4]=item_id, [6:8]=quantity, [8:24]=16B item_name_data, [24:28]=U32 compound_value, [28:40]=type/attr bytes, [40:56]=8xU16 compound_stats. Full compounding logic exists server-side. Inventory at g_state+0x260+0x0C88 (22B/slot, max 100).
    await session.send_msg(MSG_COMPOUND_REQUEST, struct.pack('>H', 1))  # reject


async def h_sell_item(session, msg_type, payload, param1):
    """0x0289 -> SELL_REQUEST (0x028D). P2P sell."""
    await session.send_msg(MSG_SELL_REQUEST, struct.pack('>H', 1))


async def h_buy_item(session, msg_type, payload, param1):
    """0x028E -> BUY_REQUEST (0x028F). P2P buy."""
    await session.send_msg(MSG_BUY_REQUEST, struct.pack('>H', 1))


async def h_trade_cancel(session, msg_type, payload, param1):
    """0x0290 -> TRADE_CANCEL_REQUEST (0x0291). Cancel trade."""
    await session.send_msg(MSG_TRADE_CANCEL_REQ, struct.pack('>H', 0))


def _recalc_equipment_stats(session):
    """
    Recalculate current_stats based on base_stats + equipped item modifiers.
    # AI-RECONSTRUCTED: Equipment stat modifier mapping is fabricated. Evidence: CHARDATA_REQUEST (0x02F9) handler at 0x3648 reads 19xU16 base_stats at offset 72-110 and 19xU16 current_stats at 110-148 (extended data). CHARDATA_NOTICE (0x01AB) at 0x3B90 reads 16xU8 stat_array at offset 40. Equipment effects are embedded in server-sent stat arrays — client stores both base and current separately.
    """
    char = session.char
    if not char:
        return

    # Start with base stats
    char.current_stats = list(char.base_stats)

    # Add equipment bonuses
    items = session.db.get_inventory(char.char_id)
    for item in items:
        if item.is_equipped:
            item_def = ITEMS.get(item.item_id)
            if item_def and item_def.stat_modifiers:
                # stat_modifiers maps to: [ATK(STR), DEF(VIT), INT, MND, AGI, DEX, LUK, CHA]
                stat_mapping = [2, 3, 4, 5, 6, 7, 8, 9]  # indices in current_stats
                for i, mod in enumerate(item_def.stat_modifiers[:8]):
                    if mod > 0 and i < len(stat_mapping):
                        idx = stat_mapping[i]
                        char.current_stats[idx] = min(65535, char.current_stats[idx] + mod)

    session.db.save_character(char)
