"""
Combat handlers: encounter initiation, battle commands, resolution, end.
AI-RECONSTRUCTED: Combat message flow from client handler decompilation. Evidence: ENCOUNTMONSTER_REQUEST (0x0244) at 0x7A2A reads U16 status. ENCOUNTMONSTER_REPLY (0x01C9) at 0x7A6C reads 10B header + N*32B entities (16B name at +8, 5B+3pad status at +24). ENCOUNTMONSTER_NOTICE (0x01CA) at 0x7BEC: 0B, sets g_state[0xF4B9]=0. BATTLEMODE_NOTICE (0x021F) at 0x7BF8 reads U16 count + N*32B (1+3+2+2+8+16=32 per entity). BTL_CMD_REQUEST (0x0222) at 0x7D88 reads U16 status then falls through to BTL_CMD_REPLY (0x0223) at 0x7DCC. BTL_GOLD_NOTICE (0x01C8) at 0x83E4 reads 12B hdr + groups. BTL_END_REQUEST (0x01EB) at 0x8356 reads U16 end_status. BTL_END_REPLY (0x02F4) at 0x836E reads 16B (zone,x,y,status).
"""
import struct
import asyncio
import random
import logging
from .config import *
from .combat_engine import CombatInstance, CombatState
from .game_data import MONSTERS

log = logging.getLogger("DD-Server")


async def start_encounter(session):
    """
    Server-initiated random encounter.
    # AI-RECONSTRUCTED: Server-initiated encounters inferred. Evidence: ENCOUNTMONSTER_REQUEST (0x0244) handler at 0x7A2A reads only U16 status — no encounter probability logic in client. Client MOVE (0x01C1) at 0x013A9A sends only 1-3 direction bytes. ENCOUNTMONSTER_NOTICE (0x01CA) at 0x7BEC has no payload (just sets g_state[0xF4B9]=0). Server must initiate all encounters.
    """
    from .world import world

    char = session.char
    if not char or session.combat:
        return

    monster_id = world.get_random_monster(char.zone_id)
    if not monster_id:
        return

    # Create combat instance
    combat = CombatInstance(session)
    combat.add_player(session)

    # Add 1-3 monsters based on zone level
    # AI-RECONSTRUCTED: Monster count scaling is fabricated. Evidence: ENCOUNTMONSTER_REPLY (0x01C9) at 0x7A6C reads entity count from encounter_type_1 at payload[1]. Entity stride=0xA4, stored at battle_base+0x0522. Server sends any number of entities — client simply iterates the loop.
    zone_monsters = [monster_id]
    mdef = MONSTERS.get(monster_id)
    if mdef and mdef.level < char.char_level:
        extra = random.randint(0, 2)
        for _ in range(extra):
            zone_monsters.append(monster_id)

    for mid in zone_monsters:
        combat.add_monster(mid)

    session.combat = combat
    combat.state = CombatState.BATTLE_INIT

    log.info("[S%d] Encounter: %d monsters (ids=%s)", session.sid,
             len(zone_monsters), zone_monsters)

    # 1. Send ENCOUNTMONSTER_REQUEST (0x0244): status=0 (2B)
    await session.send_msg(MSG_ENCOUNTMONSTER_REQ, struct.pack('>H', 0))
    await asyncio.sleep(0.05)

    # 2. Send ENCOUNTMONSTER_REPLY (0x01C9): entity data (10+N*32B)
    await session.send_msg(MSG_ENCOUNTMONSTER_RPL, combat.build_encountmonster_reply())
    await asyncio.sleep(0.05)

    # 3. Send ENCOUNTMONSTER_NOTICE (0x01CA): 0B payload
    #    Binary evidence: handler at 0x7BEC sets g_state[0xF4B9]=0 (clears flag)
    await session.send_msg(MSG_ENCOUNTMONSTER_NTC, b'')
    await asyncio.sleep(0.05)

    # 4. Send BATTLEMODE_NOTICE (0x021F): all entities (2+N*32B)
    await session.send_msg(MSG_BATTLEMODE_NOTICE, combat.build_battlemode_notice())

    combat.state = CombatState.AWAITING_COMMAND


async def h_monsterwarn(session, msg_type, payload, param1):
    """0x0243 -> ENCOUNTMONSTER_REQUEST (0x0244). Client-initiated encounter."""
    if session.combat:
        # Already in combat
        await session.send_msg(MSG_ENCOUNTMONSTER_REQ, struct.pack('>H', 1))
        return
    # Initiate encounter
    await start_encounter(session)


