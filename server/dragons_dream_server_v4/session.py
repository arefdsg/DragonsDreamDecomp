"""
DDSession: BBS handshake, session establishment, keepalive, send/recv, dispatch.
Verbatim transport code from v3, with modular handler dispatch.
"""
import asyncio
import struct
import logging
from typing import Optional
from .protocol import sv_encode, build_game_msg, parse_game_msg, hexdump, full_hexdump, sjis_pad
from .config import PAIRED_TABLE
from .models import Character
from .db import Database

log = logging.getLogger("DD-Server")


class DDSession:
    """Handles a single Dragon's Dream client connection."""

    _next_id = 0

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 db: Database):
        DDSession._next_id += 1
        self.sid = DDSession._next_id
        self.reader = reader
        self.writer = writer
        self.db = db
        self.running = True
        self.keepalive_task = None
        self.login_phase = 0

        # Session protocol state
        self.session_param = self.sid & 0xFFFF
        self.connection_id = self.sid & 0xFFFF
        self.send_seq = 0
        self.client_seq = 0

        # Character state (loaded from DB during login)
        self.char: Optional[Character] = None
        self.char_name = sjis_pad("Player", 16)

        # Combat state
        self.combat = None  # CombatInstance or None

        # Zone transition state — pauses keepalives during SV_Init window
        self._zone_transitioning = False

        # Write lock — prevents asyncio coroutine interleaving on self.writer
        # Evidence: _keepalive_loop and send_msg both call send_iv concurrently.
        # While asyncio is single-threaded, drain() yields to the event loop,
        # allowing a second write to start before the first drain completes.
        self._write_lock = asyncio.Lock()

        # Handler dispatch table — built once per session
        self._handlers = self._build_dispatch_table()

    def _build_dispatch_table(self) -> dict:
        """Build the msg_type -> handler function dispatch table."""
        from . import handlers_login as hl
        from . import handlers_movement as hm
        from . import handlers_combat as hc
        from . import handlers_shop as hs
        from . import handlers_inventory as hi
        from . import handlers_skills as hsk
        from . import handlers_leveling as hlv
        from . import handlers_party as hp
        from . import handlers_social as hso
        from . import handlers_misc as hmi

        return {
            # ── Login flow ──
            0x0035: hl.h_init,
            0x019E: hl.h_login_request,
            0x01AA: hl.h_update_chardata_reply,
            0x0B6C: hl.h_chardata2_notice,
            0x019A: hl.h_logout,
            0x019C: hl.h_gotolist_notice,
            0x02F5: hl.h_change_para,

            # ── Movement ──
            0x01C1: hm.h_move,
            0x01C2: hm.h_move,
            0x01AC: hm.h_map_change_notice,
            0x01DF: hm.h_camp_in,
            0x01B3: hm.h_camp_out,
            0x01D3: hm.h_setpos,
            0x02F7: hm.h_giveup,

            # ── Combat ──
            0x0243: hc.h_monsterwarn,
            0x0221: hc.h_btl_cmd,
            0x0224: hc.h_btl_chgmode,
            0x0296: hc.h_btl_effectend,
            0x01EA: hc.h_btl_end,
            0x01E3: hc.h_cancel_encount,

            # ── Shop ──
            0x01FE: hs.h_shop_in,
            0x0202: hs.h_shop_list,
            0x01FC: hs.h_shop_item,
            0x01F2: hs.h_shop_buy,
            0x01F4: hs.h_shop_sell,
            0x0200: hs.h_shop_out,

            # ── Inventory ──
            0x0204: hi.h_equip,
            0x026C: hi.h_disarm,
            0x02D0: hi.h_use_item,
            0x0293: hi.h_give_item,
            0x02ED: hi.h_compound,
            0x0289: hi.h_sell_item,
            0x028E: hi.h_buy_item,
            0x0290: hi.h_trade_cancel,

            # ── Skills ──
            0x02B9: hsk.h_skill_list,
            0x02E0: hsk.h_learn_skill,
            0x02E2: hsk.h_skillup,
            0x02E4: hsk.h_equip_skill,
            0x02E6: hsk.h_disarm_skill,
            0x02E8: hsk.h_use_skill,

            # ── Leveling ──
            0x0275: hlv.h_confirm_lvlup,
            0x0277: hlv.h_levelup,
            0x0298: hlv.h_class_list,
            0x029A: hlv.h_class_change,

            # ── Party ──
            0x01A2: hp.h_partylist,
            0x01A4: hp.h_partyentry,
            0x01E6: hp.h_allow_join,
            0x025B: hp.h_cancel_join,
            0x022C: hp.h_partyunite,
            0x0230: hp.h_allow_unite,
            0x01A7: hp.h_partyexit,
            0x025F: hp.h_party_breakup,

            # ── Social ──
            0x0048: hso.h_standard_reply,
            0x0268: hso.h_action_chat,
            0x02A9: hso.h_mail_list,
            0x02AB: hso.h_get_mail,
            0x02AD: hso.h_send_mail,
            0x02AF: hso.h_del_mail,
            0x029D: hso.h_dir_request,
            0x029F: hso.h_subdir_request,
            0x02A1: hso.h_memodir_request,
            0x02A3: hso.h_news_read,
            0x02A5: hso.h_news_write,
            0x02A7: hso.h_news_del,
            0x02B1: hso.h_bb_mkdir,
            0x02B3: hso.h_bb_rmdir,
            0x02B5: hso.h_bb_mksubdir,
            0x02B7: hso.h_bb_rmsubdir,
            0x020C: hso.h_sakaya_list,
            0x01F8: hso.h_sakaya_tbllist,
            0x02FA: hso.h_sakaya_tbllist,
            0x0216: hso.h_sakaya_in,
            0x01FA: hso.h_sakaya_exit,
            0x020E: hso.h_sakaya_sit,
            0x024B: hso.h_sakaya_memlist,
            0x024E: hso.h_sakaya_find,
            0x0219: hso.h_sakaya_stand,
            0x01B7: hso.h_finduser,
            0x0240: hso.h_finduser2,

            # ── Misc ──
            0x02BB: hmi.h_colo_waiting,
            0x02BE: hmi.h_colo_exit,
            0x02C1: hmi.h_colo_list,
            0x02C3: hmi.h_colo_entry,
            0x02C5: hmi.h_colo_cancel,
            0x02C8: hmi.h_colo_fldent,
            0x02CD: hmi.h_colo_ranking,
            0x02D4: hmi.h_cast_dice,
            0x02DB: hmi.h_card,
            0x01CF: hmi.h_exec_event,
            0x01AF: hmi.h_teleport_list,
            0x023B: hmi.h_area_list,
            0x023E: hmi.h_explain,
            0x026F: hmi.h_store_list,
            0x0271: hmi.h_store_in,
            0x026A: hmi.h_check_theme,
            0x01A0: hmi.h_userlist,
            0x0233: hmi.h_mirror_dungeon,
            0x0245: hmi.h_set_sign,
            0x0254: hmi.h_move_seat,
            0x0250: hmi.h_set_sekiban,
            0x04E0: hmi.h_regist_handle,
            0x01EC: hmi.h_partyid,
            0x01EE: hmi.h_clr_knownmap,
            0x006D: hmi.h_system_notice,
            0x0210: hmi.h_sel_theme,  # SAKAYA_SPEAK -> map to theme

            # ── Remaining paired entries (minor, ack-only) ──
            0x01D6: hmi.h_setpos_notice,     # SETPOS_NOTICE -> 0x02D8
            0x02D9: hmi.h_ack_generic,       # -> 0x02DA
            0x0235: hmi.h_ack_generic,       # BTLJOIN -> 0x0236
        }

    # ----------------------------------------------------------
    # Transport: IV framing (verbatim from v3)
    # ----------------------------------------------------------
    async def send_iv(self, payload: bytes):
        """Send one IV frame."""
        frame = sv_encode(payload)
        log.info("[S%d] >> WIRE TX (%d bytes): %s",
                 self.sid, len(frame), frame.hex())
        async with self._write_lock:
            self.writer.write(frame)
            await self.writer.drain()

    async def send_msg(self, msg_type: int, payload: bytes = b'', param1: int = 0):
        """Build SCMD, wrap in session DATA frame, send as IV."""
        scmd = build_game_msg(msg_type, payload, param1)
        session_frame = self._build_session_data_frame(scmd)
        await self.send_iv(session_frame)
        log.info("[S%d] >> SEND 0x%04X (%d bytes payload, send_seq=%d)",
                 self.sid, msg_type, len(payload), self.send_seq)
        log.debug("[S%d] >> SCMD:\n%s", self.sid, full_hexdump(scmd, f"SCMD 0x{msg_type:04X}"))

    async def send_msgs_atomic(self, msgs: list):
        """Send multiple SCMDs atomically in one TCP write.

        Binary analysis of scmd_dispatch_inner (0x0601341C) proves that the
        dispatch callback processes exactly ONE SCMD per session DATA frame.
        Concatenating multiple SCMDs into one session frame only dispatches
        the first — the rest are silently dropped.

        However, SV_RecvFrame (0x060226DA) LOOPS reading all available bytes
        from the socket buffer, processing each complete IV frame inline via
        delivery_function (0x060423C8) → queue_dispatch (0x06042A88).

        Therefore: each SCMD gets its own session DATA frame → its own IV
        frame, but ALL IV frames are written in a single TCP write. This
        guarantees they're all in the socket buffer when SV_RecvFrame runs,
        so all SCMDs are dispatched in one SV_Poll before the main loop
        continues to the UI phase.

        msgs: list of (msg_type, payload) or (msg_type, payload, param1) tuples.
        """
        iv_frames = []
        scmd_parts = []
        for item in msgs:
            if len(item) == 2:
                mt, pl = item
                p1 = 0
            else:
                mt, pl, p1 = item
            scmd = build_game_msg(mt, pl, p1)
            scmd_parts.append(scmd)
            session_frame = self._build_session_data_frame(scmd)
            iv_frames.append(sv_encode(session_frame))

        # Single TCP write — all IV frames arrive in one socket buffer read
        combined = b''.join(iv_frames)
        log.info("[S%d] >> WIRE TX ATOMIC (%d bytes, %d frames): %s",
                 self.sid, len(combined), len(iv_frames), combined.hex())
        async with self._write_lock:
            self.writer.write(combined)
            await self.writer.drain()

        for i, item in enumerate(msgs):
            mt = item[0]
            pl = item[1]
            log.info("[S%d] >> SEND 0x%04X (%d bytes payload, send_seq=%d, atomic %d/%d)",
                     self.sid, mt, len(pl), self.send_seq, i + 1, len(msgs))
            log.debug("[S%d] >> SCMD:\n%s", self.sid,
                      full_hexdump(scmd_parts[i], f"SCMD 0x{mt:04X}"))

    async def recv_iv(self) -> bytes:
        """Receive one complete IV frame. Handles keepalives transparently."""
        while True:
            b = await self.reader.read(1)
            if not b:
                raise ConnectionError("Connection closed")

            if b == b'$':
                buf = b''
                while True:
                    c = await self.reader.read(1)
                    if not c:
                        raise ConnectionError("Connection closed in keepalive")
                    buf += c
                    if c == b'\n':
                        break
                log.info("[S%d] Client keepalive received", self.sid)
                continue

            if b == b'I':
                b2 = await self.reader.read(1)
                if not b2:
                    raise ConnectionError("Connection closed")
                if b2 == b'V':
                    break
                log.info("[S%d] recv_iv: got 'I' then 0x%02X", self.sid, b2[0])
                continue
            log.info("[S%d] recv_iv: 0x%02X '%s'",
                     self.sid, b[0], chr(b[0]) if 32 <= b[0] < 127 else '.')

        hex_bytes = await self._readexact(6)
        size_str = hex_bytes[0:3].decode('ascii', errors='replace')
        comp_str = hex_bytes[3:6].decode('ascii', errors='replace')
        log.info("[S%d] IV header: IV%s%s", self.sid, size_str, comp_str)

        try:
            size = int(size_str, 16)
            comp = int(comp_str, 16)
        except ValueError:
            log.warning("[S%d] Invalid IV hex: %s%s", self.sid, size_str, comp_str)
            return b''

        if (size ^ comp) != 0xFFF:
            log.warning("[S%d] IV integrity fail: 0x%03X ^ 0x%03X", self.sid, size, comp)

        if size > 0:
            payload = await self._readexact(size)
            log.debug("[S%d] IV payload (%d bytes)", self.sid, size)
            return payload
        return b''

    async def _readexact(self, n: int) -> bytes:
        """Read exactly n bytes."""
        buf = b''
        while len(buf) < n:
            chunk = await self.reader.read(n - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed during read")
            buf += chunk
        return buf

    # ----------------------------------------------------------
    # Session Protocol (verbatim from v3)
    # ----------------------------------------------------------
    def _session_checksum(self, payload: bytearray) -> int:
        """Calculate session checksum: sum of all bytes with [2:6] zeroed, & 0xFFFF."""
        total = 0
        for i, b in enumerate(payload):
            if 2 <= i < 6:
                continue
            total += b
        return total & 0xFFFF

    def _build_session_data_frame(self, scmd_data: bytes) -> bytes:
        """Build 0x00-type session DATA frame wrapping SCMD data."""
        frame = bytearray(20 + len(scmd_data))
        frame[0] = 0x00
        frame[1] = 0x03
        struct.pack_into('>I', frame, 8, self.send_seq)
        struct.pack_into('>I', frame, 12, self.send_seq + 1)
        struct.pack_into('>H', frame, 16, len(scmd_data))
        frame[20:20 + len(scmd_data)] = scmd_data
        checksum = self._session_checksum(frame)
        struct.pack_into('>H', frame, 2, checksum)
        self.send_seq += len(scmd_data)
        return bytes(frame)

    def _decode_0xa6_payload(self, raw: bytes) -> bytes:
        """Extract SCMD game data from 0xA6 escape-encoded session frame."""
        if len(raw) < 8 or raw[0] != 0xA6:
            return b''
        flags = raw[1]
        if not (flags & 0x02):
            log.info("[S%d] 0xA6 status frame (no data), flags=0x%02X", self.sid, flags)
            return b''

        escape_byte = raw[6]
        pos = 8

        def read_escaped():
            nonlocal pos
            if pos >= len(raw):
                return 0
            b = raw[pos]
            pos += 1
            if b == escape_byte and pos < len(raw):
                b = raw[pos] ^ 0x60
                pos += 1
            return b & 0xFF

        seq = (read_escaped() << 24) | (read_escaped() << 16) | (read_escaped() << 8) | read_escaped()
        val2 = (read_escaped() << 24) | (read_escaped() << 16) | (read_escaped() << 8) | read_escaped()
        self.client_seq = seq
        log.info("[S%d] 0xA6 data: seq=%d, val2=0x%08X", self.sid, seq, val2)
        pos += 4

        scmd = bytearray()
        while pos < len(raw):
            scmd.append(read_escaped())

        if scmd:
            log.info("[S%d] Extracted SCMD (%d bytes): %s",
                     self.sid, len(scmd), scmd[:32].hex() + ('...' if len(scmd) > 32 else ''))
        return bytes(scmd)

    async def _send_session_establishment(self):
        """Send initial 256-byte session establishment IV frame.

        CRITICAL: Do NOT reset send_seq or client_seq.
        Evidence (dd_server_20260405_200832.log): Old success PRESERVED send_seq
        across re-establishment (1201→1260, 1576→1635). Client accepted continued
        seq values after SV_Init. Resetting to 0 causes client to respond with
        garbage seq (dd_server_20260407_172833.log: seq=3153728 after reset).
        Client delivery function at 0x060423C8 accepts any seq after ESTABLISH
        flag sets session state=2. Subsequent DATA frames use preserved offsets.
        """
        payload = bytearray(256)
        payload[0] = 0x00
        payload[1] = 0x00
        struct.pack_into('>H', payload, 8, 0x0008)
        checksum = self._session_checksum(payload)
        struct.pack_into('>H', payload, 2, checksum)
        await self.send_iv(bytes(payload))
        log.info("[S%d] Sent session establishment (256B, cksum=0x%04X, send_seq preserved=%d, client_seq preserved=%d)",
                 self.sid, checksum, self.send_seq, self.client_seq)

    # ----------------------------------------------------------
    # Session message loop (verbatim from v3)
    # ----------------------------------------------------------
    async def _session_message_loop(self):
        """Unified session message loop — handles 0xA6 and 0x00 frames."""
        msg_num = 0
        while self.running:
            try:
                raw = await asyncio.wait_for(self.recv_iv(), timeout=60.0)
            except asyncio.TimeoutError:
                continue
            if not raw:
                continue
            msg_num += 1

            if raw[0] == 0xA6:
                flags = raw[1]
                log.info("[S%d] << RECV 0xA6 #%d (%d bytes, flags=0x%02X)",
                         self.sid, msg_num, len(raw), flags)
                scmd_data = self._decode_0xa6_payload(raw)
                if scmd_data and len(scmd_data) >= 8:
                    msg_type, payload, param1 = parse_game_msg(scmd_data)
                    if msg_type is not None:
                        log.info("[S%d] << SCMD 0x%04X (%d bytes)", self.sid, msg_type, len(payload))
                        await self._dispatch(msg_type, payload, param1)
            elif raw[0] == 0x00:
                log.info("[S%d] Recv 0x00 #%d (%d bytes)", self.sid, msg_num, len(raw))
                if len(raw) >= 20 and (raw[1] & 0x02):
                    data_len = struct.unpack_from('>H', raw, 16)[0]
                    scmd_data = raw[20:20 + data_len]
                    if len(scmd_data) >= 8:
                        msg_type, payload, param1 = parse_game_msg(scmd_data)
                        if msg_type is not None:
                            await self._dispatch(msg_type, payload, param1)
            else:
                msg_type, payload, param1 = parse_game_msg(raw)
                if msg_type is not None:
                    await self._dispatch(msg_type, payload, param1)

    # ----------------------------------------------------------
    # BBS handshake (verbatim from v3)
    # ----------------------------------------------------------
    async def bbs_handshake(self) -> bool:
        """Handle BBS command phase."""
        try:
            got_p = False
            got_set = False
            got_hrpg = False

            while not got_hrpg:
                line = await asyncio.wait_for(self._read_bbs_line(), timeout=30.0)
                text = line.strip()
                log.info("[S%d] BBS: %r", self.sid, text)

                if not got_p:
                    if text in (b'P', b' P'):
                        self.writer.write(b'*\r\n')
                        await self.writer.drain()
                        got_p = True
                    continue
                if not got_set:
                    if text.startswith(b'SET'):
                        self.writer.write(b'*\r\n')
                        await self.writer.drain()
                        got_set = True
                    continue
                if text.startswith(b'C '):
                    self.writer.write(b'COM\r\n')
                    await self.writer.drain()
                    got_hrpg = True

            return True
        except asyncio.TimeoutError:
            log.warning("[S%d] BBS handshake timeout", self.sid)
            return False

    async def _read_bbs_line(self) -> bytes:
        """Read bytes until \\r."""
        buf = b''
        while True:
            b = await self.reader.read(1)
            if not b:
                raise ConnectionError("Closed during BBS")
            buf += b
            if b == b'\r':
                return buf

    # ----------------------------------------------------------
    # Keepalive (verbatim from v3)
    # ----------------------------------------------------------
    def _build_keepalive_frame(self) -> bytes:
        """Build session ACK-only frame for keepalive."""
        frame = bytearray(20)
        frame[0] = 0x00
        frame[1] = 0x01
        struct.pack_into('>I', frame, 8, self.send_seq)
        struct.pack_into('>I', frame, 12, self.send_seq + 1)
        struct.pack_into('>H', frame, 16, 0)
        checksum = self._session_checksum(frame)
        struct.pack_into('>H', frame, 2, checksum)
        return bytes(frame)

    async def _keepalive_loop(self):
        """Send IV-wrapped session ACK frames every 6 seconds.
        Paused during zone transition (SV_Init window) to avoid
        sending frames while client SV layer is being reset.
        Evidence: SV_RecvFrame at file 0x0126DA resets to state 0
        after SV_Init — stray frames during reset cause errors."""
        try:
            while self.running:
                await asyncio.sleep(6.0)
                if self.running and not self._zone_transitioning:
                    frame = self._build_keepalive_frame()
                    await self.send_iv(frame)
                    log.debug("[S%d] >> Keepalive (seq=%d)", self.sid, self.send_seq)
        except (ConnectionError, asyncio.CancelledError):
            pass

    # ----------------------------------------------------------
    # Main handler
    # ----------------------------------------------------------
    async def handle(self):
        """Main entry point for a client session."""
        addr = self.writer.get_extra_info('peername')
        log.info("[S%d] Connected from %s", self.sid, addr)

        try:
            if not await self.bbs_handshake():
                return
            log.info("[S%d] BBS complete, starting session", self.sid)

            await asyncio.sleep(0.5)
            await self._send_session_establishment()
            self.keepalive_task = asyncio.ensure_future(self._keepalive_loop())
            await self._session_message_loop()

        except (ConnectionError, asyncio.IncompleteReadError) as e:
            log.info("[S%d] Disconnected: %s", self.sid, e)
        except Exception as e:
            log.error("[S%d] Error: %s", self.sid, e, exc_info=True)
        finally:
            self.running = False
            if self.keepalive_task:
                self.keepalive_task.cancel()
            # Unregister from world
            from .world import world
            world.unregister_player(self)
            # Save character state
            if self.char:
                try:
                    self.db.save_character(self.char)
                except Exception:
                    pass
            try:
                self.writer.close()
            except Exception:
                pass
            log.info("[S%d] Session closed", self.sid)

    # ----------------------------------------------------------
    # Message dispatch
    # ----------------------------------------------------------
    async def _dispatch(self, msg_type: int, payload: bytes, param1: int):
        """Route message to handler."""
        # SIT_DIAG: when the post-sit diagnostic flag is set (by h_sakaya_sit),
        # log every incoming SCMD with full payload hexdump. This captures what
        # the client requests/sends after the gate-bypass patch lets the state
        # machine progress past sit-state-0. The output is grep-able with the
        # tag "SIT_DIAG_RX" for post-test analysis.
        if getattr(self, "_diag_post_sit", False):
            try:
                hd = full_hexdump(payload, f"0x{msg_type:04X} (param1=0x{param1:04X})")
            except Exception:
                hd = payload[:64].hex()
            log.info("[S%d] SIT_DIAG_RX 0x%04X param1=0x%04X len=%d\n%s",
                     self.sid, msg_type, param1, len(payload), hd)

        handler = self._handlers.get(msg_type)
        if handler:
            try:
                await handler(self, msg_type, payload, param1)
            except Exception as e:
                log.error("[S%d] Handler error for 0x%04X: %s", self.sid, msg_type, e, exc_info=True)
                # Try to send fallback reply so Saturn doesn't hang
                reply_type = PAIRED_TABLE.get(msg_type)
                if reply_type:
                    from .handlers_misc import build_minimal_reply
                    await self.send_msg(reply_type, build_minimal_reply(reply_type, self))
        else:
            # Fallback: use paired table
            reply_type = PAIRED_TABLE.get(msg_type)
            if reply_type:
                from .handlers_misc import build_minimal_reply
                log.debug("[S%d] Fallback 0x%04X -> 0x%04X", self.sid, msg_type, reply_type)
                await self.send_msg(reply_type, build_minimal_reply(reply_type, self))
            else:
                log.warning("[S%d] No handler or paired entry for 0x%04X", self.sid, msg_type)
