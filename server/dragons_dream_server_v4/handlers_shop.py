"""
Shop handlers: SHOP_IN, SHOP_LIST, SHOP_BUY, SHOP_SELL, SHOP_OUT, SHOP_ITEM.
AI-RECONSTRUCTED: Shop flow from client handler decompilation. Evidence: SHOP_BUY_REQUEST (0x01F3) handler at 0x57F6 reads [0:2]=U16 status, [2:4]=U16 buy_param, [4:8]=U32 gold_update stored at party_entry+0x1C. SHOP_SELL_REQUEST (0x01F5) at 0x5856 same layout. SHOP_IN_REQUEST (0x01FF) at 0x5588 reads header + N*22B items to g_state+0x7948 (max 32). Gold validation is server-authoritative — client just stores the gold_update value received.
"""
import struct
import logging
from .config import *
from .game_data import SHOPS, ITEMS, ZONES, get_item_data_blob

log = logging.getLogger("DD-Server")


def _get_shop_for_session(session):
    """Find the first shop available in the player's current zone."""
    char = session.char
    if not char:
        return None
    zone = ZONES.get(char.zone_id)
    if not zone or not zone.shop_ids:
        return None
    # Use first shop in zone, or session-stored shop if set
    shop_id = getattr(session, '_current_shop_id', zone.shop_ids[0])
    return SHOPS.get(shop_id)


async def h_shop_in(session, msg_type, payload, param1):
    """
    0x01FE -> SHOP_IN_REQUEST (0x01FF).
    Client enters a shop. Send shop inventory.
    Server payload: H(status), H(item_count), I(shop_param), then N * 22B items.
    """
    shop = _get_shop_for_session(session)
    if not shop:
        await session.send_msg(MSG_SHOP_IN_REQUEST, struct.pack('>H', 1))  # reject
        return

    items_data = []
    for item_id in shop.item_ids:
        item_def = ITEMS.get(item_id)
        if item_def:
            items_data.append((item_id, item_def))

    resp = bytearray(8 + len(items_data) * 22)
    struct.pack_into('>H', resp, 0, 0)                     # status = 0 (success)
    struct.pack_into('>H', resp, 2, len(items_data))       # item_count
    struct.pack_into('>I', resp, 4, shop.shop_id)          # shop_param

    for i, (item_id, item_def) in enumerate(items_data):
        off = 8 + i * 22
        resp[off:off + 16] = get_item_data_blob(item_id)
        struct.pack_into('>H', resp, off + 16, item_def.price & 0xFFFF)
        struct.pack_into('>H', resp, off + 18, item_def.type_a)
        struct.pack_into('>H', resp, off + 20, item_def.type_b)

    session._current_shop_id = shop.shop_id
    await session.send_msg(MSG_SHOP_IN_REQUEST, bytes(resp))
    log.info("[S%d] Shop enter: %s (%d items)", session.sid, shop.name, len(items_data))


async def h_shop_list(session, msg_type, payload, param1):
    """
    0x0202 -> SHOP_LIST_REQUEST (0x0203).
    Client requests shop item listing. Similar to SHOP_IN but different wire layout.
    """
    shop = _get_shop_for_session(session)
    if not shop:
        await session.send_msg(MSG_SHOP_LIST_REQUEST, struct.pack('>HHI', 0, 0, 0))
        return

    items_data = []
    for item_id in shop.item_ids:
        item_def = ITEMS.get(item_id)
        if item_def:
            items_data.append((item_id, item_def))

    resp = bytearray(8 + len(items_data) * 20)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, len(items_data))
    struct.pack_into('>I', resp, 4, shop.shop_id)

    for i, (item_id, item_def) in enumerate(items_data):
        off = 8 + i * 20
        resp[off:off + 16] = get_item_data_blob(item_id)
        struct.pack_into('>H', resp, off + 16, item_def.price & 0xFFFF)
        struct.pack_into('>H', resp, off + 18, item_def.type_a)

    await session.send_msg(MSG_SHOP_LIST_REQUEST, bytes(resp))


