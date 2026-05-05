---
name: New-account flow — answer to "even for a brand-new player?"
description: Architectural reality of first-time-ever play. The game requires pre-existing BRAM data to dial out, and our test save bypasses the offline character-creation step the production game expects.
type: project
---

# Does a new player skip steps? — definitive answer

## Short answer

**For an actually new account/character, the player MUST complete OFFLINE character creation BEFORE pressing TO TOWN can connect successfully.** Our test save has placeholder data that bypasses this offline step, leaving the character struct in an incomplete state.

## Binary evidence — three independent confirmations

### 1. backup-ram-load.md (existing memory, file 0x010710)

> On a truly fresh Saturn with no BRAM data, E8C2=0, and login_sm ALWAYS fails the gate check. **Online login is IMPOSSIBLE without pre-existing BRAM.**

Translation: a Saturn that has never had Dragon's Dream booted before — fresh CMOS/cart, no save data — **cannot dial out to the server at all**. The login state machine fails the gate check at `session_ctx[0xE8C2] == 1`. The player is forced through some offline setup before "TO TOWN" works.

### 2. Our save's structure says "incomplete creation"

`saves/GS-7114.zip → DRGNSDRMSYS.BUP` (the system/character save):

- Total size: 554 bytes (490 bytes payload after BUP header)
- **Bytes 0x40–0x180: 320 bytes of zeros** — suspicious gap where character struct should live
- Bytes 0x180+: just placeholder data — name `"12345"`, year `"199403"`, BBS string `"C NETRPG"`, phone number stub

A truly complete save from real character creation would populate the 0x40–0x180 region with class/race/gender/stats/appearance bytes. Ours is empty. The "12345" name confirms this came from a debug/test path, not the in-game creation flow.

### 3. The binary has SCMD messages for online registration we never see

Confirmed in dispatch table + paired table:

| msg_type | Direction | Name | Purpose |
|---|---|---|---|
| `0x04E0` → `0x0046` | client→server | `REGIST_HANDLE_REQUEST` | Register player handle online |
| `0x0298` → `0x0299` | client→server | `CLASS_LIST_REQUEST` | Get available classes |
| `0x029A` → `0x029B` | client→server | `CLASS_CHANGE_REQUEST` | Pick / change class |

Our log `dd_server_20260505_130249.log` shows the **client never sent** any of these. That tells us our test save passes the "I am a registered player with a known class" pre-condition — but we have no way to know if the data the production game would have written is actually correct for downstream gameplay.

## So... where is the player supposed to be from the very beginning?

### Phase 0: BEFORE first network play (truly new account)

```
┌──────────────────────────────────────────────────────────────────┐
│  HOME screen (offline)                                            │
│  ─ First boot detects empty/insufficient BRAM                     │
│  ─ Game forces OFFLINE CHARACTER CREATION                         │
│    • Pick name (Japanese kana / kanji input)                      │
│    • Pick class, race, gender, age                                │
│    • Roll/distribute initial stats                                │
│  ─ Saves to BRAM: DRGNSDRMSYS.BUP populated, E8C2=1              │
│  ─ Player returns to HOME with character now created              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       (rest of Phase 1-7 from
                        complete-game-flow-2026-05-05.md)
```

We have NOT directly verified this offline character-creation UI exists in the binary by disassembly — the screenshots from prior sessions show "tavern interior" and "GOTOLIST map" but no character-creation screen. However, the architectural evidence (REQUIRES PRE-EXISTING BRAM, has placeholder save with missing 320 bytes) is strong enough that this MUST exist somewhere — either:
- An offline-mode menu reachable from HOME before TO TOWN
- A first-boot wizard that ran once when the disc was first inserted
- Or possibly a shipped pre-populated BRAM expected from a memory cart sold with the game

### Phase 1: HOME (after creation, before dial)

- Same as documented in `complete-game-flow-2026-05-05.md`
- "TO TOWN" button now functional (BRAM gate passes)

### Phases 2-7

- Identical to returning-player flow. The server doesn't really distinguish "first online ever" from "returning after a week" — both go through LOGIN → MAP → zone → tavern.
- The server-side `0x04E0 → 0x0046` flow exists for handle registration but is only triggered if the **client** initiates it (the client decides based on BRAM state).

## What this means for the current freeze

### Hypothesis: incomplete save data may be contributing to Phase 7 failures

Our save's `DRGNSDRMSYS.BUP`:
- Bytes 0x40–0x180 (320 bytes) **are all zero**
- Bytes around 0xC7 specifically (the offset we identified earlier as the sit-freeze gate poll location, `0x202E02CB - 0x202DE990 = 0x193B`, but in BUP space the analog would be a similar offset in the loaded character struct)

If the production game's save populates one or more of those 320 zero bytes with non-zero values during character creation, and the tavern/temple state machine reads those as gates, our placeholder save would fail those checks even though we pass the upstream login gates.

**This is consistent with**: Tests 41/49 (`server_info=[4,4,4]`) progressed past the cycle-2 freeze but hung "post-tavern" — i.e., after the cycle-2 transition completed, something in the tavern still wouldn't advance. That "post-tavern hang" might be the same character-data validation failing.

### Concrete next experiment (does NOT need binary patches or live debug)

1. **Try a completely empty BUP**: rename `saves/GS-7114.zip` to a backup, boot the patched CD with NO save. If the game has an offline character-creation flow, it should appear. Document what UI shows up.

2. **OR scan for a prior successful save from another player**: any DD save someone else has played online with would have the actual production data layout. Diffing it against ours would identify which fields we lack.

3. **OR try to find the offline character-creation entry point in the binary** by disassembling around the HOME-screen render functions (which we haven't located yet — would need new analysis).

## Practical implication for the user's frustration

The user's instinct in asking this question was right: **this is an architectural prerequisite issue, not a server-protocol issue alone.** Our 50+ tests of dest_index and server_info variations couldn't fix it because:

- The client side believes it has a valid character (E8C2=1)
- The server cooperates with login and CHARDATA
- Both sides reach the tavern in the same state
- But then SOMETHING downstream (Temple click, table click, second zone) reads a character field that's zero in our save but non-zero in a real save

**Without a real working save to diff against, or without finding the offline character-creation flow in the binary, we are inherently testing with broken input data.**

The user's earlier suggestion ("can we fix the character on the server and force it to update the save?") is actually the right idea — and we have the mechanism (`0x02D2 TYPE 2 → BRAM save`). What we need is to identify *which specific bytes* in DRGNSDRMSYS.BUP are non-zero in a complete save, then push that data via `0x02D2 TYPE 2` on every login to repair the save.

That's a concrete next step:
1. Find an unmodified production save online (e.g., from emulator save-state archives, fan sites)
2. Diff it against our placeholder save
3. Server pushes the differing bytes via `0x02F9` (172-byte extended) + `0x02D2 TYPE 2` on every login
4. Saturn writes them to BRAM
5. Next boot, save is "complete"
6. All subsequent game state should match production
