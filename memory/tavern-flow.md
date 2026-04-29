# Tavern (Sakaya) Flow — Complete Binary-Verified Documentation

## Date: 2026-04-10 (CORRECTED) | Source: SH-2 disassembly of extracted/0.BIN (base=0x06010000)

---

## Handler Dispatch Table (file 0x435D8, format: [msg_type:2][pad:2][handler:4])

**CRITICAL**: Previous analyses used WRONG table format ([handler:4][msg_type:2][pad:2] at 0x435DC).
The CORRECT format is [msg_type:2][pad:2][handler:4] starting at file 0x435D8.

| Entry | msg_type | Handler Addr | File | Description |
|-------|----------|-------------|------|-------------|
| 28 | 0x0270 | 0x06014AF4 | 0x04AF4 | STORE_ENTER — game world entry ack |
| 29 | 0x0272 | 0x06014BFE | 0x04BFE | STORE_IN — reads status, if 0: writes store_flag to ctx+0xA0 |
| 31 | 0x020D | 0x06014C3A | 0x04C3A | Seat list: 12 slots (22B each at ctx+0x6C94) |
| 35 | 0x0217 | 0x06014E7E | 0x04E7E | Tavern entry ack |
| 38 | 0x021C | 0x06014EC2 | 0x04EC2 | User list (RTS stub — no-op) |
| 39 | 0x01F9 | 0x06014EC6 | 0x04EC6 | Table list: 10 slots (48B each at ctx+0x6DA8) |
| 41 | 0x01FB | 0x06015060 | 0x05060 | Tavern exit ack |
| 42 | 0x021B | 0x060150A4 | 0x050A4 | User list notification — **NO-OP** (reads 4B, discards) |
| 43 | 0x020F | 0x060150D0 | 0x050D0 | **SIT REPLY**: reads [2B status][2B unused], if status==0: strcpy(ctx+0x74EC, ctx+0x7515), always clears ctx+0x7515 |
| 44 | 0x024C | 0x06015112 | 0x05112 | **MEMBER DELTA UPDATE**: checks status, process_member_entries, NO clear |
| 45 | 0x024D | 0x06015152 | 0x05152 | **MEMBER FULL REFRESH**: clears 8 slots, process_member_entries, ALWAYS processes |
| 46 | 0x024F | 0x06015290 | 0x05290 | **FIND RESULT**: reads [2B status][2B count_discarded][4B find_result→ctx+0x9C]. NO member processing! |
| 47 | 0x021A | 0x060152CE | 0x052CE | Stand up ack |
| 49 | 0x0246 | 0x060152FA | 0x052FA | Sign/action reply: reads [2B status][2B unused], if status==0: strcpy(ctx+0x74EC, ctx+0x7515), clears ctx+0x7515 |
| 50 | 0x0247 | 0x0601533C | 0x0533C | **SELF DATA**: memmove(ctx+0x74EC, payload+16, 40). UNCONDITIONAL. Clears ctx+0x7514. |
| 51 | 0x0255 | 0x0601538C | 0x0538C | Move seat reply |

---

## Paired Message Table (relevant tavern entries)

| Client Sends | Server Replies | Handler Purpose |
|---|---|---|
| 0x020E (sit) | 0x020F | Sit ack — name commit |
| 0x024B (memlist req) | 0x024C | Delta member update |
| 0x024E (find) | 0x024F | Find result (NOT member list!) |
| 0x0219 (stand) | 0x021A | Stand ack |
| 0x0245 (action) | 0x0246 | Action/sign reply |
| 0x0254 (move seat) | 0x0255 | Move seat ack |
| 0x01F8 (tbllist) | 0x01F9 | Table list |
| 0x020C (seat list) | 0x020D | Character seat list |
| 0x0216 (entry) | 0x0217 | Tavern entry ack |
| 0x01FA (exit) | 0x01FB | Tavern exit ack |

**0x024D is NOT in paired table** — it's a server-initiated push notification (full member refresh).

---

## Session Context Memory Map (GBR[2] = 0x202CB000)

| Offset | Size | Written by | Description |
|--------|------|-----------|-------------|
| +0x0004 | 2 | 0x020F, 0x024C, 0x024F | Status word (U16) |
| +0x009C | 4 | 0x024F | Find result (U32) |
| +0x00A0 | 2 | 0x0272 | Store type/flag (tavern=?) |
| +0x6C94 | 264 | 0x020D | Character seat area (12 x 22B slots) |
| +0x6DA0 | 2 | 0x01F9 | Table list field1 |
| +0x6DA2 | 2 | 0x01F9 | Table list entry_count |
| +0x6DA4 | 2 | 0x01F9 | Table list counter (zeroed) |
| +0x6DA8 | 480 | 0x01F9 | Table entries (10 x 48B slots) |
| +0x6F88 | 2 | 0x024C, 0x024D | Member count |
| +0x6F8C | 1376 | 0x024D | Member array (8 x 172B slots) |
| +0x74EC | 40 | 0x0247, 0x020F, 0x0246 | Active table/self name |
| +0x7514 | 1 | 0x0247 | Flag byte (cleared) |
| +0x7515 | ~40 | Client 0x020E send func | Pending name (cleared by 0x020F) |

