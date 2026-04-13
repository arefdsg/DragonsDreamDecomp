# Bomberman US H2HLIBUS.BIN LED Patch

## Overview
Patched Saturn Bomberman US `H2HLIBUS.BIN` to blink NetLink modem LED during online gameplay.
Japanese XBAND games have this; American NetLink games do not.

## Key Facts (CONFIRMED)
- **H2HLIBUS.BIN**: 8,850 bytes, load base **0x06002F80**
- **Identical across ALL US NetLink games** -- same binary in every title
- **Dispatch table**: 31 x 4-byte entries at file 0x00-0x7B
- **Entry 7 = XBExchangeGameData** -- PRESERVED by XBAND init, called every frame
- **Entry 23 = XBVBLTask** -- OVERWRITTEN by XBAND.BIN init
- **CRITICAL: dispatch[23] VALUE must NOT change** -- causes freeze (v5/v6/v7)
- **CRITICAL: literal pool at 0x131C must NOT change** -- breaks data exchange (v8)
- **CRITICAL: code at 0x15B4 must handle dispatch[23] calls** -- crash if BRA elsewhere (v9)
- **CRITICAL: XBAND.BIN overwrites CODE at 0x12A2** -- code hooks get erased (v10)
- **File 0x1934-0x193F**: 12 bytes zeroed, safe for data storage
- **File 0x15B4-0x15C7**: init stub, dead after XBAND init, safe for code

## Patch v12 -- CURRENT (2026-03-20)
**Solid LED ON via dispatch[23] init, 22 bytes modified**

### Design
Replace init stub body with direct write of 0x80 to board ctrl register.
LED turns ON during XBAND init, stays ON permanently (register retains state).

### 2 Patch Locations (22 bytes total)
| # | File Offset | Size | Description |
|---|-------------|------|-------------|
| 1 | 0x15B4 | 20B | MOV #0x80,R1 + MOV.L bctrl,R0 + MOV.B + NOP pad + RTS |
| 2 | 0x1938 | 4B | Board ctrl literal (0x25885031) in dead zone |

### Flow
1. XBAND init calls dispatch[23] -> 0x15B4
2. Write 0x80 to 0x25885031 (LED ON)
3. RTS + pop R14 (return to XBAND init)
4. XBAND.BIN overwrites dispatch[23] -> LED stays ON permanently

## All Failed Approaches
1. **v1 BSS injection**: zeroed at runtime
2. **v2 file extension**: patcher can't use larger files
3. **30Hz XOR toggle**: perceived as solid light
4. **Dispatch[23]-only counter**: init runs once
5. **NULL dispatch[23] + VBL BRA**: crash
6. **v3 VBL prologue hook**: LED at title only; crash on disconnect
7. **Init stub RTS only**: missing byte-writes
8. **v4 dispatch[23] counter**: dead after XBAND overwrite
9. **v5 dispatch[7] wrapper**: crash (BRA not RTS)
10. **v5-fix**: dispatch[23] changed -> freeze
11. **v6**: dispatch[23] changed -> freeze
12. **v7**: dispatch[23] changed + R0 clobbered -> freeze
13. **v8**: literal pool 0x131C changed -> broke data exchange
14. **v9**: wrapper at 0x15B4 BRA 0x12A6 -> dispatch[23] crash
15. **v10**: BRA hook at 0x12A2 overwritten by XBAND.BIN -> LED never lit
16. **v11**: dispatch[7] redirect -> game won't load challenge screen

## Files
- **Git repo**: `D:\NetlinkLEDPatch`
- **Patch script**: `D:\NetlinkLEDPatch\patch_led.py`
- **Original SHA-256**: 7d988e45bb18b58e0dcbe713eb1c7b3694de2eca80ecaf77357c797c12971eb6
- **Patched v12 SHA-256**: 4e3560b5d6fe33a0c9faba147f63107305e954fc8af6cdde091491e6dc1d3661
