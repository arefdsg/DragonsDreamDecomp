"""
Social handlers: chat, mail, bulletin board, sakaya (tavern), find user.
"""
import struct
import asyncio
import logging
from .config import *
from .protocol import sjis_pad

log = logging.getLogger("DD-Server")


def _build_zone_member_entry(char_id, name, char_class, char_level,
                              char_race=0, char_gender=0, seat_byte=0,
                              stats=None):
    """Build a 128-byte zone member entry for 0x01B6 handler at 0x06015FE6.

    BINARY EVIDENCE (2026-04-20, decompiled table_entry_writer_61FE at 0x060161FE):
      Per-entry read sequence (NON-SELF path):
        [0:4]    U32 BE  char_id         (read_data_9FD2)
        [4:20]   16B     name            (memcpy_16)
        [20:28]  8B      status_data     (parse_status: [22]=class 0-5, [27]=level 1-16)
        [28:32]  U32 BE  field_1C        (read_data_9FD2, unused)
        [32:36]  U32 BE  field_20        (read_data_9FD2, unused)
        [36:44]  8B      char_info       (read_func_A106: [36]=gender, [38]=race, [39]=class)
        [44:52]  8B      seat_data       (read_5_skip_3: 5 data + 3 pad → entry+0x8C)
        [52:90]  38B     equip_a         (read_func_9EE8: 19 × U16 BE → entry+0x66)
        [90:128] 38B     equip_b         (read_func_9EE8: 19 × U16 BE → entry+0x40)

      CRITICAL: seat_data[0] (entry+0x8C byte 0) must be non-zero for init_seat_grid
      to count this character as "seated". Without this, ctx[0x1B85]=0 and state 259
      loops forever → permanent client freeze.

      NOTE: SELF entries (matching ctx[0x0260]) use a different read path in
      table_entry_writer_61FE. Only send NON-SELF entries (bot characters) to avoid
      payload format mismatch.
    """
    entry = bytearray(128)
    # [0:4] char_id
    struct.pack_into('>I', entry, 0, char_id)
    # [4:20] name (16B null-padded)
    name_bytes = name[:16] if isinstance(name, bytes) else name.encode('ascii')[:16]
    entry[4:4 + len(name_bytes)] = name_bytes
    # [20:28] status_data (parse_status format: byte[2]=class, byte[7]=level)
    entry[22] = char_class & 0xFF
    entry[27] = max(1, min(16, char_level)) & 0xFF
    # [28:36] field_1C, field_20 (zeros)
    # [36:44] char_info (read_func_A106 format)
    entry[36] = char_gender & 0xFF   # → entry+0x15
    entry[38] = char_race & 0xFF     # → bit_decode → entry+0x18 (race bitmask)
    entry[39] = char_class & 0xFF    # → bit_decode → entry+0x16 (class bitmask)
    entry[40] = char_level & 0xFF    # → entry+0x19
    # [44:52] seat_data (5 bytes + 3 pad)
    entry[44] = seat_byte & 0xFF     # non-zero = seated
    # [52:90] equip_a (19 × U16 BE)
    if stats:
        for i in range(min(19, len(stats))):
            struct.pack_into('>H', entry, 52 + i * 2, stats[i] & 0xFFFF)
    # [90:128] equip_b (19 × U16 BE)
    if stats:
        for i in range(min(19, len(stats))):
            struct.pack_into('>H', entry, 90 + i * 2, stats[i] & 0xFFFF)
    return bytes(entry)


async def _send_zone_members(session, entries):
    """Send ZONE_MEMBERS (0x01B6) with the given 128-byte entries.

    SCMD format: [2B status=0][2B count][4B zone_data=0][N × 128B entries]
    Handler at 0x06015FE6 populates ctx+0x1BE0 (max 4 entries, stride 0xA4).
    """
    count = min(len(entries), 4)  # table has 4 entry slots
    header = struct.pack('>HHI', 0, count, 0)  # status=0, count, zone_data=0
    payload = header + b''.join(entries[:count])
    await session.send_msg(MSG_ZONE_MEMBERS, payload)
    log.info("[S%d] ZONE_MEMBERS: sent 0x01B6 with %d entries (%dB)",
             session.sid, count, len(payload))