async def h_shop_item(session, msg_type, payload, param1):
    """
    0x01FC -> SHOP_ITEM_REQUEST (0x01FD).
    Client requests specific shop item details.
    """
    shop = _get_shop_for_session(session)
    if not shop:
        await session.send_msg(MSG_SHOP_ITEM_REQUEST, struct.pack('>HHI', 0, 0, 0))
        return

    # Parse which item they're looking at
    item_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    items_data = []
    for item_id in shop.item_ids:
        item_def = ITEMS.get(item_id)
        if item_def:
            items_data.append((item_id, item_def))

    # Return the specific item (or all if index is out of range)
    resp = bytearray(8 + len(items_data) * 22)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, len(items_data))
    struct.pack_into('>I', resp, 4, shop.shop_id)

    for i, (item_id, item_def) in enumerate(items_data):
        off = 8 + i * 22
        resp[off:off + 16] = get_item_data_blob(item_id)
        struct.pack_into('>H', resp, off + 16, item_def.price & 0xFFFF)
        struct.pack_into('>H', resp, off + 18, item_def.type_a)
        struct.pack_into('>H', resp, off + 20, item_def.type_b)

    await session.send_msg(MSG_SHOP_ITEM_REQUEST, bytes(resp))


async def h_shop_buy(session, msg_type, payload, param1):
    """
    0x01F2 -> SHOP_BUY_REQUEST (0x01F3): 8 bytes.
    Client buys an item. Validate gold, add to inventory.
    Client payload: W(arg1), W(arg2) = item index + quantity
    Server: H(status), H(buy_param), I(gold_update)
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_SHOP_BUY_REQUEST, struct.pack('>HHI', 1, 0, 0))
        return

    item_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    shop = _get_shop_for_session(session)
    if not shop or item_idx >= len(shop.item_ids):
        await session.send_msg(MSG_SHOP_BUY_REQUEST, struct.pack('>HHI', 1, 0, 0))
        return

    item_id = shop.item_ids[item_idx]
    item_def = ITEMS.get(item_id)
    if not item_def:
        await session.send_msg(MSG_SHOP_BUY_REQUEST, struct.pack('>HHI', 1, 0, 0))
        return

    # Check gold
    if char.gold < item_def.price:
        log.info("[S%d] Shop buy: insufficient gold (%d < %d)",
                 session.sid, char.gold, item_def.price)
        await session.send_msg(MSG_SHOP_BUY_REQUEST, struct.pack('>HHI', 1, 0, char.gold))
        return

    # Add item to inventory
    slot = session.db.add_item(
        char.char_id, item_id, get_item_data_blob(item_id),
        item_def.type_a, item_def.type_b, item_def.equip_slot, item_def.price
    )
    if slot < 0:
        log.info("[S%d] Shop buy: inventory full", session.sid)
        await session.send_msg(MSG_SHOP_BUY_REQUEST, struct.pack('>HHI', 1, 0, char.gold))
        return

    # Deduct gold
    char.gold -= item_def.price
    session.db.save_character(char)

    log.info("[S%d] Shop buy: item_id=%d, price=%d, gold_remaining=%d",
             session.sid, item_id, item_def.price, char.gold)
    await session.send_msg(MSG_SHOP_BUY_REQUEST,
                           struct.pack('>HHI', 0, item_idx, char.gold))


async def h_shop_sell(session, msg_type, payload, param1):
    """
    0x01F4 -> SHOP_SELL_REQUEST (0x01F5): 8 bytes.
    Client sells an item. Remove from inventory, add gold.
    Server: H(status), H(sell_param), I(gold_update)
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_SHOP_SELL_REQUEST, struct.pack('>HHI', 1, 0, 0))
        return

    slot_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    # Find item in inventory
    items = session.db.get_inventory(char.char_id)
    target_item = None
    for item in items:
        if item.slot_index == slot_idx:
            target_item = item
            break

    if not target_item:
        await session.send_msg(MSG_SHOP_SELL_REQUEST, struct.pack('>HHI', 1, 0, char.gold))
        return

    # AI-RECONSTRUCTED: Sell price formula is fabricated. Evidence: SHOP_SELL_REQUEST (0x01F5) handler at 0x5856 reads [4:8]=U32 gold_update and stores it directly at party_entry+0x1C (gold). Server sends the final gold value — client does not compute sell price locally.
    sell_price = target_item.item_price // 2

    # Remove from inventory and add gold
    session.db.remove_item(char.char_id, slot_idx)
    char.gold += sell_price
    session.db.save_character(char)

    log.info("[S%d] Shop sell: slot=%d, item_id=%d, sell_price=%d, gold=%d",
             session.sid, slot_idx, target_item.item_id, sell_price, char.gold)
    await session.send_msg(MSG_SHOP_SELL_REQUEST,
                           struct.pack('>HHI', 0, slot_idx, char.gold))


async def h_shop_out(session, msg_type, payload, param1):
    """0x0200 -> SHOP_OUT_REQUEST (0x0201). Leave shop."""
    session._current_shop_id = None
    await session.send_msg(MSG_SHOP_OUT_REQUEST, struct.pack('>H', 0))
