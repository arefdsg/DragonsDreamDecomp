"""
SQLite database layer for persistent character, inventory, skill, mail, and bulletin data.
Thread-safe via aiosqlite for async operations.
"""
import sqlite3
import struct
import logging
import os
from typing import Optional
from .models import Character, InventoryItem
from .config import DEFAULT_BASE_STATS, MAX_INVENTORY_SLOTS

log = logging.getLogger("DD-Server")

# ============================================================
# Schema
# ============================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS characters (
    char_id INTEGER PRIMARY KEY AUTOINCREMENT,
    char_name BLOB NOT NULL,           -- 16B Shift-JIS
    char_class INTEGER NOT NULL DEFAULT 0,
    char_level INTEGER NOT NULL DEFAULT 1,
    char_race INTEGER NOT NULL DEFAULT 0,
    char_gender INTEGER NOT NULL DEFAULT 0,
    experience INTEGER NOT NULL DEFAULT 0,
    gold INTEGER NOT NULL DEFAULT 1000,
    base_stats BLOB NOT NULL,          -- 19 x U16 BE = 38 bytes
    current_stats BLOB NOT NULL,       -- 19 x U16 BE = 38 bytes
    appearance BLOB NOT NULL DEFAULT X'0000000000000000',  -- 8 bytes
    skill_slots BLOB NOT NULL DEFAULT X'00000000000000000000000000000000',  -- 8 x U16 = 16B
    skill_levels BLOB NOT NULL DEFAULT X'00000000000000000000000000000000', -- 8 x U16 = 16B
    equipment BLOB NOT NULL,           -- 24 slots x 2 x U16 = 96 bytes
    zone_id INTEGER NOT NULL DEFAULT 4,
    map_id INTEGER NOT NULL DEFAULT 4,
    pos_x INTEGER NOT NULL DEFAULT 24,
    pos_y INTEGER NOT NULL DEFAULT 24,
    facing INTEGER NOT NULL DEFAULT 1,
    move_mode INTEGER NOT NULL DEFAULT 1,
    reconnect_flag INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    char_id INTEGER NOT NULL,
    slot_index INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    item_data BLOB NOT NULL,           -- 16B raw
    item_type_a INTEGER NOT NULL DEFAULT 0,
    item_type_b INTEGER NOT NULL DEFAULT 0,
    equip_slot INTEGER NOT NULL DEFAULT 0,
    item_price INTEGER NOT NULL DEFAULT 0,
    is_equipped INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (char_id) REFERENCES characters(char_id),
    UNIQUE(char_id, slot_index)
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    char_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    skill_level INTEGER NOT NULL DEFAULT 1,
    equipped_slot INTEGER,             -- NULL or 0-7
    FOREIGN KEY (char_id) REFERENCES characters(char_id),
    UNIQUE(char_id, skill_id)
);

CREATE TABLE IF NOT EXISTS mail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_char_id INTEGER NOT NULL,
    from_char_id INTEGER NOT NULL,
    from_name BLOB NOT NULL,           -- 16B Shift-JIS
    subject BLOB NOT NULL,             -- 40B
    body BLOB NOT NULL DEFAULT X'',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (to_char_id) REFERENCES characters(char_id),
    FOREIGN KEY (from_char_id) REFERENCES characters(char_id)
);

