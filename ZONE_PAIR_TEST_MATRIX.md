# Zone-pair test matrix — cycle-2 freeze isolation

Purpose: systematically test which combinations of cycle-1-destination + cycle-2-destination + dest_index values cause the documented cycle-2 freeze, and which (if any) succeed. Comparing the wire traffic of a working pair against a failing pair would isolate the bug.

## Background

User starts at zone 4 (Cave Dungeon). Zone connections:
- Zone 4 → [3, 5] (Forest, Dark Tower)
- Zone 3 → [2, 4, 5]
- Zone 5 → [4, 6]

GOTOLIST always shows current zone + connections, e.g. starting in zone 4: destinations = [4, 3, 5].

## Configurable knob

The server now reads `DD_DEST_INDEX_MAP` env var to override `dest_index` per cycle:

```
DD_DEST_INDEX_MAP="cycle:value,cycle:value,..."
```

Special value `dest_id` means "use the user's actual selection".

Examples:
```bash
# Production default (always 4):
unset DD_DEST_INDEX_MAP

# Test A: cycle 1 dest_index=4, cycle 2 dest_index=3 (try dest 3 instead of 4)
export DD_DEST_INDEX_MAP="1:4,2:3"

# Test B: cycle 2 dest_index matches user's pick:
export DD_DEST_INDEX_MAP="1:4,2:dest_id"

# Test C: try unrelated index value:
export DD_DEST_INDEX_MAP="1:4,2:7"
```

Server log will contain `[OVERRIDE via DD_DEST_INDEX_MAP]` when active.

## Test plan

For each test:
1. Set `DD_DEST_INDEX_MAP` per the table below
2. Start server (`python -m dragons_dream_server_v4 --port 8020`)
3. Power-cycle Saturn, dial in
4. Cycle 1: from main game, navigate to and select destination per "cycle 1 click"
5. Cycle 2: from new zone's tavern, click destination per "cycle 2 click"
6. Wait 30s. Record outcome:
   - **OK**: client enters new zone, sends post-zone messages (0x019A, etc.)
   - **FREEZE**: client ACKs 256B establishment then total silence
   - **OTHER**: any other behavior — record details
7. Save log file with test ID (e.g., `log-renamed-test1.log`)

## Test matrix

Currently broken default (Test 0) for reference:
| # | cycle 1 click | cycle 2 click | DD_DEST_INDEX_MAP | Expected | Observed |
|---|---|---|---|---|---|
| 0 | (any) | (any, e.g. dest_id=5 Dark Tower) | unset (default `1:4,2:4`) | FREEZE (known) | FREEZE — log 20260505_130249 ✓ |

### Phase 1: vary cycle 2 dest_index (cycle 1 fixed at 4)

| # | cycle 1 click | cycle 2 click | DD_DEST_INDEX_MAP | Observed |
|---|---|---|---|---|
| 1a | dest_id=4 (Cave) | dest_id=3 (Forest) | `1:4,2:3` | _(record)_ |
| 1b | dest_id=4 (Cave) | dest_id=3 (Forest) | `1:4,2:dest_id` | _(record)_ |
| 1c | dest_id=4 (Cave) | dest_id=5 (Dark Tower) | `1:4,2:5` | _(record)_ |
| 1d | dest_id=4 (Cave) | dest_id=5 (Dark Tower) | `1:4,2:dest_id` | _(record)_ |
| 1e | dest_id=4 (Cave) | dest_id=4 (back to self) | `1:4,2:4` | _(record — should match Test 0)_ |

### Phase 2: vary cycle 1 (run only if Phase 1 reveals a working combination)

| # | cycle 1 click | cycle 2 click | DD_DEST_INDEX_MAP | Observed |
|---|---|---|---|---|
| 2a | dest_id=3 (Forest) | dest_id=4 (Cave) | `1:3,2:4` | _(record)_ |
| 2b | dest_id=3 (Forest) | dest_id=4 (Cave) | `1:3,2:dest_id` | _(record)_ |
| 2c | dest_id=5 (Dark) | dest_id=4 (Cave) | `1:5,2:4` | _(record)_ |
| 2d | dest_id=5 (Dark) | dest_id=4 (Cave) | `1:5,2:dest_id` | _(record)_ |

### Phase 3: zone-id stays vs. updates (only run after Phases 1-2)

If any pair from Phase 1/2 succeeds, also test with zone_id update enabled (vs. current "stays") to see if that changes outcome.

## Analysis after each test

If a test succeeds (cycle 2 → user enters new zone):
1. **Compare logs**: diff the working test's wire traffic against Test 0 (the documented freeze).
2. **Identify the differentiator**: which message/payload byte changed between fail and success?
3. **Apply fix**: update server defaults to match the working pattern.
4. **Verify**: re-test with default config — should now work.

If all tests fail identically:
- The bug is NOT in `dest_index`. The test matrix has falsified that hypothesis.
- Consider next angle: zone_id update timing, message ordering, ESP payload content.

## Important notes

- **Power-cycle Saturn between tests** — cache invalidation matters per prior session findings.
- **Wait 30+ seconds** after cycle 2 click before declaring freeze (some patterns recover slowly).
- **Save logs with descriptive names** — diff-able across runs.
- **Run at least 2 attempts per test** — Saturn timing can vary.

## Where to log results

Append observations to this file's "Observed" column. After each phase, commit the updated matrix so progress is preserved.
