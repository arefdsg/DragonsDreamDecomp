#!/usr/bin/env python3
"""
Dragon's Dream — Modem-to-TCP Bridge

Bridges a Saturn NetLink modem connection (via Yabause/Kronos NetLink emulation
or a real serial modem) to the Dragon's Dream revival server over TCP.

Architecture:
  [Saturn/Emulator] <--modem/TCP--> [Bridge :1337] <--TCP--> [Server :8020]

The bridge handles:
  1. BBS-style connection commands ("C HRPG\r", "SET" parameters)
  2. Modem AT command responses (for real hardware)
  3. Transparent byte proxying once connection is established

Usage:
  # For Yabause/Kronos NetLink emulation (internet_enable mode):
  python bridge.py --listen-port 1337 --server-host 127.0.0.1 --server-port 8020

  # Configure emulator NetLink to connect to 127.0.0.1:1337
  # The bridge will handle BBS commands and proxy to the game server

For direct TCP connections (Yabause internet_enable), the bridge is optional —
the game may connect directly to the server on port 8020.
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('Bridge')

# BBS commands the Saturn game sends before entering game protocol
BBS_COMMANDS = {
    b'C HRPG':   'Connect to HRPG game server',
    b'C NETRPG': 'Connect to NETRPG game server',
}


def hexdump_line(data: bytes, max_bytes: int = 32) -> str:
    chunk = data[:max_bytes]
    hex_part = ' '.join(f'{b:02X}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    suffix = f' ... (+{len(data)-max_bytes})' if len(data) > max_bytes else ''
    return f'{hex_part}  {ascii_part}{suffix}'


async def proxy_data(name: str, reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter):
    """Proxy data from reader to writer until EOF."""
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                log.info('%s: EOF', name)
                break
            log.debug('%s: %d bytes: %s', name, len(data), hexdump_line(data))
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        log.info('%s: connection closed', name)
    except Exception as e:
        log.error('%s: error: %s', name, e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_bbs_phase(reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> bool:
    """
    Handle BBS-style commands from the Saturn client.
    Returns True if BBS phase completed and we should connect to game server.
    Returns False if client disconnected or sent unexpected data.
    """
    buf = bytearray()

    while True:
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        except asyncio.TimeoutError:
            if not buf:
                # No BBS commands received — client may be in direct mode
                log.info('No BBS commands received (direct mode)')
                return True
            continue

        if not data:
            return False

        buf.extend(data)
        log.debug('BBS recv: %s', hexdump_line(bytes(buf)))

        # Check for known BBS commands
        for cmd, desc in BBS_COMMANDS.items():
            if buf.startswith(cmd):
                # Wait for \r terminator
                cr_pos = buf.find(b'\r')
                if cr_pos >= 0:
                    full_cmd = bytes(buf[:cr_pos])
                    log.info('BBS command: %s (%s)', full_cmd.decode('ascii', errors='replace'), desc)
                    del buf[:cr_pos+1]

                    # Respond with connection confirmation
                    writer.write(b'\r\n')
                    await writer.drain()
                    return True

        # Check for SET command
        if buf.startswith(b'SET '):
            cr_pos = buf.find(b'\r')
            if cr_pos >= 0:
                set_cmd = bytes(buf[:cr_pos])
                log.info('BBS SET: %s', set_cmd.decode('ascii', errors='replace'))
                del buf[:cr_pos+1]
                # Acknowledge SET
                writer.write(b'\r\n')
                await writer.drain()
                continue

        # Check for OFF command
        if buf.startswith(b'OFF'):
            log.info('BBS OFF command — client disconnecting')
            return False

        # If buffer is getting large without matching, assume direct mode
        if len(buf) > 256:
            log.info('Large unrecognized buffer — assuming direct mode')
            return True


class Bridge:
    """Modem-to-TCP bridge for Dragon's Dream."""

    def __init__(self, listen_port: int = 1337,
                 server_host: str = '127.0.0.1',
                 server_port: int = 8020,
                 skip_bbs: bool = False):
        self.listen_port = listen_port
        self.server_host = server_host
        self.server_port = server_port
        self.skip_bbs = skip_bbs

    async def handle_client(self, client_reader: asyncio.StreamReader,
                            client_writer: asyncio.StreamWriter):
        addr = client_writer.get_extra_info('peername')
        log.info('Client connected from %s:%d', addr[0], addr[1])

        try:
            # Phase 1: Handle BBS commands (unless skipped)
            if not self.skip_bbs:
                ok = await handle_bbs_phase(client_reader, client_writer)
                if not ok:
                    log.info('BBS phase failed — closing connection')
                    client_writer.close()
                    await client_writer.wait_closed()
                    return
                log.info('BBS phase complete — connecting to game server')

            # Phase 2: Connect to game server
            try:
                server_reader, server_writer = await asyncio.open_connection(
                    self.server_host, self.server_port
                )
                log.info('Connected to game server %s:%d',
                         self.server_host, self.server_port)
            except Exception as e:
                log.error('Failed to connect to game server: %s', e)
                client_writer.close()
                await client_writer.wait_closed()
                return

            # Phase 3: Transparent proxy
            log.info('Entering transparent proxy mode')
            task1 = asyncio.create_task(
                proxy_data('client->server', client_reader, server_writer)
            )
            task2 = asyncio.create_task(
                proxy_data('server->client', server_reader, client_writer)
            )
            await asyncio.gather(task1, task2, return_exceptions=True)

        except Exception as e:
            log.error('Bridge error: %s', e)
        finally:
            log.info('Bridge session ended for %s:%d', addr[0], addr[1])
            for w in [client_writer]:
                try:
                    w.close()
                    await w.wait_closed()
                except Exception:
                    pass

    async def start(self):
        server = await asyncio.start_server(
            self.handle_client, '0.0.0.0', self.listen_port
        )
        log.info('Bridge listening on TCP port %d', self.listen_port)
        log.info('Forwarding to game server at %s:%d',
                 self.server_host, self.server_port)
        if self.skip_bbs:
            log.info('BBS phase: SKIP (direct proxy mode)')
        else:
            log.info('BBS phase: ENABLED (handles C HRPG, SET commands)')

        async with server:
            await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(
        description="Dragon's Dream modem-to-TCP bridge"
    )
    ap.add_argument('--listen-port', type=int, default=1337,
                    help='Port to listen on (default 1337)')
    ap.add_argument('--server-host', default='127.0.0.1',
                    help='Game server host (default 127.0.0.1)')
    ap.add_argument('--server-port', type=int, default=8020,
                    help='Game server port (default 8020)')
    ap.add_argument('--skip-bbs', action='store_true',
                    help='Skip BBS command handling (direct proxy)')
    args = ap.parse_args()

    bridge = Bridge(
        listen_port=args.listen_port,
        server_host=args.server_host,
        server_port=args.server_port,
        skip_bbs=args.skip_bbs,
    )
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        log.info('Bridge shutting down')


if __name__ == '__main__':
    main()
