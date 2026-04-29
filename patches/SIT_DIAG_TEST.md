# Sit-freeze diagnostic test procedure

This is a one-time hardware test that combines a single-byte client-side
patch with enhanced server-side logging to identify which character field
or message the production game expected post-sit. Once the data point is
captured, the patch is reverted and the fix is applied server-side only.

## What the test does

1. **Client patch** (`sit_diag_gate_patch.py`): bypasses the gate-byte check
   at `FUN_06030CEC`. The byte at `0x06067D58` controls whether the table-list
   state machine processes input. With the patch, the gate check still runs
   but its result is ignored — control always falls through, letting the
   state machine progress.

2. **Server logging**: when `h_sakaya_sit` fires, it sets
   `session._diag_post_sit = True`. After that, every incoming SCMD from the
   client is logged with full payload hexdump under the tag `SIT_DIAG_RX`.
   This captures exactly what the client requests/sends after the sit
   transition completes.

The combination tells us:
- Which messages the client sends post-sit that we currently don't (or that
  we're sending with the wrong content).
- Which character struct fields the client touches/relies on.
- The exact moment any subsequent freeze occurs (if there's a downstream
  state machine that also needs fixing).

## Apply the patch

```bash
cd "D:\DragonsDreamDecomp\NEW BRANCH"
py -3 patches\sit_diag_gate_patch.py
```

This auto-discovers `0.BIN` and any `Track 1.bin` Mode1/2352 CD images
under the project tree. Backups (`.pre_sit_diag_gate.bak`) are created
before any modification. Re-running is safe (already-patched files are
skipped).

If the auto-discovery doesn't find your patched CD location, pass it:

```bash
py -3 patches\sit_diag_gate_patch.py "D:\path\to\bincue\folder"
```

## Run the test

1. Burn / load the patched CD on your Saturn (or just put the patched
   `0.BIN` on the ODE).
2. Start the server with logging at INFO or DEBUG level.
3. Connect from the Saturn, log in, walk to a tavern, sit at a table.
4. Watch the server log for `SIT_DIAG_RX` lines after `SAKAYA_SIT`.
5. Collect the log file (`server/dd_server_*.log`).

Run for ~30 seconds after the sit attempt. Stop the server cleanly so the
log flushes.

## Analyze

Search the log for the two key markers:

```bash
grep -E "SAKAYA_SIT|SIT_DIAG_RX" server/dd_server_*.log
```

Each `SIT_DIAG_RX` line shows the message type, param1, length, and a full
hexdump. The first few messages after `SAKAYA_SIT` reveal:
- What the client requests next (a CHARDATA query, a status check, etc.)
- What payload format the client uses (so we can match the expected response)

Compare the message types against `memory/handler-payloads-detailed.md` to
identify each. If the client sends a message we don't have a handler for,
or sends one with unexpected content, that's the field/feature we need to
fix on the server.

## Revert the patch

After the test, restore the original 0.BIN and CD:

```bash
py -3 patches\sit_diag_gate_patch.py --revert
```

The session diagnostic flag is set per-session and disappears when the
session closes; no server-side cleanup needed beyond ensuring logging is
back at normal level for production.

## Apply the real fix

Once the missing data is identified:
1. Update the relevant character struct field on the server (or the
   message payload that pushes it).
2. Re-test on hardware **without the patch** — production data should
   now make the gate clear naturally.
3. If still broken, the diagnostic logs from this test will tell us why.