---

## Handler Details

### 0x020F — Sit Reply (file 0x050D0)
- **Payload**: [2B status U16][2B unused U16] = 4 bytes
- **If status==0**: strcpy(ctx+0x74EC, ctx+0x7515) — commits pending name
- **Always**: clears ctx+0x7515[0] = 0
- **Note**: Since client sends target=0, ctx+0x7515 is empty. 0x0247 overwrites ctx+0x74EC anyway.

### 0x0247 — Self/Table Data (file 0x0533C)
- **Payload**: [16B header (skipped)][40B data] = 56 bytes
- **Action**: memmove(ctx+0x74EC, payload+16, 40) — UNCONDITIONAL, no status check
- **Also**: clears ctx+0x7514 = 0

### 0x024C — Member Delta Update (file 0x05112)
- **Payload**: [2B status→ctx+4][2B count→ctx+0x6F88][4B context→local][N×36B entries]
- **Checks status**: if status!=0, returns immediately
- **NO slot clearing** — updates existing entries in place
- **Paired reply** for 0x024B

### 0x024D — Member Full Refresh (file 0x05152) — SERVER PUSH
- **Payload**: [2B status→LOCAL][2B count→ctx+0x6F88][4B context→local][N×36B entries]
- **ALWAYS clears** all 8 member slots (172B each) before processing
- **ALWAYS processes** entries regardless of status
- **NOT paired** — server-initiated push notification
- **This is the correct message for populating member lists after sit**

### 0x024F — Find Result (file 0x05290)
- **Payload**: [2B status→ctx+4][2B count(discarded)][4B find_result→ctx+0x9C] = 8 bytes max
- **Does NOT** process member entries
- **Does NOT** clear member slots
- **Paired reply** for 0x024E (find request)

### Per-Entry Wire Format (36 bytes, used by 0x024C and 0x024D)

| Wire Offset | Size | Type | Description | Stored at slot offset |
|---|---|---|---|---|
| 0 | 16 | char[16] | Name (Shift-JIS null-padded) | +8 (memcpy 16B) |
| 16 | 1 | U8 | Member type (1=occupied) | +0 |
| 17 | 1 | U8 | Class bitmask (1<<class_id) | +26 (decoded) |
| 18 | 1 | U8 | Reserved | +25 |
| 19 | 1 | U8 | Race bitmask (1<<race_id) | +28 (decoded) |
| 20 | 4 | U32 BE | char_id | +168 (0xA8) |
| 24 | 8 | bytes | Visual block ([+2]=class 0-5, [+7]=level 1-16) | +4 area |
| 32 | 4 | bytes | Padding (skipped) | -- |

### Member Slot Layout (172 = 0xAC bytes each, at ctx+0x6F8C + i*172)

| Offset | Size | Field | Source |
|---|---|---|---|
| +0 | 1 | member_type | wire[16] |
| +4 | 4 | slot_index / empty marker (0xFFFFFFFF when cleared) | loop counter / clear |
| +8 | 16 | name | wire[0:16] |
| +24 | 1 | zero | cleared |
| +25 | 1 | reserved | wire[18] |
| +26 | 1 | class index (decoded) | wire[17] decoded |
| +28 | 1 | race index (decoded) | wire[19] decoded |
| +40 | 1 | level_raw | visual[7] |
| +46 | 1 | class_raw (copy) | visual[2] |
| +47 | 1 | class_raw | visual[2] |
| +48 | 1 | populated flag (=16) | constant |
| +168 | 4 | char_id | wire[20:24] U32 BE |

---

## Paired Wait Mechanism (FULLY DECODED 2026-04-13)

The mechanism is **cooperative, not blocking**. No busy-wait loop — integrated into the normal main loop.