def _build_member_entry(bot):
    """Build a 36-byte member entry for the 0x024D processor at 0x060151D2.

    Wire format (from verified SH-2 disassembly, 2026-04-10):
      [0:16]   name (16B Shift-JIS null-padded, memcpy to slot[8:24])
      [16]     U8 -> slot[0] (member status: 1=occupied)
      [17]     U8 -> 0x0601A18E bit_decode -> slot[26] (class bitmask: 1<<class_id)
      [18]     U8 -> slot[25] (reserved, 0)
      [19]     U8 -> 0x0601A1BC bit_decode -> slot[28] (race bitmask: 1<<race_id)
      [20:24]  U32 BE -> slot[168] (char_id, via 0x06019FD2)
      [24:32]  8B sub-struct -> 0x0601A1EA ([+2]=class 0-5, [+7]=level 1-16)
      [32:36]  4B skipped padding
    """
    entry = bytearray(36)
    name_bytes = bot.char_name[:16]
    entry[0:len(name_bytes)] = name_bytes
    entry[16] = 1                                     # occupied
    entry[17] = (1 << bot.char_class) & 0xFF          # class bitmask
    entry[18] = 0                                     # reserved
    entry[19] = (1 << bot.char_race) & 0xFF if bot.char_race < 8 else 0x01
    struct.pack_into('>I', entry, 20, bot.char_id)    # char_id
    entry[26] = bot.char_class                        # sub-struct[+2] = class
    entry[31] = bot.char_level                        # sub-struct[+7] = level
    # [32:36] padding = 0
    return bytes(entry)


# ── Chat ──

async def h_standard_reply(session, msg_type, payload, param1):
    """
    0x0048 -> SPEAK_REQUEST (0x0049).
    Chat message from client. Broadcast to zone.
    """
    from .world import world

    char = session.char
    # Send acknowledge to sender
    await session.send_msg(0x0049, struct.pack('>H', 1))  # status=1 skips speak processing

    # If we have actual chat data, broadcast
    if char and payload:
        # Build SPEAK_NOTICE (0x0076) for other players in zone
        # Format: LF-delimited fields (name + message)
        try:
            msg_text = payload.rstrip(b'\x00')
            if msg_text:
                notice = char.char_name[:16] + b'\x0a' + msg_text + b'\x00'
                await world.broadcast_to_zone(char.zone_id, 0x0076, notice,
                                              exclude_char_id=char.char_id)
        except Exception as e:
            log.warning("[S%d] Chat broadcast failed: %s", session.sid, e)


async def h_action_chat(session, msg_type, payload, param1):
    """0x0268 -> SEL_THEME_REQUEST (0x0269). Action chat / emote."""
    await session.send_msg(MSG_SEL_THEME_REQUEST, struct.pack('>H', 0))


# ── Mail ──

