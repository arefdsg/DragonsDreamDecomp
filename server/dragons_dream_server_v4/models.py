"""
Data model classes for characters, items, monsters, skills, zones.
"""
from dataclasses import dataclass, field
from typing import Optional
from .config import DEFAULT_BASE_STATS, MAX_INVENTORY_SLOTS, MAX_SKILL_SLOTS


@dataclass
class Character:
    """Represents a player character, maps to party_entry stride 0xA4 (164B)."""
    char_id: int = 0
    char_name: bytes = b'\x00' * 16  # 16 bytes Shift-JIS
    char_class: int = 0              # 0-5
    char_level: int = 1              # 1-16
    char_race: int = 0
    char_gender: int = 0
    experience: int = 0
    gold: int = 1000
    # 19 stats: HP,MP,STR,VIT,INT,MND,AGI,DEX,LUK,CHA,+9
    base_stats: list = field(default_factory=lambda: list(DEFAULT_BASE_STATS[0]))
    current_stats: list = field(default_factory=lambda: list(DEFAULT_BASE_STATS[0]))
    appearance: bytes = b'\x00' * 8
    skill_slots: list = field(default_factory=lambda: [0] * MAX_SKILL_SLOTS)   # skill IDs
    skill_levels: list = field(default_factory=lambda: [0] * MAX_SKILL_SLOTS)  # per-slot level
    equipment: list = field(default_factory=lambda: [0] * 48)  # 24 slots x 2 U16 (item_id, param)
    zone_id: int = 1
    map_id: int = 1
    pos_x: int = 24
    pos_y: int = 24
    facing: int = 1                  # 1-4
    move_mode: int = 1               # 1=walk, 2=run, 3=sneak
    reconnect_flag: int = 0          # 0x0000=new, 0xFFFF=revive

    @property
    def hp(self):
        return self.current_stats[0] if self.current_stats else 100

    @hp.setter
    def hp(self, val):
        if self.current_stats:
            self.current_stats[0] = max(0, min(val, 65535))

    @property
    def mp(self):
        return self.current_stats[1] if len(self.current_stats) > 1 else 50

    @mp.setter
    def mp(self, val):
        if len(self.current_stats) > 1:
            self.current_stats[1] = max(0, min(val, 65535))

    def init_from_class(self, char_class: int):
        """Initialize stats from class defaults."""
        self.char_class = char_class
        if char_class in DEFAULT_BASE_STATS:
            self.base_stats = list(DEFAULT_BASE_STATS[char_class])
            self.current_stats = list(DEFAULT_BASE_STATS[char_class])


@dataclass
class InventoryItem:
    """Represents one inventory slot. 22B/slot on wire."""
    slot_index: int = 0
    item_id: int = 0
    item_data: bytes = b'\x00' * 16  # 16B raw item data blob
    item_type_a: int = 0
    item_type_b: int = 0
    equip_slot: int = 0              # 0=unequipped, 1-24=slot
    item_price: int = 0
    is_equipped: bool = False


@dataclass
class ItemDef:
    """Static item definition from game data."""
    item_id: int = 0
    name: bytes = b'\x00' * 16       # 16B Shift-JIS
    type_a: int = 0                   # item category
    type_b: int = 0                   # sub-category
    equip_slot: int = 0               # which equipment slot (0=none)
    price: int = 0
    stat_modifiers: list = field(default_factory=lambda: [0] * 8)  # 8 x U16 stat mods


@dataclass
class MonsterDef:
    """Static monster definition."""
    monster_id: int = 0
    name: bytes = b'\x00' * 16       # 16B Shift-JIS
    level: int = 1
    hp: int = 50
    mp: int = 0
    atk: int = 10
    defense: int = 5
    agi: int = 10
    exp_reward: int = 10
    gold_reward: int = 5
    drop_table: list = field(default_factory=list)  # [(item_id, drop_chance_percent)]


@dataclass
class SkillDef:
    """Static skill definition."""
    skill_id: int = 0
    name: bytes = b'\x00' * 16
    mp_cost: int = 5
    base_power: int = 10
    element: int = 0                  # 0=none, 1=fire, 2=ice, 3=lightning, 4=holy, 5=dark
    target_type: int = 0              # 0=single enemy, 1=all enemies, 2=single ally, 3=all allies
    learn_cost: int = 100             # gold cost to learn
    class_req: list = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])  # which classes can learn


@dataclass
class ZoneDef:
    """Static zone definition."""
    zone_id: int = 0
    name: str = "Unknown"
    map_id: int = 0
    width: int = 48
    height: int = 48
    walkability: bytes = b'\xff' * 288   # 48 rows x 6 bytes/row, 1=walkable
    encounter_rate: float = 0.05          # per-step encounter chance
    monster_pool: list = field(default_factory=list)  # [monster_id, ...]
    npc_list: list = field(default_factory=list)       # [(npc_id, x, y, type)]
    shop_ids: list = field(default_factory=list)       # shop IDs available in this zone
    # AI-RECONSTRUCTED: GOTOLIST position for world map UI. GOTOLIST_REQUEST (0x019B)
    # entry offset +8 is U16 BE stored as entry[8..9] via read_u16_be at file 0x492E.
    # Position=0 causes all city names to overlap at origin (hardware 2026-03-31).
    # Values 60-240 pushed cities off-screen (hardware 2026-03-31). Small values
    # (2-30 range) needed. Coordinate system unknown — possibly character cells.
    map_x: int = 14                       # world map X position (U8, small values)
    map_y: int = 12                       # world map Y position (U8, small values)


@dataclass
class ShopDef:
    """Static shop definition."""
    shop_id: int = 0
    name: str = "Shop"
    item_ids: list = field(default_factory=list)  # items sold here


@dataclass
class CombatEntity:
    """Runtime combat entity (player or monster in a battle)."""
    entity_id: int = 0
    name: bytes = b'\x00' * 16
    is_player: bool = False
    char_id: int = 0                  # for players
    monster_id: int = 0               # for monsters
    hp: int = 0
    max_hp: int = 0
    mp: int = 0
    max_mp: int = 0
    atk: int = 0
    defense: int = 0
    agi: int = 0
    level: int = 1
    is_alive: bool = True
