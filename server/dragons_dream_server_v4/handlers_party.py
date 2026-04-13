"""
Party handlers: party list, entry, unite, exit, join, cancel.
AI-RECONSTRUCTED: Party system for up to 6 members.
"""
import struct
import logging
from .config import *
from .protocol import sjis_pad

log = logging.getLogger("DD-Server")


async def h_partylist(session, msg_type, payload, param1):
    """
    0x01A2 -> PARTYLIST_REQUEST (0x01A3): 12 + N*72 bytes.
    Return list of party members.
    """
    from .world import world
    char = session.char

    # Build party list with just the current player (solo)
    members = []
    if char:
        members.append(char)

    resp = bytearray(12 + len(members) * 72)
    struct.pack_into('>H', resp, 0, 0)                  # result_code
    struct.pack_into('>H', resp, 2, 0)                  # unknown
    struct.pack_into('>I', resp, 4, len(members))       # num_members
    struct.pack_into('>I', resp, 8, 0)                  # unknown

    for i, member in enumerate(members):
        off = 12 + i * 72
        struct.pack_into('>H', resp, off, 1)            # member_info
        struct.pack_into('>I', resp, off + 4, member.char_id)
        resp[off + 8:off + 24] = member.char_name[:16]  # name_block_0

    await session.send_msg(MSG_PARTYLIST_REQUEST, bytes(resp))


async def h_partyentry(session, msg_type, payload, param1):
    """
    0x01A4 -> PARTYENTRY_REQUEST (0x022B): 4 bytes.
    Client requests to create/join a party.
    """
    resp = bytearray(4)
    struct.pack_into('>H', resp, 0, 0)  # status = success
    struct.pack_into('>H', resp, 2, 0)  # entry_param
    await session.send_msg(MSG_PARTYENTRY_REQUEST, bytes(resp))


async def h_allow_join(session, msg_type, payload, param1):
    """0x01E6 -> ALLOW_JOIN_REQUEST (0x01E7): 2 bytes."""
    await session.send_msg(MSG_ALLOW_JOIN_REQUEST, struct.pack('>H', 0))


async def h_cancel_join(session, msg_type, payload, param1):
    """0x025B -> CANCEL_JOIN_REQUEST (0x025C): 2 bytes."""
    await session.send_msg(MSG_CANCEL_JOIN_REQUEST, struct.pack('>H', 0))


async def h_partyunite(session, msg_type, payload, param1):
    """0x022C -> PARTYUNITE_REQUEST (0x022F): 4 bytes."""
    resp = bytearray(4)
    struct.pack_into('>H', resp, 0, 0)
    struct.pack_into('>H', resp, 2, 0)
    await session.send_msg(MSG_PARTYUNITE_REQUEST, bytes(resp))


async def h_allow_unite(session, msg_type, payload, param1):
    """0x0230 -> ALLOW_UNITE_REQUEST (0x0231): 4 bytes."""
    await session.send_msg(MSG_ALLOW_UNITE_REQUEST, struct.pack('>HH', 0, 0))


async def h_partyexit(session, msg_type, payload, param1):
    """0x01A7 -> PARTYEXIT_REQUEST (0x01A8): reject (no party to exit)."""
    await session.send_msg(MSG_PARTYEXIT_REQUEST, struct.pack('>H', 1))


async def h_party_breakup(session, msg_type, payload, param1):
    """0x025F -> ACTION_CHAT_REQUEST (0x0260): 2 bytes. Party breakup."""
    await session.send_msg(MSG_ACTION_CHAT_REQUEST, struct.pack('>H', 0))