CREATE TABLE IF NOT EXISTS bulletin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    dir_name TEXT NOT NULL DEFAULT 'general',
    subdir_name TEXT NOT NULL DEFAULT '',
    subject BLOB NOT NULL,             -- 40B
    body BLOB NOT NULL DEFAULT X'',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (author_id) REFERENCES characters(char_id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_char ON inventory(char_id);
CREATE INDEX IF NOT EXISTS idx_skills_char ON skills(char_id);
CREATE INDEX IF NOT EXISTS idx_mail_to ON mail(to_char_id);
CREATE INDEX IF NOT EXISTS idx_bulletin_dir ON bulletin(dir_name, subdir_name);
"""


def _stats_to_blob(stats: list) -> bytes:
    """Convert 19-element stat list to 38-byte BE blob."""
    out = bytearray(38)
    for i in range(min(19, len(stats))):
        struct.pack_into('>H', out, i * 2, stats[i] & 0xFFFF)
    return bytes(out)


def _blob_to_stats(blob: bytes) -> list:
    """Convert 38-byte BE blob to 19-element stat list."""
    stats = []
    for i in range(19):
        if i * 2 + 2 <= len(blob):
            stats.append(struct.unpack_from('>H', blob, i * 2)[0])
        else:
            stats.append(10)
    return stats


def _equipment_to_blob(equipment: list) -> bytes:
    """Convert 48-element equipment list to 96-byte blob (24 slots x 2 x U16)."""
    out = bytearray(96)
    for i in range(min(48, len(equipment))):
        struct.pack_into('>H', out, i * 2, equipment[i] & 0xFFFF)
    return bytes(out)


def _blob_to_equipment(blob: bytes) -> list:
    """Convert 96-byte blob to 48-element equipment list."""
    equip = []
    for i in range(24):
        idx = i * 4
        if idx + 4 <= len(blob):
            equip.append(struct.unpack_from('>H', blob, idx)[0])
            equip.append(struct.unpack_from('>H', blob, idx + 2)[0])
        else:
            equip.extend([0, 0])
    return equip


def _skill_slots_to_blob(slots: list) -> bytes:
    """Convert 8-element skill slot list to 16-byte blob."""
    out = bytearray(16)
    for i in range(min(8, len(slots))):
        struct.pack_into('>H', out, i * 2, slots[i] & 0xFFFF)
    return bytes(out)


def _blob_to_skill_slots(blob: bytes) -> list:
    """Convert 16-byte blob to 8-element skill slot list."""
    slots = []
    for i in range(8):
        if i * 2 + 2 <= len(blob):
            slots.append(struct.unpack_from('>H', blob, i * 2)[0])
        else:
            slots.append(0)
    return slots


# ============================================================
# Database class
# ============================================================

class Database:
    """Synchronous SQLite database (all calls from asyncio must use run_in_executor)."""

    def __init__(self, db_path: str = "dd_world.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def open(self):
        """Open database connection and create schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        log.info("Database opened: %s", os.path.abspath(self.db_path))

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ── Character CRUD ──

    def create_character(self, name: bytes, char_class: int = 0,
                         race: int = 0, gender: int = 0) -> int:
        """Create a new character, returns char_id."""
        name_16 = (name + b'\x00' * 16)[:16]
        base = DEFAULT_BASE_STATS.get(char_class, DEFAULT_BASE_STATS[0])
        base_blob = _stats_to_blob(base)
        equip_blob = b'\x00' * 96
        skill_blob = b'\x00' * 16

        cur = self.conn.execute(
            """INSERT INTO characters
               (char_name, char_class, char_level, char_race, char_gender,
                experience, gold, base_stats, current_stats, equipment,
                skill_slots, skill_levels)
               VALUES (?, ?, 1, ?, ?, 0, 1000, ?, ?, ?, ?, ?)""",
            (name_16, char_class, race, gender,
             base_blob, base_blob, equip_blob, skill_blob, skill_blob)
        )
        self.conn.commit()
        char_id = cur.lastrowid
        log.info("Created character: id=%d, name=%s, class=%d", char_id, name_16.hex(), char_class)
        return char_id

    def load_character(self, char_id: int) -> Optional[Character]:
        """Load character by ID, returns Character or None."""
        row = self.conn.execute(
            "SELECT * FROM characters WHERE char_id = ?", (char_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_character(row)

    def load_character_by_name(self, name_bytes: bytes) -> Optional[Character]:
        """Load character by name (16-byte Shift-JIS), returns Character or None."""
        name_16 = (name_bytes + b'\x00' * 16)[:16]
        row = self.conn.execute(
            "SELECT * FROM characters WHERE char_name = ?", (name_16,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_character(row)

    def save_character(self, char: Character):
        """Save all mutable character fields."""
        self.conn.execute(
            """UPDATE characters SET
               char_class=?, char_level=?, char_race=?, char_gender=?,
               experience=?, gold=?, base_stats=?, current_stats=?,
               appearance=?, skill_slots=?, skill_levels=?, equipment=?,
               zone_id=?, map_id=?, pos_x=?, pos_y=?, facing=?,
               move_mode=?, reconnect_flag=?, last_login=datetime('now')
               WHERE char_id=?""",
            (char.char_class, char.char_level, char.char_race, char.char_gender,
             char.experience, char.gold,
             _stats_to_blob(char.base_stats), _stats_to_blob(char.current_stats),
             char.appearance, _skill_slots_to_blob(char.skill_slots),
             _skill_slots_to_blob(char.skill_levels), _equipment_to_blob(char.equipment),
             char.zone_id, char.map_id, char.pos_x, char.pos_y, char.facing,
             char.move_mode, char.reconnect_flag, char.char_id)
        )
        self.conn.commit()

    def list_characters(self) -> list:
        """List all characters (for admin/debug)."""
        rows = self.conn.execute("SELECT * FROM characters ORDER BY char_id").fetchall()
        return [self._row_to_character(r) for r in rows]

    def _row_to_character(self, row) -> Character:
        """Convert a database row to a Character object."""
        char = Character()
        char.char_id = row['char_id']
        char.char_name = bytes(row['char_name'])
        char.char_class = row['char_class']
        char.char_level = row['char_level']
        char.char_race = row['char_race']
        char.char_gender = row['char_gender']
        char.experience = row['experience']
        char.gold = row['gold']
        char.base_stats = _blob_to_stats(bytes(row['base_stats']))
        char.current_stats = _blob_to_stats(bytes(row['current_stats']))
        char.appearance = bytes(row['appearance'])
        char.skill_slots = _blob_to_skill_slots(bytes(row['skill_slots']))
        char.skill_levels = _blob_to_skill_slots(bytes(row['skill_levels']))
        char.equipment = _blob_to_equipment(bytes(row['equipment']))
        char.zone_id = row['zone_id']
        char.map_id = row['map_id']
        char.pos_x = row['pos_x']
        char.pos_y = row['pos_y']
        char.facing = row['facing']
        char.move_mode = row['move_mode']
        char.reconnect_flag = row['reconnect_flag']
        return char

    # ── Inventory CRUD ──

    def get_inventory(self, char_id: int) -> list:
        """Get all inventory items for a character."""
        rows = self.conn.execute(
            "SELECT * FROM inventory WHERE char_id = ? ORDER BY slot_index",
            (char_id,)
        ).fetchall()
        items = []
        for row in rows:
            item = InventoryItem(
                slot_index=row['slot_index'],
                item_id=row['item_id'],
                item_data=bytes(row['item_data']),
                item_type_a=row['item_type_a'],
                item_type_b=row['item_type_b'],
                equip_slot=row['equip_slot'],
                item_price=row['item_price'],
                is_equipped=bool(row['is_equipped']),
            )
            items.append(item)
        return items

    def add_item(self, char_id: int, item_id: int, item_data: bytes = b'\x00' * 16,
                 item_type_a: int = 0, item_type_b: int = 0,
                 equip_slot: int = 0, item_price: int = 0) -> int:
        """Add item to next available slot. Returns slot_index or -1 if full."""
        used = set(
            r['slot_index'] for r in
            self.conn.execute("SELECT slot_index FROM inventory WHERE char_id = ?",
                              (char_id,)).fetchall()
        )
        slot = -1
        for i in range(MAX_INVENTORY_SLOTS):
            if i not in used:
                slot = i
                break
        if slot < 0:
            return -1

        self.conn.execute(
            """INSERT INTO inventory
               (char_id, slot_index, item_id, item_data, item_type_a, item_type_b,
                equip_slot, item_price, is_equipped)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (char_id, slot, item_id, item_data[:16],
             item_type_a, item_type_b, equip_slot, item_price)
        )
        self.conn.commit()
        return slot

    def remove_item(self, char_id: int, slot_index: int) -> bool:
        """Remove item from slot. Returns True if removed."""
        cur = self.conn.execute(
            "DELETE FROM inventory WHERE char_id = ? AND slot_index = ?",
            (char_id, slot_index)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def equip_item(self, char_id: int, slot_index: int, equip_slot: int) -> bool:
        """Mark an item as equipped in a specific equipment slot."""
        cur = self.conn.execute(
            "UPDATE inventory SET is_equipped = 1, equip_slot = ? WHERE char_id = ? AND slot_index = ?",
            (equip_slot, char_id, slot_index)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def unequip_item(self, char_id: int, slot_index: int) -> bool:
        """Unequip an item."""
        cur = self.conn.execute(
            "UPDATE inventory SET is_equipped = 0, equip_slot = 0 WHERE char_id = ? AND slot_index = ?",
            (char_id, slot_index)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── Skills CRUD ──

    def get_skills(self, char_id: int) -> list:
        """Get all learned skills for a character."""
        return self.conn.execute(
            "SELECT * FROM skills WHERE char_id = ? ORDER BY skill_id",
            (char_id,)
        ).fetchall()

    def learn_skill(self, char_id: int, skill_id: int, level: int = 1) -> bool:
        """Learn a new skill. Returns False if already known."""
        try:
            self.conn.execute(
                "INSERT INTO skills (char_id, skill_id, skill_level) VALUES (?, ?, ?)",
                (char_id, skill_id, level)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def upgrade_skill(self, char_id: int, skill_id: int) -> int:
        """Increase skill level by 1. Returns new level or 0 if not found."""
        row = self.conn.execute(
            "SELECT skill_level FROM skills WHERE char_id = ? AND skill_id = ?",
            (char_id, skill_id)
        ).fetchone()
        if not row:
            return 0
        new_level = row['skill_level'] + 1
        self.conn.execute(
            "UPDATE skills SET skill_level = ? WHERE char_id = ? AND skill_id = ?",
            (new_level, char_id, skill_id)
        )
        self.conn.commit()
        return new_level

    def equip_skill(self, char_id: int, skill_id: int, slot: int) -> bool:
        """Equip a skill into a slot (0-7)."""
        # Clear any existing skill in this slot
        self.conn.execute(
            "UPDATE skills SET equipped_slot = NULL WHERE char_id = ? AND equipped_slot = ?",
            (char_id, slot)
        )
        cur = self.conn.execute(
            "UPDATE skills SET equipped_slot = ? WHERE char_id = ? AND skill_id = ?",
            (slot, char_id, skill_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def unequip_skill(self, char_id: int, skill_id: int) -> bool:
        """Unequip a skill."""
        cur = self.conn.execute(
            "UPDATE skills SET equipped_slot = NULL WHERE char_id = ? AND skill_id = ?",
            (char_id, skill_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── Mail CRUD ──

    def get_mail_list(self, char_id: int, limit: int = 20) -> list:
        """Get mail list for a character."""
        return self.conn.execute(
            "SELECT id, from_char_id, from_name, subject, is_read, created_at "
            "FROM mail WHERE to_char_id = ? ORDER BY created_at DESC LIMIT ?",
            (char_id, limit)
        ).fetchall()

    def get_mail(self, mail_id: int) -> Optional[sqlite3.Row]:
        """Get a specific mail message."""
        row = self.conn.execute("SELECT * FROM mail WHERE id = ?", (mail_id,)).fetchone()
        if row:
            self.conn.execute("UPDATE mail SET is_read = 1 WHERE id = ?", (mail_id,))
            self.conn.commit()
        return row

    def send_mail(self, from_id: int, to_id: int, from_name: bytes,
                  subject: bytes, body: bytes) -> int:
        """Send mail. Returns mail ID."""
        cur = self.conn.execute(
            "INSERT INTO mail (to_char_id, from_char_id, from_name, subject, body) VALUES (?, ?, ?, ?, ?)",
            (to_id, from_id, from_name[:16], subject[:40], body)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_mail(self, mail_id: int, char_id: int) -> bool:
        """Delete mail (only if recipient)."""
        cur = self.conn.execute(
            "DELETE FROM mail WHERE id = ? AND to_char_id = ?", (mail_id, char_id)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── Bulletin CRUD ──

    def get_bulletin_dirs(self) -> list:
        """Get unique bulletin board directories."""
        return self.conn.execute(
            "SELECT DISTINCT dir_name FROM bulletin ORDER BY dir_name"
        ).fetchall()

    def get_bulletin_subdirs(self, dir_name: str) -> list:
        """Get subdirectories within a dir."""
        return self.conn.execute(
            "SELECT DISTINCT subdir_name FROM bulletin WHERE dir_name = ? ORDER BY subdir_name",
            (dir_name,)
        ).fetchall()

    def get_bulletin_posts(self, dir_name: str, subdir_name: str = '',
                           limit: int = 20) -> list:
        """Get posts in a bulletin board."""
        return self.conn.execute(
            "SELECT * FROM bulletin WHERE dir_name = ? AND subdir_name = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (dir_name, subdir_name, limit)
        ).fetchall()

    def create_bulletin_post(self, author_id: int, dir_name: str,
                             subdir_name: str, subject: bytes, body: bytes) -> int:
        """Create a bulletin board post."""
        cur = self.conn.execute(
            "INSERT INTO bulletin (author_id, dir_name, subdir_name, subject, body) VALUES (?, ?, ?, ?, ?)",
            (author_id, dir_name, subdir_name, subject[:40], body)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_bulletin_post(self, post_id: int) -> bool:
        """Delete a bulletin post."""
        cur = self.conn.execute("DELETE FROM bulletin WHERE id = ?", (post_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def create_bulletin_dir(self, dir_name: str) -> bool:
        """Create directory by inserting a placeholder (if no posts exist yet)."""
        # Directories are implicit from posts, but we insert a placeholder
        existing = self.conn.execute(
            "SELECT 1 FROM bulletin WHERE dir_name = ? LIMIT 1", (dir_name,)
        ).fetchone()
        if existing:
            return False
        self.conn.execute(
            "INSERT INTO bulletin (author_id, dir_name, subdir_name, subject, body) "
            "VALUES (0, ?, '', X'00', X'')", (dir_name,)
        )
        self.conn.commit()
        return True

    def delete_bulletin_dir(self, dir_name: str) -> bool:
        """Delete all posts in a directory."""
        cur = self.conn.execute("DELETE FROM bulletin WHERE dir_name = ?", (dir_name,))
        self.conn.commit()
        return cur.rowcount > 0
