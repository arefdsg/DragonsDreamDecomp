# init_zone_transition (0x06010554)

Full game initialization/reset function. Called during boot, zone transitions, disconnect, and reconnection.

## Callers
| Address | Context |
|---------|---------|
| 0x0601003E | Boot startup |
| 0x06010A06 | Zone transition (CD subsystem) |
| 0x06010C5C | Disconnect handler |
| 0x060200DE | Connection reinit |

## Execution Sequence (verified from binary)

### Registers
- R14 = 0 (constant zero)
- R12 = 1 (constant one)
- R13 = session_ctx (0x202CB000 from GBR[2])

### Operations in Order
1. Clear 4 global bytes at g_state+0x1CF8..0x1D03
2. Set g_state[0x01AC] = 1
3. Clear g_state+0x1ADC..0x1ADF
4. **CALL SV_Init (0x0602219E)** — resets SV network layer
5. CALL func_00F8 (0x060200F8)
6. Clear 32-bit globals at g_state+0x1C18, 0x1C1C
7. Set g_state[0x01BD] = 1, clear g_state[0x01B8]
8. Clear g_state: 0x01B1, 0x0008, 0x01A7..0x01AB
9. Clear session_ctx: 0xDDFE, 0xDE00, 0xDE01, 0x12D74
10. Clear g_state: 0x2094, 0x017E, 0x017F, 0x0181, 0x0183
11. Clear session_ctx[0x0000] (32-bit)
12. Clear session_ctx[0x008B], [0x008C]
13. **Set init flags: session_ctx[0x008E]=1, [0x008F]=1, [0x0090]=1, [0x0091]=1**
14. CALL scmd_func_430C, scmd_func_4384, scmd_func_43EC
15. CALL func_63CC(1), func_042C
16. Clear session_ctx[0x1C0E]
17. Set session_ctx[0x1E7D]=1, [0x1E7A]=1
18. Set session_ctx[0x1B90]=0, [0x1B91]=0xFF
19. CALL func_B8C4(0)
20. **Set g_state[0x01AD] = 0** (clear high-level game state)
21. **Set g_state[0x01BC] = 1**
22. **CALL gate_set(0)** → clears session_ctx[0xDDFE]=0 AND [0xE8C2]=0
23. CALL func_B4CC(0)
24. Set *0x06060F6C = 1
25. **Clear g_state[0x01B4] = 0** (event handler fptr)
26. **Clear session_ctx[0xABA5]=0, [0xABA4]=0** (event queue indices)
27. **Set session_ctx[0xABAB] = 1** (event handler enable flag)
28. **CALL backup_ram_load (0x06010710)** — loads all 3 BRAM files
29. Return

## Key Effects
- g_state[0x01AD] = 0 (neither login nor game_world)
- Both gate flags cleared by gate_set(0), BUT may be overwritten by BRAM load (#28)
- Init flags [0x8E-0x91] pre-set to 1 (deferred sends ready without ESP_NOTICE)
- SV connection RESET by SV_Init — requires server re-establishment
- Event queue cleared, handler enable flag set
- g_state[0x01BD] = 1 (enables SV_Poll in main loop Phase 2)

## BRAM Overwrite Issue
gate_set(0) at step #22 clears DDFE=0 and E8C2=0.
backup_ram_load at step #28 loads session_ctx+0xDDFC and +0xE8C0 from BRAM.
If BRAM contains saved flags with DDFE=1 or E8C2=1, they OVERWRITE the zeros.
This means a returning player's gate flags are determined by BRAM, not by gate_set(0).
