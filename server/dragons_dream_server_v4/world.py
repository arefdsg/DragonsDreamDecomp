"""
Shared world state: zone management, player registry, broadcasting.
Thread-safe via asyncio (single event loop, no GIL issues).
"""
import asyncio
import logging
import random
import struct
from typing import Optional, Dict, Set
from .game_data import ZONES, ZONE_CONNECTIONS

log = logging.getLogger("DD-Server")


class World:
    """Singleton world state holding all active sessions and zone data."""

    def __init__(self):
        # char_id -> session mapping
        self.sessions: Dict[int, 'DDSession'] = {}
        # zone_id -> set of char_ids in that zone
        self.zone_players: Dict[int, Set[int]] = {zid: set() for zid in ZONES}

    def register_player(self, session):
        """Add a player to the world when they complete login."""
        char_id = session.char.char_id
        zone_id = session.char.zone_id
        self.sessions[char_id] = session
        if zone_id not in self.zone_players:
            self.zone_players[zone_id] = set()
        self.zone_players[zone_id].add(char_id)
        log.info("World: registered char_id=%d in zone %d (%d online)",
                 char_id, zone_id, len(self.sessions))

    def unregister_player(self, session):
        """Remove a player from the world on disconnect."""
        if not session.char:
            return
        char_id = session.char.char_id
        zone_id = session.char.zone_id
        self.sessions.pop(char_id, None)
        if zone_id in self.zone_players:
            self.zone_players[zone_id].discard(char_id)
        log.info("World: unregistered char_id=%d (%d online)",
                 char_id, len(self.sessions))

    def move_player_zone(self, session, new_zone_id: int):
        """Move a player from their current zone to a new one."""
        if not session.char:
            return
        char_id = session.char.char_id
        old_zone = session.char.zone_id
        if old_zone in self.zone_players:
            self.zone_players[old_zone].discard(char_id)
        session.char.zone_id = new_zone_id
        if new_zone_id not in self.zone_players:
            self.zone_players[new_zone_id] = set()
        self.zone_players[new_zone_id].add(char_id)
        log.info("World: char_id=%d moved zone %d -> %d", char_id, old_zone, new_zone_id)

    def get_players_in_zone(self, zone_id: int, exclude_char_id: int = 0) -> list:
        """Get all sessions in a zone, optionally excluding one."""
        result = []
        for cid in self.zone_players.get(zone_id, set()):
            if cid != exclude_char_id and cid in self.sessions:
                result.append(self.sessions[cid])
        return result

    async def broadcast_to_zone(self, zone_id: int, msg_type: int,
                                payload: bytes, exclude_char_id: int = 0):
        """Send a message to all players in a zone except the excluded one."""
        targets = self.get_players_in_zone(zone_id, exclude_char_id)
        for session in targets:
            try:
                await session.send_msg(msg_type, payload)
            except Exception as e:
                log.warning("World: broadcast to char_id=%d failed: %s",
                            session.char.char_id if session.char else 0, e)

    def get_session_by_char_id(self, char_id: int) -> Optional['DDSession']:
        """Look up a session by character ID."""
        return self.sessions.get(char_id)

    def get_session_by_name(self, name_bytes: bytes) -> Optional['DDSession']:
        """Look up a session by character name (16-byte match)."""
        name_16 = (name_bytes + b'\x00' * 16)[:16]
        for session in self.sessions.values():
            if session.char and session.char.char_name == name_16:
                return session
        return None

    def should_encounter(self, zone_id: int) -> bool:
        """Roll for random encounter based on zone encounter rate.
        # AI-RECONSTRUCTED: encounter_rate per step, server-authoritative.
        """
        zone = ZONES.get(zone_id)
        if not zone or zone.encounter_rate <= 0:
            return False
        return random.random() < zone.encounter_rate

    def get_random_monster(self, zone_id: int) -> Optional[int]:
        """Pick a random monster ID from the zone's pool.
        # AI-RECONSTRUCTED: uniform random from zone monster pool.
        """
        zone = ZONES.get(zone_id)
        if not zone or not zone.monster_pool:
            return None
        return random.choice(zone.monster_pool)

    @property
    def online_count(self) -> int:
        return len(self.sessions)


class BotPlayer:
    """Simulated player for tavern tables and party formation.
    # AI-RECONSTRUCTED: Bot players fill tavern tables so real players can sit,
    # form parties, and transition to dungeons. Original game required 2+ players.
    """

    def __init__(self, char_id, name, char_class=0, level=3, zone_id=4):
        self.char_id = char_id
        self.char_name = (name.encode('ascii') + b'\x00' * 16)[:16]
        self.char_class = char_class
        self.char_level = level
        self.char_race = 0
        self.char_gender = 0
        self.zone_id = zone_id
        self.experience = level * 100
        self.gold = level * 50
        self.current_stats = [120, 30, 18, 16, 8, 10, 12, 10, 10, 10,
                              10, 10, 10, 10, 10, 10, 10, 10, 10]

    def build_chardata_notice(self):
        """Build 76-byte CHARDATA_NOTICE payload matching the proven format."""
        payload = bytearray(76)
        struct.pack_into('>H', payload, 0, self.char_id & 0xFFFF)
        payload[2:2 + min(16, len(self.char_name))] = self.char_name[:16]
        payload[24] = 0
        payload[25] = 0
        payload[26] = self.char_race
        payload[27] = self.char_gender
        payload[28] = self.char_level
        struct.pack_into('>I', payload, 32, self.experience)
        struct.pack_into('>I', payload, 36, self.gold)
        for i in range(min(8, len(self.current_stats))):
            struct.pack_into('>H', payload, 40 + i * 2, self.current_stats[i])
        payload[58] = self.char_class
        payload[63] = self.char_level
        payload[67] = 1  # has_equip_stats = nonzero → skip
        payload[71] = 1  # has_equip_items = nonzero → skip
        return bytes(payload)


# Pre-defined bot players for tavern tables
BOT_PLAYERS = [
    BotPlayer(char_id=100, name="Hikaru", char_class=0, level=5, zone_id=4),
    BotPlayer(char_id=101, name="Ryuji", char_class=1, level=4, zone_id=4),
    BotPlayer(char_id=102, name="Sakura", char_class=2, level=3, zone_id=4),
]

# Tavern table definitions: (table_id, display_name, bot_player or None)
TAVERN_TABLES = [
    (1, "Temple", BOT_PLAYERS[0]),      # Bot sitting at Temple table
    (2, "Dragon's Peak", BOT_PLAYERS[1]),  # Bot sitting at Dragon's Peak
    (3, "Training", BOT_PLAYERS[2]),     # Bot sitting at Training table
]


# Global singleton
world = World()
