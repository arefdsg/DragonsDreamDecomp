#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dragon's Dream Revival Server v4 — Entry Point
Feature-complete multi-client game server.

Usage: python -m dragons_dream_server_v4 [--host 0.0.0.0] [--port 8020] [--db dd_world.db]
"""
import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime

from . import __version__
from .db import Database
from .session import DDSession

# ============================================================
# Logging — console + rotating file log
# ============================================================
LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"dd_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

log = logging.getLogger("DD-Server")
log.setLevel(logging.DEBUG)

_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
log.addHandler(_ch)

_fh = logging.FileHandler(_LOG_FILE, encoding='utf-8')
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
log.addHandler(_fh)


# ============================================================
# Server
# ============================================================

_db: Database = None


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle a new client connection."""
    session = DDSession(reader, writer, _db)
    await session.handle()


async def main(host: str, port: int, db_path: str):
    global _db

    log.info("=== Dragon's Dream Revival Server v%s ===", __version__)
    log.info("Log file: %s", _LOG_FILE)

    # Open database
    _db = Database(db_path)
    _db.open()

    # Start TCP server
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ', '.join(str(s.getsockname()) for s in server.sockets)
    log.info("Listening on %s", addrs)
    log.info("Database: %s", os.path.abspath(db_path))

    async with server:
        await server.serve_forever()


def entry_point():
    parser = argparse.ArgumentParser(
        description=f"Dragon's Dream Revival Server v{__version__}"
    )
    parser.add_argument('--host', default='0.0.0.0', help='Bind address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8020, help='Bind port (default: 8020)')
    parser.add_argument('--db', default='dd_world.db', help='SQLite database path (default: dd_world.db)')
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port, args.db))
    except KeyboardInterrupt:
        log.info("Server stopped")
    finally:
        if _db:
            _db.close()


if __name__ == '__main__':
    entry_point()
