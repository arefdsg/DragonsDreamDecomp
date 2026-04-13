"""
Turn-based combat state machine and damage formulas.
AI-RECONSTRUCTED: All combat math is fabricated — no damage formulas exist in client binary. Evidence: BTL_CMD_REPLY (0x0223) handler at 0x7DCC reads entity_index at [2], action_param (damage) as U16 BE at [6:8], and 16B name at [8:24]. BTL_RESULT_NOTICE (0x0227) at 0x81B0 reads 44B header + N*56B per combatant with U32 exp/reward at +20 and 8xU16 stat_modifiers at +40. Client only displays results — all combat resolution is server-authoritative.
"""
import struct
import random
import logging
from enum import IntEnum
from typing import Optional
from .models import CombatEntity, MonsterDef
from .game_data import MONSTERS, SKILLS
from .protocol import sjis_pad

log = logging.getLogger("DD-Server")


class CombatState(IntEnum):
    IDLE = 0
    ENCOUNTER_PENDING = 1
    BATTLE_INIT = 2
    AWAITING_COMMAND = 3
    RESOLVE_TURN = 4
    BATTLE_END = 5


class CombatInstance:
    """One combat encounter between a player (or party) and monsters."""

    _next_id = 0

    def __init__(self, session):
        CombatInstance._next_id += 1
        self.battle_id = CombatInstance._next_id & 0xFFFF
        self.session = session
        self.state = CombatState.IDLE
        self.entities: list[CombatEntity] = []
        self.turn_number = 0
        self.pending_commands: dict = {}  # entity_id -> (cmd_type, target, action_id, extra)

    def add_player(self, session) -> CombatEntity:
        """Add the player character as a combat entity."""
        char = session.char
        ent = CombatEntity(
            entity_id=len(self.entities),
            name=char.char_name,
            is_player=True,
            char_id=char.char_id,
            hp=char.current_stats[0],
            max_hp=char.base_stats[0],
            mp=char.current_stats[1],
            max_mp=char.base_stats[1],
            atk=char.current_stats[2],   # STR as ATK
            defense=char.current_stats[3],  # VIT as DEF
            agi=char.current_stats[6],   # AGI
            level=char.char_level,
        )
        self.entities.append(ent)
        return ent

    def add_monster(self, monster_id: int) -> Optional[CombatEntity]:
        """Add a monster as a combat entity."""
        mdef = MONSTERS.get(monster_id)
        if not mdef:
            return None
        ent = CombatEntity(
            entity_id=len(self.entities),
            name=mdef.name,
            is_player=False,
            monster_id=monster_id,
            hp=mdef.hp,
            max_hp=mdef.hp,
            mp=mdef.mp,
            max_mp=mdef.mp,
            atk=mdef.atk,
            defense=mdef.defense,
            agi=mdef.agi,
            level=mdef.level,
        )
        self.entities.append(ent)
        return ent

    def process_command(self, entity_id: int, cmd_type: int, target: int,
                        action_id: int, extra: bytes):
        """Store a combat command for resolution."""
        self.pending_commands[entity_id] = (cmd_type, target, action_id, extra)

    def resolve_turn(self) -> list:
        """
        Resolve all pending commands for this turn.
        Returns list of (attacker_id, defender_id, damage, is_kill) tuples.
        # AI-RECONSTRUCTED: Damage formula and turn order are fabricated. Evidence: BTL_CMD (0x0221) client sends B(cmd_type), B(target), W(action_id), D(extra,8) = 12B at 0x013EBE. Server computes damage and sends BTL_CMD_REPLY (0x0223) with U16 action_param (damage) at [6:8]. No damage calculation logic exists in client binary.
        """
        results = []
        self.turn_number += 1

        # Sort by AGI (higher goes first)
        order = sorted(self.entities, key=lambda e: e.agi, reverse=True)

        for entity in order:
            if not entity.is_alive:
                continue

            if entity.is_player:
                # Use player's submitted command
                cmd = self.pending_commands.get(entity.entity_id)
                if not cmd:
                    continue
                cmd_type, target_id, action_id, extra = cmd

                if cmd_type == 0:  # Attack
                    target = self._get_entity(target_id)
                    if target and target.is_alive:
                        dmg = self._calc_physical_damage(entity, target)
                        target.hp = max(0, target.hp - dmg)
                        is_kill = target.hp <= 0
                        if is_kill:
                            target.is_alive = False
                        results.append((entity.entity_id, target.entity_id, dmg, is_kill))

                elif cmd_type == 1:  # Skill
                    skill = SKILLS.get(action_id)
                    if skill and entity.mp >= skill.mp_cost:
                        entity.mp -= skill.mp_cost
                        if skill.target_type in (0, 1):  # enemy target
                            target = self._get_entity(target_id)
                            if target and target.is_alive:
                                dmg = self._calc_skill_damage(entity, target, skill)
                                target.hp = max(0, target.hp - dmg)
                                is_kill = target.hp <= 0
                                if is_kill:
                                    target.is_alive = False
                                results.append((entity.entity_id, target.entity_id, dmg, is_kill))
                        elif skill.target_type in (2, 4):  # heal ally/self
                            heal_target = entity if skill.target_type == 4 else self._get_entity(target_id)
                            if heal_target:
                                heal_amt = skill.base_power + entity.level * 3
                                heal_target.hp = min(heal_target.max_hp, heal_target.hp + heal_amt)
                                results.append((entity.entity_id, heal_target.entity_id, -heal_amt, False))

                elif cmd_type == 2:  # Defend
                    # Temporarily boost defense (handled implicitly)
                    results.append((entity.entity_id, entity.entity_id, 0, False))

                elif cmd_type == 3:  # Flee
                    # AI-RECONSTRUCTED: Flee chance formula is fabricated. Evidence: BTL_CMD client payload cmd_type=3 is flee. CANCEL_ENCOUNT_REQUEST (0x01E4) handler at 0x86C8 reads U16 status — if 0, clears battle slots at g_state+0x4B58. Server decides flee success and sends status=0 to confirm.
                    flee_chance = 0.5
                    avg_monster_agi = sum(e.agi for e in self.entities if not e.is_player and e.is_alive) / max(1, sum(1 for e in self.entities if not e.is_player and e.is_alive))
                    flee_chance += (entity.agi - avg_monster_agi) * 0.05
                    if random.random() < max(0.1, min(0.95, flee_chance)):
                        results.append((entity.entity_id, entity.entity_id, -1, False))  # -1 = fled
                    else:
                        results.append((entity.entity_id, entity.entity_id, 0, False))
            else:
                # Monster AI: simple — attack random living player
                # AI-RECONSTRUCTED: Monster AI is fabricated. Evidence: client sends BTL_CMD (0x0221) only for player actions. Monster turns are resolved entirely server-side and sent as BTL_CMD_REPLY (0x0223) entries. Client at 0x7DCC just displays entity_index, action_bytes, and damage — no monster AI in ROM.
                living_players = [e for e in self.entities if e.is_player and e.is_alive]
                if living_players:
                    target = random.choice(living_players)
                    dmg = self._calc_physical_damage(entity, target)
                    target.hp = max(0, target.hp - dmg)
                    is_kill = target.hp <= 0
                    if is_kill:
                        target.is_alive = False
                    results.append((entity.entity_id, target.entity_id, dmg, is_kill))

        self.pending_commands.clear()
        return results

    def _calc_physical_damage(self, attacker: CombatEntity, defender: CombatEntity) -> int:
        """
        Calculate physical damage.
        # AI-RECONSTRUCTED: Physical damage formula is fabricated. Evidence: BTL_CMD_REPLY (0x0223) handler at 0x7DCC reads damage as U16 BE at payload[6:8] (action_param). Max damage is U16=65535. Client stores result in 22B entity slot via 0x0603FB24 — no damage calculation on client side.
        """
        base = max(1, attacker.atk * 2 - defender.defense)
        variance = random.uniform(0.85, 1.15)
        return max(1, int(base * variance))

    def _calc_skill_damage(self, caster: CombatEntity, target: CombatEntity, skill) -> int:
        """
        Calculate skill damage.
        # AI-RECONSTRUCTED: Skill damage formula is fabricated. Evidence: same as physical — BTL_CMD_REPLY at 0x7DCC delivers damage as U16 BE at [6:8]. BTL_CMD client sends action_id as U16 at payload[2:4] identifying the skill. Server resolves all skill effects.
        """
        base = skill.base_power * (1.0 + caster.level / 10.0) - target.defense / 2.0
        base = max(1, base)
        variance = random.uniform(0.90, 1.10)
        return max(1, int(base * variance))

    def _get_entity(self, entity_id: int) -> Optional[CombatEntity]:
        """Get entity by ID."""
        for e in self.entities:
            if e.entity_id == entity_id:
                return e
        return None

    def is_battle_over(self) -> bool:
        """Check if all monsters or all players are dead."""
        players_alive = any(e.is_player and e.is_alive for e in self.entities)
        monsters_alive = any(not e.is_player and e.is_alive for e in self.entities)
        return not players_alive or not monsters_alive

    def players_won(self) -> bool:
        """Check if players won (all monsters dead, at least one player alive)."""
        return (any(e.is_player and e.is_alive for e in self.entities) and
                not any(not e.is_player and e.is_alive for e in self.entities))

    def calc_rewards(self) -> tuple:
        """
        Calculate battle rewards (total EXP, total gold, drop items).
        # AI-RECONSTRUCTED: Reward formula is fabricated. Evidence: BTL_GOLD_NOTICE (0x01C8) handler at 0x83E4 reads 12B header with U16 battle_gold_total at [2:4], U16 num_groups at [4:6], then per-group U32 entity_id + U16 item_count + action_type. BTL_RESULT_NOTICE (0x0227) at 0x81B0 reads U32 experience/reward per combatant at +20. Server defines all reward values.
        """
        total_exp = 0
        total_gold = 0
        drops = []
        for entity in self.entities:
            if not entity.is_player:
                mdef = MONSTERS.get(entity.monster_id)
                if mdef:
                    total_exp += mdef.exp_reward
                    total_gold += mdef.gold_reward
                    for item_id, chance in mdef.drop_table:
                        if random.randint(1, 100) <= chance:
                            drops.append(item_id)
        return total_exp, total_gold, drops

    # ── Wire format builders ──

    def build_encountmonster_reply(self) -> bytes:
        """
        Build ENCOUNTMONSTER_REPLY (0x01C9) payload.
        10-byte header + N * 32 bytes per entity.
        """
        monsters = [e for e in self.entities if not e.is_player]
        header = bytearray(10)
        header[0] = 0  # encounter_type_0
        header[1] = len(monsters)  # encounter_type_1 = count
        struct.pack_into('>H', header, 2, self.battle_id)
        struct.pack_into('>H', header, 4, 0)  # encounter_param
        struct.pack_into('>H', header, 6, 1)  # battle_field

        payload = bytearray(header)
        for i, m in enumerate(monsters):
            entry = bytearray(32)
            entry[0] = 1  # facing
            entry[1] = 0  # mode
            entry[2] = 0  # field_36
            struct.pack_into('>H', entry, 4, i * 3)  # x_coord
            struct.pack_into('>H', entry, 6, 0)  # y_coord
            entry[8:24] = m.name[:16]  # name
            entry[24] = 0  # status type
            entry[25] = 0
            entry[26] = 0  # race
            entry[27] = 0  # gender
            entry[28] = m.level & 0xFF
            payload.extend(entry)

        return bytes(payload)

    def build_battlemode_notice(self) -> bytes:
        """
        Build BATTLEMODE_NOTICE (0x021F) payload.
        2-byte count + N * 32 bytes per entity.
        Binary evidence: handler at 0x7BF8 reads per entity:
          +0: U8 entity_byte, +1: 3B skip, +4: U16 field_a(HP), +6: U16 field_b(maxHP),
          +8: 5B+3pad status, +16: 16B name. Total=32B. Processing at +32.
        """
        payload = bytearray(2)
        struct.pack_into('>H', payload, 0, len(self.entities))

        for e in self.entities:
            entry = bytearray(32)
            entry[0] = 1 if e.is_player else 0
            # +1:+4 skip (zeros)
            struct.pack_into('>H', entry, 4, e.hp)       # field_a = current HP
            struct.pack_into('>H', entry, 6, e.max_hp)   # field_b = max HP
            # +8: status block (5B data + 3B pad = 8B total)
            entry[8] = 0   # status byte 0
            entry[9] = 0   # status byte 1
            entry[10] = 0  # status byte 2 (class)
            entry[11] = 0  # status byte 3
            entry[12] = e.level & 0xFF  # status byte 4
            # +13:+16 = 3B pad (zeros)
            # +16: 16B name
            name = e.name[:16] if len(e.name) >= 16 else e.name + b'\x00' * (16 - len(e.name))
            entry[16:32] = name
            payload.extend(entry)

        return bytes(payload)

    def build_btl_cmd_reply(self, attacker_id: int, target_id: int,
                            damage: int, is_kill: bool) -> bytes:
        """Build BTL_CMD_REPLY (0x0223) payload: ~24 bytes."""
        payload = bytearray(24)
        # [0:2] skipped (status from fallthrough)
        payload[2] = attacker_id & 0xFF  # entity_index
        payload[3] = 0  # action_byte_0
        payload[4] = 1 if is_kill else 0  # action_byte_1
        payload[5] = 0  # action_flag
        struct.pack_into('>H', payload, 6, damage & 0xFFFF)
        return bytes(payload)

    def build_btl_result_notice(self, results: list) -> bytes:
        """
        Build BTL_RESULT_NOTICE (0x0227): 44-byte header + N * 56 bytes per combatant.
        """
        header = bytearray(44)
        struct.pack_into('>H', header, 0, self.battle_id)
        struct.pack_into('>H', header, 2, len(self.entities))

        total_exp, total_gold, drops = self.calc_rewards()

        payload = bytearray(header)
        for e in self.entities:
            entry = bytearray(56)
            struct.pack_into('>H', entry, 0, e.entity_id)
            struct.pack_into('>H', entry, 2, 1 if e.is_alive else 0)
            entry[4:20] = e.name[:16]
            struct.pack_into('>I', entry, 20, total_exp if e.is_player else 0)
            entry[28] = 1 if e.is_player else 0
            entry[29] = e.level & 0xFF
            payload.extend(entry)

        return bytes(payload)

    def build_btl_end_request(self, won: bool) -> bytes:
        """Build BTL_END_REQUEST (0x01EB): 2 bytes."""
        return struct.pack('>H', 0 if won else 1)

    def build_btl_gold_notice(self) -> bytes:
        """
        Build BTL_GOLD_NOTICE (0x01C8) payload.
        Binary evidence: handler at 0x83E4 reads:
          [0]: U8 result_flag_1, [1]: U8 result_flag_2,
          [2:4]: U16 battle_gold_total, [4:6]: U16 num_groups,
          [6:12]: reserved (6B zeros)
          Per group: [0:4] U32 entity_id, [4:6] U16 item_count,
          [6] U8 action_type (1=gold_gained), [7] U8 action_param
        # AI-RECONSTRUCTED: Gold notice format from handler 0x83E4.
        # Sends 1 group (player) with gold total and no items for simplicity.
        """
        total_exp, total_gold, drops = self.calc_rewards()
        player = next((e for e in self.entities if e.is_player), None)

        # 12-byte header
        header = bytearray(12)
        header[0] = 0  # result_flag_1
        header[1] = 0  # result_flag_2
        struct.pack_into('>H', header, 2, total_gold & 0xFFFF)  # gold total
        struct.pack_into('>H', header, 4, 1)  # num_groups = 1

        # 1 group (player), no items
        group = bytearray(8)
        struct.pack_into('>I', group, 0, player.entity_id if player else 0)
        struct.pack_into('>H', group, 4, 0)  # item_count = 0
        group[6] = 1  # action_type = gold_gained
        group[7] = 0  # action_param

        return bytes(header) + bytes(group)

    def build_btl_end_reply(self, char) -> bytes:
        """
        Build BTL_END_REPLY (0x02F4) payload: 16 bytes.
        Binary evidence: handler at 0x836E reads:
          [0:4] U32 location_id → party_entry+0x1C
          [4:6] U16 x_coord → party_entry+0x66
          [6:8] U16 y_coord → party_entry+0x68
          [8:16] 5B+3pad status_block → party_entry+0x8C
        Restores player field position after battle.
        """
        payload = bytearray(16)
        struct.pack_into('>I', payload, 0, getattr(char, 'zone_id', 0))
        struct.pack_into('>H', payload, 4, getattr(char, 'pos_x', 0))
        struct.pack_into('>H', payload, 6, getattr(char, 'pos_y', 0))
        # status_block at [8:16] = 5B data + 3B pad (zeros = healthy)
        return bytes(payload)