async def h_btl_cmd(session, msg_type, payload, param1):
    """
    0x0221 - Battle command from player.
    Client payload: B(cmd_type), B(target), W(action_id), D(extra,8) = 12 bytes
    """
    combat = session.combat
    if not combat or combat.state != CombatState.AWAITING_COMMAND:
        await session.send_msg(MSG_BTL_CMD_REQUEST, struct.pack('>H', 1))
        return

    cmd_type = payload[0] if len(payload) > 0 else 0
    target = payload[1] if len(payload) > 1 else 0
    action_id = struct.unpack_from('>H', payload, 2)[0] if len(payload) >= 4 else 0
    extra = payload[4:12] if len(payload) >= 12 else b'\x00' * 8

    log.info("[S%d] BTL_CMD: cmd=%d target=%d action=%d",
             session.sid, cmd_type, target, action_id)

    # Store player command
    player_entity = next((e for e in combat.entities if e.is_player), None)
    if player_entity:
        combat.process_command(player_entity.entity_id, cmd_type, target, action_id, extra)

    # Check for flee
    if cmd_type == 3:
        results = combat.resolve_turn()
        fled = any(d == -1 for _, _, d, _ in results if d == -1)
        if fled:
            # Flee successful
            await session.send_msg(MSG_BTL_CMD_REQUEST, struct.pack('>H', 0))
            await asyncio.sleep(0.1)
            await session.send_msg(MSG_CANCEL_ENCOUNT_REQ, struct.pack('>H', 0))
            session.combat = None
            return

    # Resolve turn
    combat.state = CombatState.RESOLVE_TURN
    results = combat.resolve_turn()

    # Send BTL_CMD_REQUEST with status=0 (acknowledge)
    await session.send_msg(MSG_BTL_CMD_REQUEST, struct.pack('>H', 0))
    await asyncio.sleep(0.05)

    # Send BTL_CMD_REPLY for each action result
    for attacker_id, target_id, damage, is_kill in results:
        reply = combat.build_btl_cmd_reply(attacker_id, target_id, damage, is_kill)
        await session.send_msg(MSG_BTL_CMD_REPLY, reply)
        await asyncio.sleep(0.02)

    # Check if battle is over
    if combat.is_battle_over():
        await _end_battle(session, combat)
    else:
        # Send BTL_RESULT_NOTICE with current state
        await session.send_msg(MSG_BTL_RESULT_NOTICE, combat.build_btl_result_notice())
        combat.state = CombatState.AWAITING_COMMAND


async def h_btl_chgmode(session, msg_type, payload, param1):
    """0x0224 -> BTL_CHGMODE_REQUEST (0x0225). Change battle mode."""
    await session.send_msg(MSG_BTL_CHGMODE_REQ, struct.pack('>H', 0))


async def h_btl_effectend(session, msg_type, payload, param1):
    """0x0296 -> BTL_EFFECTEND_REQUEST (0x0297). Effect animation complete."""
    await session.send_msg(MSG_BTL_EFFECTEND_REQ, b'')  # Empty handler


async def h_btl_end(session, msg_type, payload, param1):
    """
    0x01EA -> BTL_END_REQUEST (0x01EB) + BTL_END_REPLY (0x02F4).
    Client sends 0x01EA after processing battle results display.
    Server responds with end status + position restoration.
    Binary evidence: paired table 0x01EA→0x01EB. BTL_END_REPLY (0x02F4)
    handler at 0x836E reads 16B: U32 location_id, U16 x, U16 y, 8B status.
    """
    combat = session.combat
    if combat:
        won = combat.players_won()
        # Send BTL_END_REQUEST (0x01EB): 2B end status
        await session.send_msg(MSG_BTL_END_REQUEST, combat.build_btl_end_request(won))
        await asyncio.sleep(0.05)
        # Send BTL_END_REPLY (0x02F4): 16B position restore
        char = session.char
        if char:
            await session.send_msg(MSG_BTL_END_REPLY, combat.build_btl_end_reply(char))
        session.combat = None
    else:
        await session.send_msg(MSG_BTL_END_REQUEST, struct.pack('>H', 0))


async def h_cancel_encount(session, msg_type, payload, param1):
    """0x01E3 -> CANCEL_ENCOUNT_REQUEST (0x01E4). Cancel encounter."""
    session.combat = None
    await session.send_msg(MSG_CANCEL_ENCOUNT_REQ, struct.pack('>H', 0))


async def _end_battle(session, combat):
    """
    Handle battle end: distribute rewards, update DB, send results + gold.
    Does NOT send BTL_END_REQUEST (0x01EB) — that's sent by h_btl_end
    when the client sends 0x01EA after processing the results display.

    Sequence (binary evidence):
    1. Server sends BTL_RESULT_NOTICE (0x0227) — 44+N*56B per combatant
    2. Server sends BTL_GOLD_NOTICE (0x01C8) — 12B header + groups
    3. Client sends 0x01EA when done processing → h_btl_end sends 0x01EB + 0x02F4
    """
    won = combat.players_won()
    combat.state = CombatState.BATTLE_END

    if won:
        total_exp, total_gold, drops = combat.calc_rewards()
        char = session.char
        if char:
            char.experience += total_exp
            char.gold += total_gold
            log.info("[S%d] Battle won: +%d EXP, +%d gold, %d drops",
                     session.sid, total_exp, total_gold, len(drops))

            # Add dropped items to inventory
            for item_id in drops:
                from .game_data import get_item_data_blob, ITEMS
                item_def = ITEMS.get(item_id)
                if item_def:
                    session.db.add_item(
                        char.char_id, item_id,
                        get_item_data_blob(item_id),
                        item_def.type_a, item_def.type_b,
                        item_def.equip_slot, item_def.price
                    )

            # Restore player HP/MP to current combat values
            player_ent = next((e for e in combat.entities if e.is_player), None)
            if player_ent:
                char.current_stats[0] = player_ent.hp
                char.current_stats[1] = player_ent.mp

            session.db.save_character(char)

    # 1. Send BTL_RESULT_NOTICE (0x0227): 44B header + N*56B per combatant
    await session.send_msg(MSG_BTL_RESULT_NOTICE, combat.build_btl_result_notice())
    await asyncio.sleep(0.1)

    # 2. Send BTL_GOLD_NOTICE (0x01C8): 12B header + 1 group (player)
    #    Binary evidence: handler at 0x83E4 reads gold_total, groups, items
    await session.send_msg(MSG_BTL_GOLD_NOTICE, combat.build_btl_gold_notice())
    # NOTE: Do NOT send 0x01EB here. Wait for client 0x01EA → h_btl_end.
