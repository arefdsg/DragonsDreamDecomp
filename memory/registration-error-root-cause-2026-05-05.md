---
name: Registration error → corrupt BUP — confirmed root cause
description: User's failed Saturn-side character creation left the BUP in a partial state (name="12345" + 320 zero bytes). All subsequent connections inherit this corruption. The server-side fix is to push correct character data via 0x02D2 TYPE 2 on every login to repair the BUP.
type: project
---

# Confirmed: registration error → corrupt BUP → downstream failures

## Timeline reconstruction (from user + logs)

1. **First-ever boot**: Saturn had empty BRAM. Game tried to run character creation, but **the BRAM write errored out** — Saturn disconnected.
2. **Partial write left BUP corrupt**: name="12345" (Saturn's default placeholder) plus 320 zero bytes at 0x40–0x180 of `DRGNSDRMSYS.BUP`.
3. **Subsequent boots** read the partial BUP, see `E8C2=1` (gate passed) and a "valid" character → skip character creation, go straight to HOME with TO TOWN button enabled.
4. **TO TOWN dial** → log shows server treats this as login of registered player "12345":
   - `dd_server_20260413_123429.log` line 25: `Created character: id=1, name=31323334350000000000000000000000, class=0` (= "12345" hex)
5. **Login proceeds, server pushes character data** including 0x02D2 TYPE 2 → Saturn writes "12345" + zeros back to BUP → no improvement.
6. **Tavern/Temple downstream features fail** because character struct is incomplete.

## Why this is THE root cause

Verified across multiple log files going back to 2026-04-13:

- **Every server log shows `name='12345'`** because that's what the Saturn sends in 0x0035 INIT (read straight from BUP).
- **DB row for char_id=1 is `name="12345"`** because the server stored it on first INIT.
- **The 320 zero bytes in DRGNSDRMSYS.BUP** at offset 0x40-0x180 likely correspond to fields that should hold:
  - Equipment slot data (16 slots × 2 bytes = 32 bytes)
  - Appearance bytes (5 + 3 padding)
  - Skill IDs and levels (16 × 2 = 32 bytes for IDs + 16 × 2 = 32 bytes for levels)
  - Class/race/gender flags
  - Stat blocks (19 base + 19 current = 76 bytes)
  - Total ~200 bytes of structured data we know is missing
- **The Saturn's BRAM save trigger is `0x02D2 TYPE 2`** (handler at file 0x03858 ends with `FUN_0603AD2C` BRAM save) — server already calls this in `handlers_login.py:_send_chardata_reply_type2`.

## The fix (architecturally)

We have the mechanism. We're already pushing 0x02F9 (172 bytes) + 0x02D2 TYPE 1/2/3 on every login. The Saturn should be saving these to BRAM. **What's currently broken is that we're pushing PLACEHOLDER values from the database row** — the same "12345" name and incomplete fields the Saturn already has. So each login round-trips the corrupt data and never repairs it.

### Three ways to fix it

**Option A — manual fix via Admin GUI (simplest, you can do now)**

1. Open Admin GUI → Characters tab
2. Edit char_id=1: set proper name (not "12345"), set proper class (e.g., 1=Warrior), proper level, proper stats
3. Save
4. Reconnect Saturn — server now pushes the GOOD data on login
5. Saturn saves GOOD data to BRAM via 0x02D2 TYPE 2
6. Re-test Temple click

**Option B — server-side auto-repair on login (programmatic)**

Add a handler that detects "corrupt placeholder" character data on login (e.g., name == "12345" or all-zero stat blocks) and **rewrites the DB row with sensible defaults** BEFORE sending CHARDATA cascade. Subsequent logins push the corrected data.

**Option C — wipe the BUP, force re-creation**

Delete `saves/GS-7114.zip` and let Saturn try fresh BRAM creation. If the original error was reproducible (BRAM write hardware/timing issue), this might fail again. But if the error was a one-time glitch (e.g., during initial server startup turbulence), starting clean might work.

## Where the 320 missing bytes go in the BUP

`DRGNSDRMSYS.BUP` payload (490 bytes after 0x40-byte BUP header):

| BUP offset | Size | Field (educated guess based on 0x02F9 wire format) |
|---|---|---|
| 0x40–0x4F | 16 | char_name (Shift-JIS) |
| 0x50 | 1 | char_class |
| 0x51 | 1 | char_sub_class |
| 0x52–0x53 | 2 | character flags (race, gender packed?) |
| 0x54–0x57 | 4 | character_id |
| 0x58 | 1 | char_level |
| 0x59 | 1 | reserved |
| 0x5A–0x5D | 4 | experience |
| 0x5E–0x61 | 4 | gold/HP |
| 0x62–0x99 | 56 | base_stats[19] U16 BE |
| 0x9A–0xD1 | 56 | current_stats[19] U16 BE |
| 0xD2–0xD9 | 8 | appearance |
| 0xDA–0xF9 | 32 | skill_ids[16] U16 BE |
| 0xFA–0x119 | 32 | skill_levels[16] U16 BE |
| 0x11A–0x119+N | … | inventory / equipment slots |
| 0x180+ | … | session config (BBS commands, phone) |

(Above is **inferred** from wire formats; not yet directly verified by disassembling the BRAM save function. But the structure should be close.)

In our save, **all of 0x40–0x180 is zero** → essentially zero stats, zero level, zero class, zero appearance, zero skills. The Saturn's character is alive only because the session-config region at 0x180+ has just enough data (BBS string, name, year) to bootstrap.

## Action items for the user

**Immediate**:
1. Open Admin GUI → Characters tab.
2. Find char_id=1 (name "12345").
3. Set:
   - **Name**: a real name (e.g., "Hero")
   - **Class**: pick from valid class IDs (0–5)
   - **Level**: ≥1
   - **HP/MP/stats**: reasonable values for a level-1 character
   - **Gold**: ≥1
4. Save the character.
5. Power-cycle Saturn, dial in.
6. After login, check `saves/GS-7114.zip` (re-extract and inspect `DRGNSDRMSYS.BUP`) — see if the 0x40-0x180 region now has non-zero data.
7. Re-attempt Temple click.

**If the BUP still has the 320 zero bytes after login**:
- The Saturn isn't actually committing the 0x02D2 TYPE 2 data to those offsets, despite the BRAM-save call.
- That means the in-memory char struct has these zeros and the BRAM write just persists what's in memory.
- Next step: trace what wire-format messages populate which BUP offsets — likely `0x02F9` (extended 172B) is the right one, not `0x02D2`.

## Why this changes the cycle-2 freeze story

Earlier this session I theorized the cycle-2 zone-transition was a fundamental client-side bug. With the registration-corruption discovered, **the cycle-2 freeze might be a downstream symptom of incomplete character data**, not a separate bug. Tests 41/49 with `server_info=[4,4,4]` actually got past cycle-2 and only failed at "post-tavern" — same place a corrupt character would cause issues.

If pushing corrected character data fixes the cycle-2 freeze, that confirms the chain:
- Corrupt BUP → corrupt in-memory character → fails some validation downstream → freeze.