async def h_mail_list(session, msg_type, payload, param1):
    """
    0x02A9 -> MAIL_LIST_REQUEST (0x02AA): 12 + N*19 bytes.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_MAIL_LIST_REQUEST,
                               struct.pack('>HHIBBI', 0, 0, 0, 0, 0, 0))
        return

    mails = session.db.get_mail_list(char.char_id)

    resp = bytearray(12 + len(mails) * 19)
    struct.pack_into('>H', resp, 0, 0)                  # error_code
    struct.pack_into('>H', resp, 2, len(mails))         # mail_count
    resp[4] = 1                                          # page_indicator
    resp[5] = 0                                          # has_more = 0

    for i, mail in enumerate(mails):
        off = 12 + i * 19
        resp[off] = 1 if mail['is_read'] else 0          # status_byte_0
        resp[off + 1] = 0                                 # status_byte_1
        name = bytes(mail['from_name'])[:16]
        resp[off + 2:off + 2 + len(name)] = name

    await session.send_msg(MSG_MAIL_LIST_REQUEST, bytes(resp))


async def h_get_mail(session, msg_type, payload, param1):
    """
    0x02AB -> GET_MAIL_REQUEST (0x02AC): 94 + body_len bytes.
    """
    char = session.char
    if not char:
        await session.send_msg(MSG_GET_MAIL_REQUEST, struct.pack('>H', 1))
        return

    mail_idx = struct.unpack_from('>I', payload, 0)[0] if len(payload) >= 4 else 0

    mails = session.db.get_mail_list(char.char_id)
    if mail_idx >= len(mails):
        await session.send_msg(MSG_GET_MAIL_REQUEST, struct.pack('>H', 1))
        return

    mail_id = mails[mail_idx]['id']
    mail = session.db.get_mail(mail_id)
    if not mail:
        await session.send_msg(MSG_GET_MAIL_REQUEST, struct.pack('>H', 1))
        return

    body = bytes(mail['body'])
    resp = bytearray(94 + len(body))
    struct.pack_into('>H', resp, 0, 0)                   # error_code
    resp[4:20] = bytes(mail['from_name'])[:16]           # sender_name
    resp[26:66] = bytes(mail['subject'])[:40]            # subject
    struct.pack_into('>I', resp, 86, 94)                 # body_offset
    struct.pack_into('>I', resp, 90, len(body))          # body_length
    resp[94:94 + len(body)] = body

    await session.send_msg(MSG_GET_MAIL_REQUEST, bytes(resp))


async def h_send_mail(session, msg_type, payload, param1):
    """
    0x02AD -> SEND_MAIL_REQUEST (0x02AE): 2 bytes.
    Send mail to another player.
    """
    char = session.char
    if not char or len(payload) < 70:
        await session.send_msg(MSG_SEND_MAIL_REQUEST, struct.pack('>H', 1))
        return

    to_name = payload[2:18]
    subject = payload[18:58]
    body_len = struct.unpack_from('>I', payload, 66)[0] if len(payload) >= 70 else 0
    body = payload[70:70 + body_len] if len(payload) >= 70 + body_len else b''

    # Find recipient
    to_char = session.db.load_character_by_name(to_name)
    if not to_char:
        log.info("[S%d] Send mail: recipient not found", session.sid)
        await session.send_msg(MSG_SEND_MAIL_REQUEST, struct.pack('>H', 1))
        return

    session.db.send_mail(char.char_id, to_char.char_id, char.char_name, subject, body)
    log.info("[S%d] Mail sent to char_id=%d", session.sid, to_char.char_id)
    await session.send_msg(MSG_SEND_MAIL_REQUEST, struct.pack('>H', 0))


async def h_del_mail(session, msg_type, payload, param1):
    """0x02AF -> DEL_MAIL_REQUEST (0x02B0): 2 bytes."""
    char = session.char
    mail_idx = struct.unpack_from('>I', payload, 0)[0] if len(payload) >= 4 else 0

    if char:
        mails = session.db.get_mail_list(char.char_id)
        if mail_idx < len(mails):
            session.db.delete_mail(mails[mail_idx]['id'], char.char_id)

    await session.send_msg(MSG_DEL_MAIL_REQUEST, struct.pack('>H', 0))


# ── Bulletin Board ──

async def h_dir_request(session, msg_type, payload, param1):
    """
    0x029D -> DIR_REQUEST (0x029E): 8 + N*44 bytes.
    List bulletin board directories.
    """
    dirs = session.db.get_bulletin_dirs()

    resp = bytearray(8 + len(dirs) * 44)
    struct.pack_into('>H', resp, 0, 0)       # status
    resp[2] = len(dirs) & 0xFF               # result_byte (count)

    for i, d in enumerate(dirs):
        off = 8 + i * 44
        resp[off] = 0x21                     # type = 0x21 (validated by client)
        name = d['dir_name'].encode('ascii', errors='replace')[:42]
        resp[off + 1:off + 1 + len(name)] = name

    await session.send_msg(MSG_DIR_REQUEST, bytes(resp))


async def h_subdir_request(session, msg_type, payload, param1):
    """0x029F -> SUBDIR_REQUEST (0x02A0). Subdirectories."""
    # Parse dir name from payload
    dir_name = payload[1:43].rstrip(b'\x00').decode('ascii', errors='replace') if len(payload) >= 4 else ''
    subdirs = session.db.get_bulletin_subdirs(dir_name)

    resp = bytearray(8 + len(subdirs) * 44)
    struct.pack_into('>H', resp, 0, 0)
    resp[2] = len(subdirs) & 0xFF

    for i, sd in enumerate(subdirs):
        off = 8 + i * 44
        resp[off] = 0x21
        name = sd['subdir_name'].encode('ascii', errors='replace')[:42]
        resp[off + 1:off + 1 + len(name)] = name

    await session.send_msg(MSG_SUBDIR_REQUEST, bytes(resp))


async def h_memodir_request(session, msg_type, payload, param1):
    """
    0x02A1 -> MEMODIR_REQUEST (0x02A2): 12 + N*66 bytes.
    List posts in a bulletin board.
    """
    dir_name = 'general'
    subdir_name = ''
    if len(payload) >= 8:
        # Parse dir/subdir from payload
        pass

    posts = session.db.get_bulletin_posts(dir_name, subdir_name)

    resp = bytearray(12 + len(posts) * 66)
    struct.pack_into('>H', resp, 0, 0)                   # status
    struct.pack_into('>H', resp, 2, 0)                   # area_id
    struct.pack_into('>H', resp, 4, len(posts))          # entry_count

    for i, post in enumerate(posts):
        off = 12 + i * 66
        struct.pack_into('>H', resp, off, post['id'] & 0xFFFF)
        # author name at +2
        author = session.db.load_character(post['author_id'])
        if author:
            resp[off + 2:off + 18] = author.char_name[:16]
        # subject at +26
        subj = bytes(post['subject'])[:40]
        resp[off + 26:off + 26 + len(subj)] = subj

    await session.send_msg(MSG_MEMODIR_REQUEST, bytes(resp))


async def h_news_read(session, msg_type, payload, param1):
    """0x02A3 -> NEWS_READ_REQUEST (0x02A4): article content."""
    # Parse article ID
    article_idx = struct.unpack_from('>H', payload, 0)[0] if len(payload) >= 2 else 0

    posts = session.db.get_bulletin_posts('general', '')
    if article_idx >= len(posts):
        await session.send_msg(MSG_NEWS_READ_REQUEST, struct.pack('>H', 1))
        return

    post = posts[article_idx]
    body = bytes(post['body'])
    author = session.db.load_character(post['author_id'])
    author_name = author.char_name[:16] if author else b'\x00' * 16
    subject = bytes(post['subject'])[:40]

    resp = bytearray(64 + len(body) + 1)
    struct.pack_into('>H', resp, 0, 0)                   # error_code
    struct.pack_into('>H', resp, 2, post['id'] & 0xFFFF)
    resp[8:24] = author_name
    resp[24:64] = subject + b'\x00' * (40 - len(subject))
    resp[64:64 + len(body)] = body
    resp[64 + len(body)] = 0  # null terminator

    await session.send_msg(MSG_NEWS_READ_REQUEST, bytes(resp))


async def h_news_write(session, msg_type, payload, param1):
    """0x02A5 -> NEWS_WRITE_REQUEST (0x02A6): 2 bytes."""
    char = session.char
    if not char or len(payload) < 45:
        await session.send_msg(MSG_NEWS_WRITE_REQUEST, struct.pack('>H', 1))
        return

    subject = payload[4:44]
    body = payload[44:].rstrip(b'\x00')
    session.db.create_bulletin_post(char.char_id, 'general', '', subject, body)
    await session.send_msg(MSG_NEWS_WRITE_REQUEST, struct.pack('>H', 0))


async def h_news_del(session, msg_type, payload, param1):
    """0x02A7 -> NEWS_DEL_REQUEST (0x02A8): 2 bytes."""
    await session.send_msg(MSG_NEWS_DEL_REQUEST, struct.pack('>H', 0))


async def h_bb_mkdir(session, msg_type, payload, param1):
    """0x02B1 -> BB_MKDIR_REQUEST (0x02B2): 2 bytes."""
    await session.send_msg(MSG_BB_MKDIR_REQUEST, struct.pack('>H', 0))


async def h_bb_rmdir(session, msg_type, payload, param1):
    """0x02B3 -> BB_RMDIR_REQUEST (0x02B4): 2 bytes."""
    await session.send_msg(MSG_BB_RMDIR_REQUEST, struct.pack('>H', 0))


async def h_bb_mksubdir(session, msg_type, payload, param1):
    """0x02B5 -> BB_MKSUBDIR_REQUEST (0x02B6): 2 bytes."""
    await session.send_msg(MSG_BB_MKSUBDIR_REQUEST, struct.pack('>H', 0))


async def h_bb_rmsubdir(session, msg_type, payload, param1):
    """0x02B7 -> BB_RMSUBDIR_REQUEST (0x02B8): 2 bytes."""
    await session.send_msg(MSG_BB_RMSUBDIR_REQUEST, struct.pack('>H', 0))


# ── Sakaya (Tavern) ──
#
# FREEZE-BISECT EXPERIMENT (2026-04-22)
#
# After patching state 259 (ctx[0x1B85] poll) via patches/sit_patch.py, the
# client still freezes identically after the sit atomic. That rules out state
# 259 as the actual freeze point. Remaining suspects are one of the three
# data-push handlers we send alongside 0x020F:
#
#   0x0247 — memmove(ctx+0x74EC, payload+16, 40)              bounded
#   0x024D — clear 8 slots + process_member_entries(count=1)  count-driven
#   0x01B6 — process_zone_entries(count=N)                    count-driven
#
# Set SIT_INCLUDE in order to bisect which message triggers the hang. Leave
# the list at ("0x020F",) as the first test — if sending ONLY the paired
# reply and still freezing, the freeze is in the state machine / input path,
# not in a data-push handler.
#
# Test order (each setting, one test, save the log):
#   1. ("020F",)                                — ack only
#   2. ("020F", "0247")                         — + self-data
#   3. ("020F", "0247", "024D")                 — + member push
#   4. ("020F", "0247", "024D", "01B6")         — full baseline (the hang)
#
# First config that hangs identifies the culprit handler.
SIT_INCLUDE = ("020F", "0247", "024D")  # 0x01B6 removed — disproved premise (see docs)

# GHIDRA INVESTIGATION (2026-04-22, exhaustive scan of 124,874 instructions):
#
#   1. ctx[0x1B85] has 6 READS and ZERO WRITES anywhere in the binary — confirmed
#      by (a) scan of every MOV.W @(disp,PC),Rn followed by MOV.B store,
#      (b) literal-0x202CCB85 absolute-address search, (c) GBR+8 + offset + ADD
#      pattern scan. The "state 259 polls ctx[0x1B85]" branch at 0x06034E4E is
#      structurally dead code — the advance path cannot be triggered by any
#      server message.
#
#   2. 0x0274 is NOT in the client dispatch table at 0x060535D8. Prior theory
#      that it was a "universal paired ack" was wrong — the client silently drops
#      it. The ~2.5min recovery + "table full" message seen with _DIAG_SEND_0274
#      was just the client's paired-wait for 0x020E timing out.
#
#   3. init_seat_grid at 0x06035ED8 writes to global 0x06068B6C (resolved via
#      PTR_DAT_06036008), NOT ctx+0x1B85. So feeding ctx+0x1BE0 via 0x01B6 does
#      not populate the state-259 gate.
#
#   4. All tavern state transitions are driven LOCALLY by UI code
#      (tavern_full_setup, build_seated_display, enable_transition, etc.) that
#      writes tavern_ctx[0..1] at 0x06068576. No server message writes there.
#
#   Implication: if the client enters state 259 (0x103) on sit, it always
#   freezes. The real game must avoid state 259 via local UI-driven state
#   transitions (tavern_ctx[0..1] set to 0x104 before the 258 → transition
#   enqueues the next state). The server's only job is to (a) ack the 0x020E
#   paired-wait with 0x020F so the client's RX loop unblocks, and (b) push
#   table name (0x0247) and member list (0x024D) data in the same frame so the
#   UI has populated data when it renders.
#
# Baseline behavior: atomic send of 0x020F(status=0) + 0x0247 + 0x024D + 0x01B6
# in that order. 0x020F must come first so its strcpy runs before 0x0247's
# memmove overwrites ctx+0x74EC with the server table name (otherwise strcpy
# from an empty ctx+0x7515 would blank the name).

async def h_sakaya_list(session, msg_type, payload, param1):
    """0x020C -> SAKAYA_LIST_REQUEST (0x020D): 8 + N*20 bytes.

    BINARY EVIDENCE (2026-04-10, handler at file 0x04C3A):
      Handler clears 12 slots (22B each at ctx+0x6C94, total 264B).
      Sets slot[0] = "出口" (exit) with slot[0].byte_19 = 11.
      Header: [0:2] U16 status, [2:4] U16 entry_count, [4:8] U32 unknown
      Per entry (20 bytes):
        [0:16]  char name (16B Shift-JIS)
        [16]    seat_index (0-11, determines slot position)
        [17]    field_b (→ slot+18, role/class)
        [18]    field_c (→ slot+19 as value-1, level)
        [19]    padding (skipped)
      Slot 0 is always "exit" (built-in). Player entries use slots 1-11.
    """
    from .world import TAVERN_TABLES

    log.info("[S%d] SAKAYA_LIST (0x020C): %d bytes", session.sid, len(payload))

    # Build character seat list with bot players at their tables
    entries = []
    for i, (table_id, table_name, bot) in enumerate(TAVERN_TABLES):
        if bot:
            entry = bytearray(20)
            entry[0:len(bot.char_name)] = bot.char_name[:16]  # char name
            entry[16] = (i + 1) & 0xFF      # seat_index (1-based, slot 0 = exit)
            entry[17] = bot.char_class       # field_b (class)
            entry[18] = bot.char_level + 1   # field_c (level+1, handler does -1)
            entry[19] = 0                    # padding
            entries.append(bytes(entry))

    entry_count = len(entries)
    header = struct.pack('>HHI', 0, entry_count, 0)  # status=0, count, unknown=0
    resp = header + b''.join(entries)
    await session.send_msg(MSG_SAKAYA_LIST_REQUEST, resp)
    log.info("[S%d] SAKAYA_LIST: sent 0x020D with %d character entries (%d bytes)",
             session.sid, entry_count, len(resp))


async def h_sakaya_tbllist(session, msg_type, payload, param1):
    """0x01F8/0x02FA -> SAKAYA_TBLLIST_REQUEST (0x01F9): 12 + N×64 bytes.

    Handler at file 0x4EC6:
      HEADER (12 bytes):
        [0:2]  U16 BE  status → session_ctx+4 (0=success)
        [2:4]  U16 BE  unknown_1
        [4:6]  U16 BE  entry_count (max 10)
        [6:12] read but discarded

      PER ENTRY (64 bytes):
        [0:4]   U32 BE  table_id → slot[0:4]
        [4:6]   U16 BE  flags (low byte → slot[45], occupied=1)
        [6:24]  18 bytes SKIPPED
        [24:64] 40 bytes table_data → slot[4:44] (display name/info)

    Storage: session_ctx+0x6DA8, 48B stride, 10 slots max.
    """
    from .world import TAVERN_TABLES

    arg2 = 0
    if len(payload) >= 20:
        arg2 = struct.unpack_from('>H', payload, 18)[0]
    log.info("[S%d] SAKAYA_TBLLIST (0x%04X): %d bytes, arg2=%d",
             session.sid, msg_type, len(payload), arg2)

    entry_count = min(len(TAVERN_TABLES), 10)

    # HEADER (12 bytes)
    header = bytearray(12)
    struct.pack_into('>H', header, 0, 0)            # status = 0 (success)
    struct.pack_into('>H', header, 2, 0)            # unknown_1
    struct.pack_into('>H', header, 4, entry_count)  # entry_count at [4:6]

    resp = bytearray(header)
    table_names = []
    for table_id, table_name, bot in TAVERN_TABLES:
        entry = bytearray(64)
        struct.pack_into('>I', entry, 0, table_id)
        # flags byte (→ slot[45]). Investigation 2026-04-22: all tables flagged
        # occupied=1 may make auto-assign sit (target=0) think no seat is
        # available, causing the client's sit UI to block waiting for a free
        # table — match the permanent post-sit silence we observed. Mark all
        # tables as EMPTY so the auto-assign path has a seat to take.
        flags = 0
        struct.pack_into('>H', entry, 4, flags)
        # Display data at [24:64] → slot[4:44]
        table_data = sjis_pad(table_name, 40)
        entry[24:64] = table_data[:40]
        resp.extend(entry)
        table_names.append(f"{table_name}(f={flags})")

    await session.send_msg(MSG_SAKAYA_TBLLIST_REQ, bytes(resp))
    log.info("[S%d] SAKAYA_TBLLIST: sent %d tables: %s",
             session.sid, entry_count, table_names)
    # Note: prior versions also sent 0x01B6 ZONE_MEMBERS here on the premise
    # that init_seat_grid would populate ctx[0x1B85] from ctx+0x1BE0. Full-
    # binary decompile (2026-04-22) confirmed init_seat_grid writes the
    # global 0x06068B6C, NOT ctx[0x1B85]. That premise was wrong, so the
    # extra push has been removed to keep the tavern-entry protocol minimal.


async def h_sakaya_in(session, msg_type, payload, param1):
    """0x0216 -> SAKAYA_IN_REQUEST (0x0217): 4 bytes.
    Accept tavern entry. Also sends 0x01B6 (ZONE_MEMBERS) to populate ctx+0x1BE0
    with bot characters and their seat occupancy — required for sit flow.

    BINARY EVIDENCE (2026-04-20): Handler 0x01B6 at 0x06015FE6 populates ctx+0x1BE0.
    init_seat_grid reads this table for seat count → ctx[0x1B85]. Without 0x01B6,
    ctx[0x1B85]=0 and tavern sit state 259 loops forever.
    """
    from .world import TAVERN_TABLES

    log.info("[S%d] SAKAYA_IN (0x0216): %d bytes", session.sid, len(payload))
    await session.send_msg(MSG_SAKAYA_IN_REQUEST, struct.pack('>HH', 0, 0))
    # Prior versions pushed 0x01B6 ZONE_MEMBERS here to pre-populate ctx+0x1BE0
    # in the hope of unblocking state-259's ctx[0x1B85] poll. Full decompile
    # (2026-04-22) disproved the chain — init_seat_grid writes 0x06068B6C
    # not ctx[0x1B85]. Extra push removed.


async def h_sakaya_exit(session, msg_type, payload, param1):
    """0x01FA -> SAKAYA_EXIT_REQUEST (0x01FB): 8 bytes.
    Handler reads error_code(U16), if 0: unknown(U16) + exit_context(U32).
    """
    log.info("[S%d] SAKAYA_EXIT (0x01FA): leaving tavern", session.sid)
    await session.send_msg(MSG_SAKAYA_EXIT_REQUEST, struct.pack('>HHI', 0, 0, 0))


async def h_sakaya_sit(session, msg_type, payload, param1):
    """0x020E -> 0x020F (paired ack) + 0x0247 (table name push) + 0x024D (member list push).

    BINARY EVIDENCE (CORRECTED 2026-04-10, dispatch table at file 0x435D8,
    format [msg_type:2][pad:2][handler:4]):

      0x020F handler at file 0x050D0 (entry 43):
        Reads [2B status][2B unused] from payload → ctx+4.
        If status==0: strcpy(ctx+0x74EC, ctx+0x7515) — commits pending name.
        Always clears ctx+0x7515 = 0.
        NOT a no-op — it reads status and conditionally copies the name buffer.

      0x0247 handler at file 0x0533C (entry 50):
        memmove(ctx+0x74EC, payload+16, 40) — UNCONDITIONAL, no status check.
        Clears ctx+0x7514 = 0.
        Payload: 16B header (skipped) + 40B data → ctx+0x74EC.

      0x024D handler at file 0x05152 (entry 45) — FULL MEMBER REFRESH:
        Reads status→LOCAL (NOT ctx+4). Reads count→ctx+0x6F88.
        Clears ALL 8 member slots (172B each at ctx+0x6F8C).
        Calls process_member_entries at 0x060151D2. ALWAYS processes.
        Entry format: 36B per entry.
        NOT paired — server push only.

      0x024F handler at file 0x05290 (entry 46) — FIND RESULT ONLY:
        Reads [2B status][2B count_discarded][4B find_result→ctx+0x9C].
        Does NOT process member entries. Does NOT clear slots.
        Paired reply for 0x024E (find request).

      CORRECTED FLOW (2026-04-13, complete binary analysis):
        Client sends 0x020E (table_id=0, cmd=8) — table_id=0 = auto-assign.
        Server replies with 3 messages atomically (send_msgs_atomic):
        1. 0x020F (4B): status=0 → exits paired wait, strcpy blanks ctx+0x74EC
        2. 0x0247 (56B): 16B header + 40B table name → restores ctx+0x74EC
        3. 0x024D (44B): 8B header + 36B entry → populates member list

        All 3 dispatched in one SV_Poll (before UI frame) via SV_RecvFrame loop.
        After all 3 handlers: ctx+0x74EC=table name, ctx+0x6F88=1, member[0]=bot.
        UI sees populated data on next frame → advances to seated view.

        Adjacent GBR entry 0x024B sender is for REQUESTING delta updates
        AFTER already seated, NOT for initial sit sequence.
    """
    from .world import TAVERN_TABLES

    target = 0
    cmd = 0
    if len(payload) >= 4:
        target = struct.unpack_from('>I', payload, 0)[0]
    if len(payload) >= 6:
        cmd = struct.unpack_from('>H', payload, 4)[0]
    log.info("[S%d] SAKAYA_SIT (0x020E): target=%d, cmd=%d, %d bytes",
             session.sid, target, cmd, len(payload))

    selected_table = None
    for table_id, table_name, bot in TAVERN_TABLES:
        if bot:
            selected_table = (table_id, table_name, bot)
            break

    if not selected_table:
        await session.send_msg(MSG_SAKAYA_SIT_REQUEST, struct.pack('>HH', 1, 0))
        log.info("[S%d] SAKAYA_SIT: REJECTED (no bot tables)", session.sid)
        return

    table_id, table_name, bot = selected_table
    session._seated_table = table_id
    session._seated_bot = bot

    # --- 0x020F: paired reply (4B). status=0 → client strcpy commits pending name. ---
    sit_payload = struct.pack('>HH', 0, 0)

    # --- 0x0247: table name push (56B). Handler memmove(ctx+0x74EC, payload+16, 40). ---
    tname_header = b'\x00' * 16
    tname_data = sjis_pad(table_name, 40)
    self_data_payload = tname_header + tname_data

    # --- 0x024D: full member refresh (8B header + 36B entry). ---
    member_entry = _build_member_entry(bot)
    member_payload = struct.pack('>HHI', 0, 1, 0) + member_entry

    # --- 0x01B6: ZONE_MEMBERS (populates ctx+0x1BE0 / init_seat_grid input). ---
    # Per Ghidra findings this does NOT unblock state 259, but it does populate
    # the seat grid that build_seated_display renders, so include it.
    zone_member_msgs = []
    zone_entries = []
    for tid, tname, tbot in TAVERN_TABLES:
        if tbot:
            zone_entries.append(_build_zone_member_entry(
                char_id=tbot.char_id,
                name=tbot.char_name,
                char_class=tbot.char_class,
                char_level=tbot.char_level,
                char_race=tbot.char_race,
                char_gender=tbot.char_gender,
                seat_byte=tid,
                stats=tbot.current_stats,
            ))
    if zone_entries:
        zm_count = min(len(zone_entries), 4)
        zm_header = struct.pack('>HHI', 0, zm_count, 0)
        zm_payload = zm_header + b''.join(zone_entries[:zm_count])
        zone_member_msgs = [(MSG_ZONE_MEMBERS, zm_payload)]

    all_msgs = {
        "020F": (MSG_SAKAYA_SIT_REQUEST, sit_payload),
        "0247": (MSG_SAKAYA_SELF_DATA, self_data_payload),
        "024D": (MSG_SAKAYA_MEMLIST_PUSH, member_payload),
        "01B6": zone_member_msgs[0] if zone_member_msgs else None,
    }
    seq = [all_msgs[k] for k in SIT_INCLUDE if all_msgs.get(k)]
    await session.send_msgs_atomic(seq)
    tags = "+".join("0x" + k for k in SIT_INCLUDE if all_msgs.get(k))
    log.info("[S%d] SAKAYA_SIT: sent ATOMIC %s "
             "(table=%d '%s', bot=%s class=%d lv=%d id=%d). "
             "Trace subsequent incoming SCMDs to see what client sends next.",
             session.sid, tags, table_id, table_name,
             bot.char_name.rstrip(b'\x00').decode('ascii', errors='replace'),
             bot.char_class, bot.char_level, bot.char_id)

    # SIT_DIAG: enable post-sit diagnostic logging on this session.
    # Used in conjunction with patches/sit_diag_gate_patch.py — the client-side
    # gate at FUN_06030CEC is bypassed, so the state machine progresses past
    # the table-list lock. From here, the client will send messages that reveal
    # which character fields/state the production game depended on.
    # Look for "SIT_DIAG_RX" in the server log to see every post-sit incoming
    # SCMD with full payload hexdump.
    session._diag_post_sit = True
    log.info("[S%d] SIT_DIAG: post-sit logging ENABLED "
             "(grep 'SIT_DIAG_RX' to see all subsequent client messages)",
             session.sid)


async def h_sakaya_memlist(session, msg_type, payload, param1):
    """0x024B -> 0x024C (paired reply: delta member update).

    BINARY EVIDENCE (CORRECTED 2026-04-10, dispatch table at file 0x435D8):
      0x024C handler at file 0x05112 (entry 44) — DELTA UPDATE:
        Reads status→ctx+4. If status!=0, returns (error).
        Reads count→ctx+0x6F88. Reads context(U32)→local.
        Calls process_member_entries. Does NOT clear existing slots.
        Format: [2B status][2B count][4B context][N×36B entries]

      0x024D handler at file 0x05152 (entry 45) — FULL REFRESH:
        Reads status→LOCAL. Reads count→ctx+0x6F88.
        Clears ALL 8 slots. Calls process_member_entries. Always processes.

      0x024F handler at file 0x05290 (entry 46) — FIND RESULT:
        Simple 8B handler. Reads status, find_result→ctx+0x9C. NO member processing.

    Use 0x024C (paired reply for 0x024B) for member list updates.
    """
    log.info("[S%d] SAKAYA_MEMLIST (0x024B): %d bytes", session.sid, len(payload))

    bot = getattr(session, '_seated_bot', None)

    if bot:
        entry = _build_member_entry(bot)
        header = struct.pack('>HHI', 0, 1, 0)  # status=0, count=1, context=0
        await session.send_msg(MSG_SAKAYA_MEMLIST_REQ, header + entry)
        log.info("[S%d] SAKAYA_MEMLIST: sent 0x024C delta update (1 entry, %s lv%d)",
                 session.sid,
                 bot.char_name.rstrip(b'\x00').decode('ascii', errors='replace'),
                 bot.char_level)
    else:
        # Not seated — send 0x024C with status=1 (error, handler returns early)
        await session.send_msg(MSG_SAKAYA_MEMLIST_REQ, struct.pack('>H', 1))
        log.info("[S%d] SAKAYA_MEMLIST: rejected (not seated)", session.sid)


async def h_sakaya_find(session, msg_type, payload, param1):
    """0x024E -> 0x024F (paired reply: find result).

    BINARY EVIDENCE (CORRECTED 2026-04-10, dispatch table at file 0x435D8):
      0x024F handler at file 0x05290 (entry 46) — FIND RESULT:
        Reads [2B status→ctx+4]. If status!=0, returns.
        If status==0: reads [2B count(discarded)][4B find_result→ctx+0x9C].
        Total: 8 bytes max. Does NOT process member entries.
        This is NOT a member list handler — it stores a find result.

    For member list population, send 0x024D (server push) separately.
    """
    log.info("[S%d] SAKAYA_FIND (0x024E): %d bytes", session.sid, len(payload))

    bot = getattr(session, '_seated_bot', None)
    if bot:
        # Send 0x024F find result (paired reply): status=0, count=0, find_result=bot.char_id
        await session.send_msg(MSG_SAKAYA_FIND_RESULT,
                               struct.pack('>HHI', 0, 0, bot.char_id))
        log.info("[S%d] SAKAYA_FIND: sent 0x024F find result (char_id=%d)", session.sid, bot.char_id)
        # Also send 0x024D full member refresh (server push) to populate the member list
        entry = _build_member_entry(bot)
        header = struct.pack('>HHI', 0, 1, 0)
        await session.send_msg(MSG_SAKAYA_MEMLIST_PUSH, header + entry)
        log.info("[S%d] SAKAYA_FIND: sent 0x024D member refresh (1 entry)", session.sid)
    else:
        # Not seated — send 0x024F with status=1 (error, find failed)
        await session.send_msg(MSG_SAKAYA_FIND_RESULT, struct.pack('>H', 1))
        log.info("[S%d] SAKAYA_FIND: sent 0x024F not found", session.sid)


async def h_sakaya_stand(session, msg_type, payload, param1):
    """0x0219 -> SAKAYA_STAND_REQUEST (0x021A): 4 bytes.
    Accept standing up from table.
    """
    log.info("[S%d] SAKAYA_STAND (0x0219): standing up from table", session.sid)
    session._seated_table = None
    session._seated_bot = None
    await session.send_msg(MSG_SAKAYA_STAND_REQ, struct.pack('>HH', 0, 0))


# ── Find User ──

async def h_finduser(session, msg_type, payload, param1):
    """
    0x01B7 -> FINDUSER_REQUEST (0x01B8).
    Search for a player by name.
    """
    from .world import world

    if len(payload) < 16:
        await session.send_msg(MSG_FINDUSER_REQUEST, struct.pack('>H', 1))
        return

    search_name = payload[:16]
    target = world.get_session_by_name(search_name)

    if target and target.char:
        resp = bytearray(6)
        struct.pack_into('>H', resp, 0, 0)              # found
        struct.pack_into('>I', resp, 2, target.char.char_id)
        await session.send_msg(MSG_FINDUSER_REQUEST, bytes(resp))
    else:
        await session.send_msg(MSG_FINDUSER_REQUEST, struct.pack('>H', 1))


async def h_finduser2(session, msg_type, payload, param1):
    """0x0240 -> FINDUSER2_REQUEST (0x0241). Extended find."""
    await session.send_msg(MSG_FINDUSER2_REQUEST, struct.pack('>H', 1))
