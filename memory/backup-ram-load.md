# backup_ram_load (0x06010710) — BRAM Save File Loading

## Overview
Loads 3 BRAM (battery-backed RAM) save files from Saturn internal storage into session_ctx.
Called from init_zone_transition (step 28) and boot sequence.

## Three BRAM Files
| Filename | Blocks | Destination | Size (bytes) |
|----------|--------|-------------|-------------|
| DRGNSDRMLST | 44 | session_ctx+0xDDFC | ~2816 |
| DRGNSDRMKWD | 22 | session_ctx+0xE8C0 | 0x534 (1332) |
| DRGNSDRMSYS | 9 | char data area | ~576 |
| **Total** | **75** | | |

## Execution Flow
1. Set g_state[0x01BE] = 1 (bram_loaded flag)
2. BUP_Init(0x202A2000, 0x202A6000) — init backup library
3. BUP_Dir for all 3 files — check existence
4. If any missing: check free space >= needed blocks (75 - existing)
5. Read each file via bram_read_LST/KWD/SYS wrappers
6. Return -5 (file not found) treated same as success

## Error Handling
- BUP_Init fail: sets error handler, returns -1
- Insufficient space: sets error handler, returns -1
- BUP_Read returns -5 (not found): **ACCEPTABLE** — continues to next file
- BUP_Read other error: sets specific error handler, returns -1

## Default Initialization (Fresh Saturn)
When a BRAM file doesn't exist, each read wrapper calls its defaults function:

### init_defaults_KWD (0x0603C03E) — CRITICAL
- Writes keyword entries from ROM table at 0x0605D824 to session_ctx+0xE8C0+83
- Writes 4 entries from 0x0605D9A4 to session_ctx+0xE8C0+3
- **DOES NOT write bytes 0, 1, or 2** of the KWD region
- Calls bram_save_KWD to persist defaults

### init_defaults_SYS (0x0603ABB4)
- Comprehensive reset: init char data, clear flags, set g_state[0x01B2]=2
- Calls backup_ram_save, then re-calls init_defaults_LST AND init_defaults_KWD

### init_defaults_LST (0x0603B404)
- Initializes server list region at session_ctx+0xDDFC

## Fresh Saturn Bootstrap Problem
**session_ctx[0xE8C2]** (gate flag) = KWD base + 2 (session_ctx+0xE8C0+2)

| Scenario | E8C2 Value | Reason |
|----------|-----------|--------|
| Fresh Saturn, no BRAM | **0** | init_defaults_KWD skips bytes 0-2 |
| Returning player, BRAM exists | **1** (from save) | memcpy restores from BRAM |
| After gate_set(0) | **0** | Explicit clear |
| After gate_set(1) | **1** | Written + saved to BRAM |

**Consequence**: On a truly fresh Saturn with no BRAM data, E8C2=0, and login_sm
ALWAYS fails the gate check. Online login is IMPOSSIBLE without pre-existing BRAM.

The game likely required offline character creation or a registration step to first
set E8C2=1 and save to BRAM before online mode worked.

## Success Path
After all 3 files loaded/initialized:
1. Call reinit_handler_table (0x06024622)
2. Copy 16 bytes from active char slot to g_state+12 (character name)
3. Clear g_state[0x1C] = 0
4. Return 0

## Key Addresses
| Address | Description |
|---------|-------------|
| 0x06010710 | backup_ram_load entry |
| 0x0603AE3E | bram_read_LST |
| 0x0603AF54 | bram_read_KWD |
| 0x0603ABEC | bram_read_SYS |
| 0x0603C03E | init_defaults_KWD |
| 0x0603ABB4 | init_defaults_SYS |
| 0x0603B404 | init_defaults_LST |
| 0x0605F42A | g_state[0x01BE] — bram_loaded flag |
| 0x0604BFCC | "DRGNSDRMLST" filename struct |
| 0x0604BFD8 | "DRGNSDRMKWD" filename struct |
| 0x0604BFE4 | "DRGNSDRMSYS" filename struct |