| Step | Function | Address | What it does |
|------|----------|---------|-------------|
| 1 | `scmd_new_message(0, msg_type)` | 0x060249EC | Sets `session_ctx+6 = msg_type` (the wait tracker) |
| 2 | `scmd_send()` | 0x06024E3C | Sets `session_ctx+14 = 0x0E10` (3600-frame/60s timeout) |
| 3 | Tick function (per frame) | 0x06013112 | Decrements `session_ctx+14` by 1 each frame |
| 4 | `scmd_dispatch_inner()` | 0x0601341C | On ANY incoming msg: calls handler, then checks paired table. If `paired[i].send == ctx+6 AND paired[i].reply == received_type` → clears `ctx+6 = 0` |
| 5 | Main loop check | 0x0601015A | If `ctx+6 != 0 AND ctx+14 == 0` → timeout error/disconnect |

**Key insights**:
- ALL incoming messages are dispatched through their handlers normally during the wait
- The paired table check is an ADDITIONAL step after each handler call
- Unpaired messages (0x0247, 0x024D) are processed regardless of wait state
- `scmd_new_message()` at `0x06024A26: mov.w r0,@(6,r2)` writes msg_type for EVERY send
- Dispatch only checks paired table to clear — if received msg isn't paired, ctx+6 stays set
- Server can send 0x0274 to force-cancel any pending paired wait (writes 0xFFFF to ctx+4, clears ctx+6)

### Where session_ctx+6 is set/cleared
- **SET**: `scmd_new_message()` at 0x06024A26 — happens for every client send
- **CLEARED**: `scmd_dispatch_inner()` at 0x0601341C — only when received msg matches paired table
- **FORCE CLEARED**: msg_type 0x0274 handler — emergency cancellation

---

## Complete Sit Flow (CORRECTED 2026-04-12 — STRCPY BLANKING FIX)

```
Client sends: 0x020E (target_id=U32, cmd=U16) — 6 bytes
  If target=0: client clears ctx+0x7515, sends without table lookup
  If target!=0: client searches ctx+0x6DA8 (stride 48, VERIFIED) for matching table_id,
                copies entry name to ctx+0x7515

STRCPY BLANKING PROBLEM:
  0x020F handler: if status==0 → strcpy(ctx+0x74EC, ctx+0x7515)
  When target=0, ctx+0x7515 is EMPTY → strcpy BLANKS ctx+0x74EC!
  0x0247 handler: memmove(ctx+0x74EC, payload+16, 40) → UNCONDITIONALLY restores name.
  Therefore 0x0247 MUST be processed AFTER 0x020F.

  Previous ordering (0x024D→0x0247→0x020F) failed because:
    0x0247 sets name → 0x020F blanks it → paired wait exits → name EMPTY → freeze.

Server responds with THREE messages — 0x020F FIRST:
  1. 0x020F  — paired ack FIRST [2B status=0][2B unused=0]
              Handler at 0x050D0: strcpy blanks (already empty), paired wait exits.
  2. 0x0247  — self/table data [16B header][40B table name → ctx+0x74EC]
              Processed by main loop after paired wait exits → name RESTORED.
  3. 0x024D  — member FULL REFRESH [2B status][2B count][4B ctx][N×36B entries]
              Processed by main loop → members populated.

All three sent in rapid succession (same TCP segment). After paired wait exits:
  - Main loop SV_Poll delivers 0x0247 → ctx+0x74EC = table name
  - Main loop SV_Poll delivers 0x024D → ctx+0x6F88 = count, ctx+0x6F8C+ = members
  - UI draws with complete data.
```

---

## Complete Tavern Entry Flow

```
1. Game world entry: 0x026F → 0x0270 (ack) → 0x0271 → 0x0272 (STORE_IN status=1)
2. GOTOLIST cycle: 0x019A → 0x019B (destinations)
3. User selects matching entry → 0x026F (game world entry)
4. Client sends 0x01F8 → server sends 0x01F9 (table list, 3 entries)
5. User navigates and selects table (13-14s delay)
6. Client sends 0x020E (target=0, cmd=8)
7. Server sends: 0x020F + 0x0247 + 0x024D
8. User is now seated — UI shows member list view
9. Client may send 0x024B → server responds 0x024C (delta update)
10. Client sends 0x0219 (stand up) → server sends 0x021A
11. Client sends 0x01FA (tavern exit) → server sends 0x01FB
```

**NOTE**: 0x020D (seat list) was NOT sent in the test log. The tavern table list
(0x01F9) alone was sufficient for the client to display the table selection UI.

---

## Failure History

