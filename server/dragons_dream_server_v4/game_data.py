"""
Static game data: monster tables, item definitions, shop inventories, skill definitions, zone data.
AI-RECONSTRUCTED: All game balance values are fabricated. Evidence: client binary has no built-in monster/item/shop tables — all game data comes from server messages. Stats are 19xU16 BE at CHARDATA_REQUEST handler 0x3648 offsets 72-110 (base) and 110-148 (current), max U16=65535. Levels 1-16 from parse_status at 0x0601A1EA. Classes 0-5 from same.
"""
import struct
from .protocol import sjis_pad
from .models import MonsterDef, ItemDef, SkillDef, ZoneDef, ShopDef

# ============================================================
# Monster Definitions
# AI-RECONSTRUCTED: Monster stats and rewards are fabricated. Evidence: ENCOUNTMONSTER_REPLY (0x01C9) handler at 0x7A6C reads 10B header + N*32B per entity with 16B name at +8, 5B+3pad status_block at +24 (parse_status: class 0-5, level 1-16). Entity stride=0xA4 (164B). No monster table exists in client ROM — server defines all values.
# ============================================================
MONSTERS = {
    1: MonsterDef(1, sjis_pad("Slime", 16), level=1, hp=30, mp=0, atk=8, defense=3, agi=5,
                  exp_reward=10, gold_reward=5, drop_table=[(1, 10)]),
    2: MonsterDef(2, sjis_pad("Goblin", 16), level=2, hp=50, mp=0, atk=12, defense=5, agi=8,
                  exp_reward=20, gold_reward=10, drop_table=[(2, 8)]),
    3: MonsterDef(3, sjis_pad("Bat", 16), level=1, hp=20, mp=0, atk=6, defense=2, agi=15,
                  exp_reward=8, gold_reward=3, drop_table=[]),
    4: MonsterDef(4, sjis_pad("Wolf", 16), level=3, hp=70, mp=0, atk=16, defense=8, agi=14,
                  exp_reward=35, gold_reward=15, drop_table=[(3, 5)]),
    5: MonsterDef(5, sjis_pad("Skeleton", 16), level=4, hp=90, mp=0, atk=20, defense=15, agi=6,
                  exp_reward=50, gold_reward=25, drop_table=[(4, 10)]),
    6: MonsterDef(6, sjis_pad("Imp", 16), level=3, hp=40, mp=30, atk=10, defense=5, agi=12,
                  exp_reward=30, gold_reward=20, drop_table=[(10, 8)]),
    7: MonsterDef(7, sjis_pad("OrcWarrior", 16), level=5, hp=120, mp=0, atk=25, defense=18, agi=10,
                  exp_reward=80, gold_reward=40, drop_table=[(5, 7)]),
    8: MonsterDef(8, sjis_pad("GiantSpider", 16), level=4, hp=80, mp=0, atk=18, defense=10, agi=16,
                  exp_reward=55, gold_reward=30, drop_table=[(11, 5)]),
    9: MonsterDef(9, sjis_pad("DarkMage", 16), level=6, hp=60, mp=80, atk=12, defense=8, agi=12,
                  exp_reward=100, gold_reward=60, drop_table=[(12, 10)]),
    10: MonsterDef(10, sjis_pad("Minotaur", 16), level=7, hp=200, mp=0, atk=35, defense=25, agi=8,
                   exp_reward=150, gold_reward=80, drop_table=[(6, 5)]),
    11: MonsterDef(11, sjis_pad("Wyvern", 16), level=8, hp=250, mp=20, atk=40, defense=30, agi=18,
                   exp_reward=200, gold_reward=100, drop_table=[(7, 3)]),
    12: MonsterDef(12, sjis_pad("Golem", 16), level=9, hp=350, mp=0, atk=45, defense=50, agi=3,
                   exp_reward=250, gold_reward=120, drop_table=[(8, 5)]),
    13: MonsterDef(13, sjis_pad("Lich", 16), level=10, hp=180, mp=200, atk=25, defense=20, agi=14,
                   exp_reward=300, gold_reward=150, drop_table=[(13, 8)]),
    14: MonsterDef(14, sjis_pad("Dragon", 16), level=12, hp=500, mp=100, atk=60, defense=45, agi=15,
                   exp_reward=500, gold_reward=300, drop_table=[(9, 2)]),
    15: MonsterDef(15, sjis_pad("DemonLord", 16), level=14, hp=700, mp=200, atk=75, defense=55, agi=20,
                   exp_reward=800, gold_reward=500, drop_table=[(14, 3)]),
    16: MonsterDef(16, sjis_pad("AncientDrgn", 16), level=16, hp=999, mp=300, atk=90, defense=70, agi=25,
                   exp_reward=1200, gold_reward=800, drop_table=[(15, 1)]),
    17: MonsterDef(17, sjis_pad("Rat", 16), level=1, hp=15, mp=0, atk=5, defense=2, agi=10,
                   exp_reward=5, gold_reward=2, drop_table=[]),
    18: MonsterDef(18, sjis_pad("Snake", 16), level=2, hp=35, mp=0, atk=10, defense=4, agi=12,
                   exp_reward=15, gold_reward=8, drop_table=[(11, 3)]),
    19: MonsterDef(19, sjis_pad("Bandit", 16), level=5, hp=100, mp=0, atk=22, defense=14, agi=13,
                   exp_reward=70, gold_reward=50, drop_table=[(2, 5)]),
    20: MonsterDef(20, sjis_pad("GhostKnight", 16), level=8, hp=220, mp=40, atk=38, defense=35, agi=10,
                   exp_reward=180, gold_reward=90, drop_table=[(8, 4)]),
}

