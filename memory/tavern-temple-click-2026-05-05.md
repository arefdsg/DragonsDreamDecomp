---
name: Tavern Temple click — 2026-05-05 log analysis
description: Data-driven analysis of the user's "click Temple in tavern menu" session. Shows the click reaches us as a generic 0x019A and routes through the broken 2nd-zone-transition path.
type: project
---

# Tavern "Temple" button click — what actually happens

## Log: dd_server_20260505_130249.log

User clicked "Temple" from the tavern menu (4 buttons: Tables, Temple, Settings, Exit). Reconstructed timeline:

| Time | Event | Source |
|------|-------|--------|
| 13:06:47.097 | 0x019A (LOGOUT) | Client auto — post-login destination request |
| 13:06:47.397 | 0x019C dest_id=4 | Client picked Cave Dungeon |
| 13:06:47-51 | Cycle 1 zone transition | Server sent 0x019D+0x02EF+establish+ESP+UPDATE |
| 13:06:51.928 | 0xA6 status flags=0x34 | Client ACKed establishment |
| 13:06:52.209 | 0x019A (auto re-request) | Client auto post-zone-load |
| 13:06:58.524 | 0x026F (2B `0000`) | Client auto — tavern entry handshake |
| 13:06:58.806 | 0x0271 (16B all zero) | Client auto — handshake follow-up (282ms after 0x026F) |
| **13:07:01.714** | **0x019A (2B `0000`)** | **HUMAN CLICK on Temple button (3.2s after handshake)** |
| 13:07:14.050 | 0x019C dest_id=5 | Client picked Dark Tower from server's GOTOLIST |
| 13:07:14-16 | Cycle 2 zone transition | Server sent 0x019D+0x02EF+establish+ESP+UPDATE |
| 13:07:16.596 | 0xA6 status flags=0x34 | Client ACKed establishment |
| 13:07:16.596 onward | TOTAL CLIENT SILENCE | Cycle 2 freeze (documented 30+ times) |

## What "click Temple" actually sends — `0x019A`

The 0x019A payload is **2 bytes `0000`** — exactly the same as the auto-sent post-login 0x019A. **The wire format gives no information about which button was clicked.** All 4 tavern menu buttons (Tables, Temple, Settings, Exit) likely send the same 0x019A.

Our `h_logout` handler always responds with `0x019B` (GOTOLIST destinations: Cave Dungeon, Forest, Dark Tower). The user then sees a destinations list. They picked dest_id=5 (Dark Tower) — which the user perceived as "Temple" in their interpretation.

## Two problems compound here

### Problem 1: GOTOLIST is missing "Temple" zone
ZONES (game_data.py) has: Starting Town, Plains, Forest, Cave Dungeon, Dark Tower, Dragon's Peak, Abyss, Market Town, Capital City. **No Temple.** If the production game has a Temple destination in the GOTOLIST, we need to add it as a zone.

### Problem 2: Cycle 2 zone transition is broken (THE blocker)
The user's cycle 2 (tavern → Dark Tower) hits the documented freeze at 13:07:16.596. The server sent the standard sequence (0x019D, 0x02EF, session establishment, ESP, UPDATE) but the client only ACKed the 256-byte establishment (0xA6 flags=0x34) and then went permanently silent.

Per `gotolist-flow.md`, this 2nd-cycle freeze has been tested ~30+ times with various message orderings, timings, payload variations, and dest_index values. **None worked.**

The closest approach (Test 31, log 113500) had cycle 1 work + cycle 2 fail. Test 31 log 2 (113836) had cycles 1-2 work + cycle 3 fail. Each successive cycle regresses, indicating accumulated state corruption in the client's session machinery.

## SBL FID matching — confirmed will not solve this

Earlier in this session we verified DD uses **SBL 2.11** (1996-03-21). CyberWarriorX's public sigs cover **SBL 6.0/6.0.1** (Nov 1996+) and SGL 2.0a/2.1/3.00/3.02j. FLIRT pattern matching across versions returns ~0 hits (1/1539 last attempted).

Even if FIDs matched, the affected functions (`game_world_sm`, `gate function`, `init_zone_transition`, GOTOLIST state machine at file 0x00DFB0) are all **DD game code** in the 0x0603xxxx range — not SBL library code. SBL FIDs would only name SBL helpers (PER_, SCL_, GFS_, etc.), not the game logic where the freeze lives.

## Honest verdict

This freeze has now resisted:
- 30+ documented hardware test variations (gotolist-flow.md)
- 4 separate sessions of static binary reverse-engineering
- Multiple binary patches (state-259 patch, FUN_06030CEC gate-bypass)
- SBL 6.0 source comparison (NOV96 DTS CD)
- Server-side message reordering, timing, and payload variations
- The user has firmly rejected: emulator-based debugging, binary patches as final fix

Without runtime memory inspection (Mednafen + tcpser bridge, or live Saturn debug), the static evidence is exhausted. The next-most-promising path I can suggest is **a different test angle**: if cycles 1 & 2 work for some ZONE PAIRS but not others (e.g., Cave→Dark Tower fails, Cave→Forest works?), there's a per-zone bug we can characterize. Test plan would be:
- Cycle 1: pick zone A (Cave). Document outcome.
- Cycle 2: pick zone B. Try every B systematically. Find which combinations work.

This narrows the bug to specific zone-pair state mismatches.
