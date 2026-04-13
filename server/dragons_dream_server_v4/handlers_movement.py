"""
Movement handlers: 0x01C1/C2 (MOVE), 0x01AC (MAP_CHANGE), 0x01DF (CAMP_IN),
0x01D3 (SETPOS), 0x01B3 (CAMP_OUT), move mode.
"""
import struct
import logging
from .config import *
from .protocol import sjis_pad

log = logging.getLogger("DD-Server")


async def h_move(session, msg_type, payload, param1):
    """
    0x01C1/0x01C2 - Movement from client.
    Parse direction, validate against zone walkability, update position,
    broadcast to other players, check for random encounters.
    """
    from .world import world
    from .game_data import ZONES

    char = session.char
    if not char:
        await session.send_msg(MSG_MOVE1_REQUEST, struct.pack('>H', 1))
        return

    # Parse direction from payload
    direction = payload[0] if payload else 0
    log.debug("[S%d] MOVE dir=%d (pos=%d,%d zone=%d)",
              session.sid, direction, char.pos_x, char.pos_y, char.zone_id)

    # Calculate new position based on direction (1=N, 2=E, 3=S, 4=W)
    new_x, new_y = char.pos_x, char.pos_y
    if direction == 1:    # North
        new_y = max(0, new_y - 1)
    elif direction == 2:  # East
        new_x = min(47, new_x + 1)
    elif direction == 3:  # South
        new_y = min(47, new_y + 1)
    elif direction == 4:  # West
        new_x = max(0, new_x - 1)

    # Validate walkability
    zone = ZONES.get(char.zone_id)
    if zone and zone.walkability:
        row_bytes = (zone.width + 7) // 8
        byte_idx = new_y * row_bytes + (new_x // 8)
        bit_idx = 7 - (new_x % 8)
        if byte_idx < len(zone.walkability):
            if not (zone.walkability[byte_idx] & (1 << bit_idx)):
                # Blocked tile — reject move
                resp = bytearray(16)
                struct.pack_into('>H', resp, 0, 1)  # status=1 (reject)
                await session.send_msg(MSG_MOVE1_REQUEST, bytes(resp))
                return

    # Update position
    char.pos_x = new_x
    char.pos_y = new_y
    char.facing = direction if 1 <= direction <= 4 else char.facing

    # Build success response: MOVE1_REQUEST (0x01C4): 16 bytes
    resp = bytearray(16)
    struct.pack_into('>H', resp, 0, 0)   # status = 0 (success)
    resp[6] = new_x & 0xFF
    resp[7] = new_y & 0xFF
    resp[8] = direction & 0xFF
    await session.send_msg(MSG_MOVE1_REQUEST, bytes(resp))

    # Broadcast MOVE2_NOTICE (0x02F3) to other players in same zone
    others = world.get_players_in_zone(char.zone_id, exclude_char_id=char.char_id)
    if others:
        # 4-byte header (count) + 8 bytes per player
        move_data = bytearray(4 + 8)
        struct.pack_into('>I', move_data, 0, 1)  # count = 1
        move_data[4] = new_y & 0xFF
        move_data[5] = new_x & 0xFF
        struct.pack_into('>H', move_data, 8, ((new_x & 0xFF) << 8) | (new_y & 0xFF))
        move_data[10] = direction & 0xFF
        move_data[11] = 1  # anim_state = walking
        for other in others:
            try:
                await other.send_msg(MSG_MOVE2_NOTICE, bytes(move_data))
            except Exception as e:
                log.warning("[S%d] broadcast move failed to char %d: %s",
                            session.sid, other.char.char_id, e)

    # Check for random encounter
    # AI-RECONSTRUCTED: Server-initiated encounters are inferred. Evidence: ENCOUNTMONSTER_REQUEST (0x0244) handler at 0x7A2A reads only U16 status to g_state+4 — no encounter probability logic in client. ENCOUNTMONSTER_REPLY (0x01C9) at 0x7A6C receives full entity data from server. Client MOVE (0x01C1) at 0x013A9A sends only direction bytes — server must decide encounters.
    if world.should_encounter(char.zone_id) and not session.combat:
        from .handlers_combat import start_encounter
        await start_encounter(session)

    # Periodic save (every 10 moves to reduce DB writes)
    session._move_count = getattr(session, '_move_count', 0) + 1
    if session._move_count % 10 == 0:
        session.db.save_character(char)


async def h_map_change_notice(session, msg_type, payload, param1):
    """0x01AC -> CAMP_IN_REQUEST (0x01AD). Map transition."""
    await session.send_msg(MSG_CAMP_IN_REQUEST, struct.pack('>H', 0))


async def h_camp_in(session, msg_type, payload, param1):
    """0x01DF -> SET_MOVEMODE_REQUEST (0x01E0). Enter camp / new area."""
    move_mode = 1  # default walk
    if session.char:
        move_mode = session.char.move_mode
    await session.send_msg(MSG_SET_MOVEMODE_REQ, struct.pack('>H', move_mode))


async def h_camp_out(session, msg_type, payload, param1):
    """0x01B3 -> CAMP_OUT_REQUEST (0x01B4). Leave camp."""
    await session.send_msg(MSG_CAMP_OUT_REQUEST, struct.pack('>H', 0))


async def h_setpos(session, msg_type, payload, param1):
    """0x01D3 -> SETPOS_REQUEST (0x01D4). Set position."""
    if session.char and len(payload) >= 4:
        # Parse position data from client
        pass
    await session.send_msg(MSG_SETPOS_REQUEST, struct.pack('>H', 0))


async def h_giveup(session, msg_type, payload, param1):
    """0x02F7 -> GIVEUP_REQUEST (0x02F8). Give up / return to town."""
    char = session.char
    resp = bytearray(16)
    if char:
        struct.pack_into('>I', resp, 0, char.zone_id)
        struct.pack_into('>H', resp, 4, char.pos_x)
        struct.pack_into('>H', resp, 6, char.pos_y)
    await session.send_msg(MSG_GIVEUP_REQUEST, bytes(resp))


async def h_set_movemode(session, msg_type, payload, param1):
    """0x01DF -> SET_MOVEMODE_REQUEST (0x01E0). Change movement mode."""
    mode = 1
    if payload and len(payload) >= 1:
        mode = payload[0]
    if session.char:
        session.char.move_mode = max(1, min(3, mode))
    await session.send_msg(MSG_SET_MOVEMODE_REQ, struct.pack('>H', mode & 0xFFFF))
