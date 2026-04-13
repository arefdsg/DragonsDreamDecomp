# ESP_NOTICE (0x01E8) Handler Analysis

## Location
- Handler table entry #12
- Handler address: 0x06013F1C (file offset 0x003F1C)
- Function size: 258 bytes (0x06013F1C to 0x0601401C)

## What It Does
Pure data-unpacking + initialization function. Stores server ESP data into session_ctx, resets state counters, and sets init flags.

## What It Does NOT Do
- Does NOT write gate flags (session_ctx[0xDDFE] or session_ctx[0xE8C2])
- Does NOT call gate_set() at 0x0603B488
- Does NOT modify g_state[0x01AD] (game state variable)
- Does NOT trigger any state machine transitions directly

## Payload Format (51 bytes)
| Offset | Size | Destination (session_ctx +) | Notes |
|--------|------|-----------------------------|-------|
| 0 | 2 | 0x0004 | u16 BE |
| 2 | 2 | 0x0264 | u16 BE |
| 4 | 2 | 0x00A2 | u16 BE |
| 6 | 1 | 0x00A4 | byte |
| 7 | 1 | 0x00A5 | byte |
| 8 | 4 | 0x0094 | u32 BE |
| 12 | 16 | 0x00A6..0x00B5 | memcpy (server name?) |
| 28 | 12 | 0x7C88..0x7C93 | memcpy |
| 40 | 1 | 0x7C95 | byte |
| 41 | 1 | 0x7C96 | byte |
| 42 | 1 | 0x7C97 | byte |
| 43 | 1 | 0x7C98 | **stored as value - 1** |
| 44-50 | 1 each | 0x7C99..0x7C9F | bytes |

## State Clears (zeroed by handler)
- session_ctx[0xB6] = 0
- session_ctx[0x7C94] = 0
- session_ctx[0xAB14] = 0, [0xAB15] = 0
- session_ctx[0xAD48] = 0 (word)
- session_ctx[0xD044] = 0 (long)
- **session_ctx[0xABA4] = 0** (event queue read index)
- **session_ctx[0xABA5] = 0** (event queue write index)
- session_ctx[0x6F88] = 0 (word)
- session_ctx[0xF4B4] = 0
- session_ctx[0x0006] = 0 (paired completion tracker)
- g_state[0x01C6] = 0

## Init Flags Set (all set to 1)
| Flag | Auto-sends | Description |
|------|------------|-------------|
| session_ctx[0x8E] | 0x0048 (STANDARD_REPLY) | First deferred send |
| session_ctx[0x8F] | 0x025F (PARTY_BREAKUP_NOTICE) | Second deferred send |
| session_ctx[0x90] | 0x02D4 (CMD_BLOCK_REPLY) | Third deferred send |
| session_ctx[0x91] | 0x006D (SYSTEM_NOTICE) | Fourth deferred send |

## Critical Implications
1. **Event queue wipe**: Clears ABA4/ABA5 — any queued events (e.g., from 0x02EF) are LOST
2. **Must send ESP_NOTICE BEFORE 0x02EF** during GOTOLIST re-login, not after
3. **Init flags trigger auto-sends**: Client sends 4 messages back to server automatically
4. **Paired tracker reset**: session_ctx[6]=0 — ready for new paired message tracking
