# Zone-pair test matrix — cycle-2 freeze isolation

## STATUS — most of the originally-proposed matrix is REDUNDANT

Per `memory/gotolist-flow.md` (~50 documented hardware tests covering Tests 1–55+),
nearly all `dest_index` permutations and `server_info` configurations have already
been tested. The matrix below is annotated with prior outcomes so we don't burn
hardware cycles on duplicates.

## What has already been tested (and failed)

| Configuration | Test ID | Log | Outcome |
|---|---|---|---|
| cycle 1 dest_index=4, cycle 2 dest_index=4 (current default) | many | 20260505_130249 + others | FREEZE on cycle 2 |
| cycle 1=4, cycle 2 dest_index=5 (user clicked Dark Tower) | original "success" 200832 | 20260405_200832 (lines 370-380) | "ack then silence" |
| cycle 1=4, cycle 2 dest_index=6 (Dragon's Peak) | Test 22 attempt 2 | 20260406_175850 | cycles 1-2 work, **cycle 3 fails** |
| cycle 1=4, cycle 2 dest_index=7 (Abyss) | Test 22 attempt 1 | 20260406_175446 / 20260406_182832 | black screen 84s |
| cycle 1=4, cycle 2 dest_index=1 | Tests 16, 28, 29, 30 | various | BLACK SCREEN |
| **server_info=[4,4,4]** (force all matches) | Tests 41, 49, 54, 55 | various | post-tavern HANG (cycle 2 actually works!) |
| server_info=[1,3,4] (other forced) | Test 52 | — | post-tavern HANG |
| server_info=[4,3,4] (mixed forced) | Test 53 | — | post-tavern HANG |
| Skip 0x02EF on cycle 2, send only 0x019D | Test 47 | 20260408_064558 | client permanent hang |
| Skip 0x019D on cycle 2 | Test 24 | 20260406_192541 | client sends LOGOUT (0x019A) instead of 0x019E |

**Most-instructive prior result**: Tests 41/49 with `server_info=[4,4,4]` produced
**post-tavern HANG, not cycle-2 freeze** — meaning cycle 2 actually advanced. The
follow-on hang is the tavern table list / sit issue (separate bug). This is the
strongest evidence that **server_info matching zone_cd_id is the right approach** —
it makes the client send `0x026F` (game world re-entry) instead of `0x019C`
(zone transition) when the user clicks an entry on cycle 2+.

## What has NOT been tested (genuinely novel)

After grepping `gotolist-flow.md` exhaustively, the following remain untested:

1. **cycle 1 dest_index=4, cycle 2 dest_index=3 (Forest specifically)**
   - dest_index 1, 4, 5, 6, 7 all tested — `3` is missing.
   - Configurable via: `DD_DEST_INDEX_MAP="1:4,2:3"` in admin GUI

2. **server_info=[4,4,4] + ALSO drop the 2nd 0x02EF + DON'T re-establish** (combination)
   - Tests 41/49 set server_info=[4,4,4] but kept sending 0x02EF and re-establishing.
   - If the client's `0x019C` is destined for game world re-entry (not transition),
     sending 0x019D + 0x02EF + re-establish may be over-driving the SM.
   - Untested: si=[4,4,4] + cycle 2 sends ONLY 0x019D (no 0x02EF, no establish, no ESP).

3. **Force-disconnect on cycle 2** (let client reconnect fresh)
   - Hardware never tested. Would simulate "session ran out, log in again".
   - Untested whether the Saturn cleanly re-dials and recovers.

4. **0x019B (re-send GOTOLIST) as response to cycle 2 0x019C** instead of 0x019D
   - Hypothesis: tells client "your selection is invalid, pick again"
   - Untested.

## Updated test plan — only the truly novel tests

| # | Approach | DD env / handler change | Hypothesis |
|---|---|---|---|
| N1 | cycle 2 dest_index=3 explicit | `DD_DEST_INDEX_MAP="1:4,2:3"` | Untested gap in Phase 1 |
| N2 | si=[4,4,4] + skip 0x02EF on cycle 2 | (server code change) | Combine known-good si fix with no-transition cycle 2 |
| N3 | si=[4,4,4] + force TCP disconnect on cycle 2 | (server code change) | Force fresh re-dial, possibly bypassing SV state corruption |
| N4 | Re-send 0x019B instead of 0x019D on cycle 2 | (server code change) | Make client re-render GOTOLIST |

## Configurable knobs

`DD_DEST_INDEX_MAP="cycle:value,cycle:value,..."` overrides dest_index per cycle.
Special value `dest_id` means "use the user's actual selection".

Examples:
```bash
unset DD_DEST_INDEX_MAP                  # Production default (always 4)
export DD_DEST_INDEX_MAP="1:4,2:3"       # Test N1 — cycle 2 dest_index=3
export DD_DEST_INDEX_MAP="1:4,2:dest_id" # cycle 2 dest_index = user's pick
```

Server log prints `[OVERRIDE via DD_DEST_INDEX_MAP]` when active.

## How to run

Use the **Admin GUI → Zone Test tab** for one-click testing. Select a row, click
APPLY & START SERVER, follow the popup's user actions on Saturn, then mark the
outcome (OK / FREEZE / OTHER). Outcomes auto-append to this file.

## Outcomes log
<!-- Auto-appended by admin_gui Zone Test tab -->