# ============================================================
# Item Definitions
# AI-RECONSTRUCTED: Item structure inferred from wire format. Evidence: GIVE_ITEM_REPLY (0x0295) handler at 0x8E76 reads 16B item_name at +32, U16 equip_slot at +48, 8B attributes at +50, U32 item_price at +60, 8xU16 stat_modifiers at +64. SHOP_IN_REQUEST (0x01FF) handler at 0x5588 reads 22B per item: 16B item_data + U16 fields. Item type_a maps to equip_type 0-5 from parse_status.
# type_a: 0=weapon, 1=armor, 2=shield, 3=helm, 4=accessory, 5=consumable, 6=key
# equip_slot: 0=none, 1=weapon, 2=shield, 3=armor, 4=helm, 5-8=accessory slots
# ============================================================

def _make_item_data(item_id, type_a, type_b, equip_slot, price):
    """Build 16-byte item_data blob for inventory storage."""
    data = bytearray(16)
    struct.pack_into('>H', data, 0, item_id)
    data[2] = type_a
    data[3] = type_b
    data[4] = equip_slot
    struct.pack_into('>I', data, 8, price)
    return bytes(data)


ITEMS = {
    # Weapons (type_a=0)
    1:  ItemDef(1,  sjis_pad("WoodSword", 16), 0, 0, 1, 50,  [5, 0, 0, 0, 0, 0, 0, 0]),
    2:  ItemDef(2,  sjis_pad("ShortSword", 16), 0, 0, 1, 150, [10, 0, 0, 0, 0, 0, 0, 0]),
    3:  ItemDef(3,  sjis_pad("LongSword", 16), 0, 0, 1, 400,  [18, 0, 0, 0, 0, 0, 0, 0]),
    4:  ItemDef(4,  sjis_pad("BoneSword", 16), 0, 1, 1, 600,  [22, 0, 2, 0, 0, 0, 0, 0]),
    5:  ItemDef(5,  sjis_pad("SteelSword", 16), 0, 0, 1, 1200, [30, 0, 0, 0, 0, 0, 0, 0]),
    6:  ItemDef(6,  sjis_pad("GreatAxe", 16), 0, 2, 1, 2000,  [40, 0, 0, 0, 0, 0, 0, 0]),
    7:  ItemDef(7,  sjis_pad("WyvernBlade", 16), 0, 0, 1, 4000, [55, 0, 0, 0, 5, 0, 0, 0]),
    8:  ItemDef(8,  sjis_pad("GolemFist", 16), 0, 3, 1, 5000,  [45, 0, 10, 0, 0, 0, 0, 0]),
    9:  ItemDef(9,  sjis_pad("DragonFang", 16), 0, 0, 1, 10000, [75, 0, 0, 0, 10, 0, 0, 0]),
    # Armor (type_a=1)
    10: ItemDef(10, sjis_pad("LeatherMail", 16), 1, 0, 3, 80,   [0, 5, 0, 0, 0, 0, 0, 0]),
    11: ItemDef(11, sjis_pad("ChainMail", 16), 1, 0, 3, 300,    [0, 12, 0, 0, 0, 0, 0, 0]),
    12: ItemDef(12, sjis_pad("MysticRobe", 16), 1, 1, 3, 500,   [0, 8, 0, 5, 0, 0, 0, 0]),
    13: ItemDef(13, sjis_pad("PlateMail", 16), 1, 0, 3, 1500,   [0, 25, 0, 0, 0, 0, 0, 0]),
    14: ItemDef(14, sjis_pad("DemonArmor", 16), 1, 2, 3, 8000,  [5, 40, 0, 0, 0, 0, 0, 0]),
    # Shield (type_a=2)
    15: ItemDef(15, sjis_pad("WoodShield", 16), 2, 0, 2, 40,    [0, 3, 0, 0, 0, 0, 0, 0]),
    16: ItemDef(16, sjis_pad("IronShield", 16), 2, 0, 2, 250,   [0, 10, 0, 0, 0, 0, 0, 0]),
    17: ItemDef(17, sjis_pad("DrgnShield", 16), 2, 0, 2, 5000,  [0, 30, 0, 5, 0, 0, 0, 0]),
    # Helm (type_a=3)
    18: ItemDef(18, sjis_pad("LeatherCap", 16), 3, 0, 4, 30,    [0, 2, 0, 0, 0, 0, 0, 0]),
    19: ItemDef(19, sjis_pad("IronHelm", 16), 3, 0, 4, 200,     [0, 8, 0, 0, 0, 0, 0, 0]),
    # Accessory (type_a=4)
    20: ItemDef(20, sjis_pad("PowerRing", 16), 4, 0, 5, 500,    [5, 0, 0, 0, 0, 0, 0, 0]),
    21: ItemDef(21, sjis_pad("SpeedBoots", 16), 4, 1, 6, 600,   [0, 0, 0, 0, 5, 0, 0, 0]),
    # Consumables (type_a=5, equip_slot=0)
    22: ItemDef(22, sjis_pad("Herb", 16), 5, 0, 0, 20,          [30, 0, 0, 0, 0, 0, 0, 0]),
    23: ItemDef(23, sjis_pad("Potion", 16), 5, 0, 0, 100,       [100, 0, 0, 0, 0, 0, 0, 0]),
    24: ItemDef(24, sjis_pad("Hi-Potion", 16), 5, 0, 0, 300,    [250, 0, 0, 0, 0, 0, 0, 0]),
    25: ItemDef(25, sjis_pad("Ether", 16), 5, 1, 0, 150,        [0, 50, 0, 0, 0, 0, 0, 0]),
    26: ItemDef(26, sjis_pad("Hi-Ether", 16), 5, 1, 0, 500,     [0, 150, 0, 0, 0, 0, 0, 0]),
    27: ItemDef(27, sjis_pad("Antidote", 16), 5, 2, 0, 30,      [0, 0, 0, 0, 0, 0, 0, 0]),
    28: ItemDef(28, sjis_pad("ReviveLeaf", 16), 5, 3, 0, 800,   [0, 0, 0, 0, 0, 0, 0, 0]),
    # Key items (type_a=6)
    29: ItemDef(29, sjis_pad("DungeonKey", 16), 6, 0, 0, 0,     [0, 0, 0, 0, 0, 0, 0, 0]),
    30: ItemDef(30, sjis_pad("TownPass", 16), 6, 1, 0, 0,       [0, 0, 0, 0, 0, 0, 0, 0]),
}