| Test | Approach | Result | Root Cause |
|------|----------|--------|------------|
| ALL pre-0x0247 | No 0x0247 sent | Freeze | ctx+0x74EC never populated |
| 135633 | 0x020F+0x0247+0x024F | Freeze | 0x024F is FIND RESULT, not member list |
| 092949 | 0x020F+0x0247+0x024D | Freeze | Correct ordering, but payload formats were WRONG (pre-2026-04-10 corrections) |
| 140145 | 0x024D+0x0247+0x020F | Freeze | STRCPY BLANKING: 0x020F sent LAST → strcpy(ctx+0x74EC, empty ctx+0x7515) blanked name that 0x0247 just wrote |
| FIX2 | 0x020F+0x0247+0x024D | **FAILS on HW** (tested 2026-04-22) | Freeze is downstream of paired-wait clear; not a payload issue |
| Binary patch @ 0x24E52 (tst→clrt forces state-259 advance) | State 259 bypass | **FAILS on HW** (tested 2026-04-22) | State 259 is not the real freeze point — see [sit-freeze-2026-04-22-session.md](sit-freeze-2026-04-22-session.md) |
| SIT_INCLUDE bisect (2026-04-22) | Just 0x020F alone, full 4-msg, etc. | All freeze identically | Server response content does not matter; trigger is client-local post-0x020E |

**ROOT CAUSES (THREE ISSUES)**:
1. Dispatch table format was wrong → sent 0x024F instead of 0x024D (fixed 2026-04-10)
2. Payload formats were wrong in test 092949 (fixed 2026-04-10)
3. STRCPY BLANKING: When target=0, 0x020F strcpy(ctx+0x74EC, ctx+0x7515) blanks the table name.
   0x0247 MUST be processed AFTER 0x020F to restore it. Send 0x020F FIRST (fixed 2026-04-12)

---

## If Hardware Test Still Fails — Investigation Paths (2026-04-13)

If FIX2 (0x020F+0x0247+0x024D with corrected payloads) still freezes, the issue is in client
post-sit state transition, NOT the message payloads. Investigate:

1. **Main loop post-paired-wait path** (0x0601015A-0x06010174):
   - What happens after ctx+6 is cleared? Does client transition to "seated" UI state?
   - Check flag at 0x06060F6C (must be set for paired wait to activate)
   - Check 0x06060E84 (must equal 1)

2. **Task state machine at 0x060674A8** (DIFFERENT from simple paired wait):
   - Used for zone transitions/warps, NOT tavern sit
   - ctx+0xA5 = reply_status, ctx+0xB0 = counter
   - If tavern sit somehow uses this path → investigate why

3. **GBR[0][160] callers** (file 0x0132DC):
   - The sit function is called via GBR[0] table index 160
   - Caller sets up context before calling → may set additional flags
   - Find WHO calls GBR[0][160] to understand full sit flow

4. **check_input function at 0x0601F120**:
   - Used by task state machine for user button confirmation
   - Reads controller bitmask from 0x06060E76
   - Button table at 0x06054FCC (7 entries of 6B each)
   - May be relevant if post-sit requires user confirmation

### 2026-04-22 follow-up — all 4 paths walked, results:

- **Path 1**: Both flags (`0x06060F6C`, `0x06060E84`) ARE set during zone entry
  by `init_zone_transition` (`FUN_06010554`). The main-loop check at
  `0x0601015A` correctly fires only when `ctx+6 != 0`. Our `0x020F` clears
  `ctx+6` via the pair table (entry 24: `[0x020E, 0x020F]` — verified),
  so the timeout never re-fires. **Not the cause of the freeze.**
- **Path 2**: **CONFIRMED** — `FUN_06036B6C` (sit driver) feeds the task SM
  struct at `0x060674A8` via `FUN_0602E920` (state 0 setup) and
  `FUN_0602E962` / `FUN_0602E96E` (state 2 poll/advance). So tavern sit
  DOES use this SM. Writes found at struct offsets `+0xB0` (byte) and
  `+0xB4` (u32) in `FUN_0602E974` (setup writes zero+param). Needs live
  RAM inspection to determine the freeze's exact state.
- **Path 3**: Sit sender is `FUN_060232DC`. Pool values resolved:
  target==0 writes `0` to `ctx+0x7515`, sends 0x020E. target!=0 looks up
  `ctx+0x6DA8` (stride 0x30). Our log confirms `target=0`. No new info.
- **Path 4**: `check_input` is called twice from `tavern_state_machine`'s
  epilogue (`0x06034EFA`, `0x06034F04`) only to detect return values 5 or 6,
  but the button table at `0x06054FCC` contains actions `0x0001-0x0010`
  (no 5 or 6). So these checks never fire here. **Not the cause.**

**Remaining approach**: live RAM inspection of the task SM struct at
`0x060674A8` during the freeze (Mednafen debugger or ICE) to identify which
state field is stuck and what would advance it.

See [sit-freeze-2026-04-22-session.md](sit-freeze-2026-04-22-session.md)
for full details.
