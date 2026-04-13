# Connection State Machine (file 0x0103C0, mem 0x060203C0)

## Overview
- Struct base: R14 = 0x06061D80
- State byte: struct[0xBF] at 0x06061E3F (& 0x7F for state, bit 7 = already-initialized)
- Returns: struct[0xB4] via R11

## State Diagram
```
State 0 (init) → 1 (modem) → 2 (BBS login) → 3 (wait connect) → 4 (send INIT) → 5 (session, steady state)
                                                                                         ↓
State 0 ← 8 (cooldown) ← 7 (TCP disconnect) ←────────────────────────── 6 (BBS disconnect)
```

## States

### State 0-2: Connection Setup
- State 0: Modem init (ATZ, AT commands)
- State 1: More modem config
- State 2: BBS login script (P, SET TERM, C NETRPG)

### State 3: Wait for CONNECTED (file 0x010600)
- Calls polling function at 0x06022298
- If [0x06062374]==2 (CONNECTED): sets state=4
- 600-frame (~10s) timeout

### State 4: Send INIT (file 0x010626)
- First entry: sends INIT (0x0035) to server
- Sets bit 7 → state=0x84 (prevents re-sending)
- Transitions to state 5

### State 5: Session Protocol (file 0x01071A) — STEADY STATE
- First entry: clears session_ctx[6], calls session protocol init (0x0602EDA2)
- Poll: calls session poll (0x0602E962)
- On completion: transitions to state 7, sets flag at 0x06061E46
- Also checks flag bit 0 → may jump to state 7 immediately

### State 6: BBS Disconnect (file 0x0106EC)
- Runs BBS disconnect script: WAIT *, SEND "OFF\r", WAIT "NO CARRIER"
- On completion: transitions to state 5

### State 7: TCP Teardown (file 0x0107EC)
- First entry: calls TCP teardown init (0x010204)
- Poll: calls TCP disconnect poll (0x0102BC)
- On completion: clears g_state[0x1D01], transitions to state 8 (if reconnect) or returns

### State 8: Reconnect Cooldown (file 0x010834)
- Countdown timer: 100 frames (normal) or 20 frames (fast)
- On timeout: transitions to state 0 (full restart)

## Critical Finding: NO Gate Writes
The connection SM (ALL states 0-8) does NOT:
- Call gate_set (0x0603B488)
- Call func_B/task_dispatch (0x06028310) for gate operations
- Write to session_ctx[0xE8C2] or [0xDDFE]
- Write to g_state[0x01AD]

The gate mechanism is COMPLETELY SEPARATE from connection management.