def get_item_data_blob(item_id: int) -> bytes:
    """Build the 16-byte item_data blob for a given item ID."""
    item = ITEMS.get(item_id)
    if not item:
        return b'\x00' * 16
    return _make_item_data(item_id, item.type_a, item.type_b, item.equip_slot, item.price)

# ============================================================
# Skill Definitions
# AI-RECONSTRUCTED: Skill data is fabricated. Evidence: LOGIN_REQUEST at 0x012C3C sends 8xU16 skill_slots at payload offsets 44-60 from session+0x1780. CHARDATA_REQUEST handler at 0x3648 reads 8xU16 skill_ids at offset 40 and 8xU16 skill_levels at offset 156 (extended data). SKILL_LIST_REQUEST (0x02BA) handler at 0x969C reads U16 status. No skill definitions exist in client — server provides all skill properties.
# target_type: 0=single enemy, 1=all enemies, 2=single ally, 3=all allies, 4=self
# ============================================================
SKILLS = {
    1:  SkillDef(1,  sjis_pad("Fire", 16), mp_cost=8, base_power=20, element=1,
                 target_type=0, learn_cost=200, class_req=[1, 5]),
    2:  SkillDef(2,  sjis_pad("Blizzard", 16), mp_cost=10, base_power=25, element=2,
                 target_type=0, learn_cost=300, class_req=[1]),
    3:  SkillDef(3,  sjis_pad("Thunder", 16), mp_cost=12, base_power=30, element=3,
                 target_type=0, learn_cost=400, class_req=[1]),
    4:  SkillDef(4,  sjis_pad("Heal", 16), mp_cost=6, base_power=30, element=4,
                 target_type=2, learn_cost=150, class_req=[2, 5]),
    5:  SkillDef(5,  sjis_pad("GreatHeal", 16), mp_cost=15, base_power=80, element=4,
                 target_type=2, learn_cost=500, class_req=[2]),
    6:  SkillDef(6,  sjis_pad("GroupHeal", 16), mp_cost=20, base_power=50, element=4,
                 target_type=3, learn_cost=700, class_req=[2]),
    7:  SkillDef(7,  sjis_pad("PowerSlash", 16), mp_cost=5, base_power=15, element=0,
                 target_type=0, learn_cost=100, class_req=[0, 4]),
    8:  SkillDef(8,  sjis_pad("Backstab", 16), mp_cost=4, base_power=25, element=0,
                 target_type=0, learn_cost=150, class_req=[3]),
    9:  SkillDef(9,  sjis_pad("ArrowRain", 16), mp_cost=10, base_power=18, element=0,
                 target_type=1, learn_cost=350, class_req=[4]),
    10: SkillDef(10, sjis_pad("WarCry", 16), mp_cost=8, base_power=0, element=0,
                 target_type=4, learn_cost=200, class_req=[0]),
    11: SkillDef(11, sjis_pad("Firaga", 16), mp_cost=25, base_power=60, element=1,
                 target_type=1, learn_cost=800, class_req=[1]),
    12: SkillDef(12, sjis_pad("Revive", 16), mp_cost=30, base_power=0, element=4,
                 target_type=2, learn_cost=1000, class_req=[2]),
    13: SkillDef(13, sjis_pad("Poison", 16), mp_cost=6, base_power=10, element=5,
                 target_type=0, learn_cost=200, class_req=[1, 3]),
    14: SkillDef(14, sjis_pad("Shield", 16), mp_cost=8, base_power=0, element=0,
                 target_type=4, learn_cost=250, class_req=[0, 2, 4]),
    15: SkillDef(15, sjis_pad("SongOfLife", 16), mp_cost=15, base_power=40, element=4,
                 target_type=3, learn_cost=600, class_req=[5]),
    16: SkillDef(16, sjis_pad("DarkBolt", 16), mp_cost=20, base_power=50, element=5,
                 target_type=0, learn_cost=600, class_req=[1]),
}

# ============================================================
# Shop Definitions
# AI-RECONSTRUCTED: Shop assignments are fabricated. Evidence: SHOP_LIST_REQUEST (0x0203) handler at 0x547A reads H(status), H(item_count), I(shop_id) header + N*20B items stored at g_state+0x6C94 (22B/slot). SHOP_IN_REQUEST (0x01FF) at 0x5588 stores items at g_state+0x7948 (22B/entry, max 32). Shop contents are entirely server-defined.
# ============================================================
SHOPS = {
    1: ShopDef(1, "Starter Shop", [1, 10, 15, 18, 22, 23, 25, 27]),
    2: ShopDef(2, "Armory", [2, 3, 11, 16, 19, 20, 21]),
    3: ShopDef(3, "Magic Shop", [23, 24, 25, 26, 28]),
    4: ShopDef(4, "Advanced Arms", [5, 6, 13, 16, 19, 20, 24, 26]),
    5: ShopDef(5, "Elite Forge", [7, 8, 9, 14, 17, 24, 26, 28]),
}

# ============================================================
# Zone Definitions
# AI-RECONSTRUCTED: Zone definitions are fabricated. Evidence: MAP_NOTICE (0x01DE) handler at 0x6C38 decompresses map data from server. GOTOLIST_REQUEST (0x019B) handler at 0x492E reads 8B header + N*28B destination list at g_state+0xBC. Zone walkability grid at g_state+0x8708 (4B/cell). No zone data hardcoded in client — server provides maps, encounter rates, and connectivity.
# walkability: 48x48 grid, 6 bytes/row, all 0xFF = fully walkable.
# ============================================================
# AI-RECONSTRUCTED: map_x = GOTOLIST icon selector (U8), map_y = display param (U8).
# Evidence: GOTOLIST_REQUEST handler at file 0x492E stores 28B/entry at g_state+0xBC.
# Entry[8..9] = position field read as U16 BE. Display code at file 0x02AB7E reads
# HIGH byte (map_x), adds literal 0x07BC (file 0x02ABA4) = VDP2 character number.
# map_x=0 → character #1980 = valid city icon (visible on hardware 2026-03-31).
# map_x=2-26 → characters #1982-2006 = blank tiles (invisible, confirmed 2026-04-01).
# LOW byte (map_y) stored separately at display[6] as sub-display parameter.
# GOTOLIST rendered as list/menu via state machine at file 0x00DFB0, NOT world map.
ZONES = {
    1: ZoneDef(zone_id=1, name="Starting Town", map_id=1, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.0,
               monster_pool=[], npc_list=[(1, 10, 10, 0), (2, 20, 10, 1)],
               shop_ids=[1, 3], map_x=0, map_y=0),
    2: ZoneDef(zone_id=2, name="Plains", map_id=2, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.05,
               monster_pool=[1, 2, 3, 17, 18], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    3: ZoneDef(zone_id=3, name="Forest", map_id=3, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.07,
               monster_pool=[2, 4, 6, 8, 18], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    4: ZoneDef(zone_id=4, name="Cave Dungeon", map_id=4, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.10,
               monster_pool=[5, 7, 8, 19], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    5: ZoneDef(zone_id=5, name="Dark Tower", map_id=5, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.12,
               monster_pool=[9, 10, 12, 20], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    6: ZoneDef(zone_id=6, name="Dragon's Peak", map_id=6, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.15,
               monster_pool=[11, 13, 14, 15], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    7: ZoneDef(zone_id=7, name="Abyss", map_id=7, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.18,
               monster_pool=[14, 15, 16], npc_list=[], shop_ids=[],
               map_x=0, map_y=0),
    8: ZoneDef(zone_id=8, name="Market Town", map_id=8, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.0,
               monster_pool=[], npc_list=[(3, 15, 15, 0), (4, 25, 15, 1)],
               shop_ids=[2, 4], map_x=0, map_y=0),
    9: ZoneDef(zone_id=9, name="Capital City", map_id=9, width=48, height=48,
               walkability=b'\xff' * 288, encounter_rate=0.0,
               monster_pool=[], npc_list=[(5, 20, 20, 0)],
               shop_ids=[5], map_x=0, map_y=0),
}

# Map zone_id to list of destination zone_ids for GOTOLIST
ZONE_CONNECTIONS = {
    1: [2, 8],
    2: [1, 3, 8],
    3: [2, 4, 5],
    4: [3, 5],
    5: [4, 6],
    6: [5, 7, 9],
    7: [6],
    8: [1, 2, 9],
    9: [6, 8],
}
