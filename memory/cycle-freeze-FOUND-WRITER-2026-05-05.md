---
name: Cycle-freeze WRITER FOUND — FUN_0601B316 default branch
description: Pinpointed the exact instruction that writes 0xFF to g_state[+0x1B6B], and the dispatch logic gating it. The state byte is rewritten conditionally based on session_ctx[+0xA4] — which ESP_NOTICE writes from payload data.
type: project
---

# Found the writer of g_state[+0x1B6B]

After deep tracing the per-frame poller chain, the WRITER is found:

## The write site

**`FUN_0601B316`** (init function called from `FUN_0601B058` when `g_state[+0x1B6B] == 0xFF`), default branch starting at **`0x0601B3C0`**:

```asm
                          ; r13 = g_state (loaded at function entry)
                          ; r14 = return value from sub-function (0 = complete, !=0 = wait)
0601B3C0: tst r14,r14
0601B3C2: bf -> 0x0601B3D8     ; if NOT complete, skip writes and return
                                ; --- COMPLETE: rewrite the gate bytes ---
0601B3C4: mov.w pc+,r3         ; r3 = 0x00FF
0601B3C6: mov #-1,r4            ; r4 = 0xFFFFFFFF
0601B3C8: mov.w pc+,r0         ; r0 = 0x1B6B
0601B3CA: mov.b r3,@(R0,r13)    ; *** g_state[+0x1B6B] = 0xFF ***
0601B3CC: add #-3,r0            ; r0 = 0x1B68
0601B3CE: mov.b r4,@(R0,r13)    ; g_state[+0x1B68] = 0xFF
0601B3D0: add #2,r0             ; r0 = 0x1B6A
0601B3D2: mov.b r4,@(R0,r13)    ; g_state[+0x1B6A] = 0xFF
0601B3D4: add #-1,r0            ; r0 = 0x1B69
0601B3D6: mov.b r4,@(R0,r13)    ; g_state[+0x1B69] = 0xFF
0601B3D8: lds.l @r15+,pr
0601B3DA: mov r14,r0            ; return value = r14 (0 = complete)
0601B3DC: mov.l @r15+,r11
0601B3DE: mov.l @r15+,r12
0601B3E0: mov.l @r15+,r13
0601B3E2: rts
0601B3E4: mov.l @r15+,r14
```

So the write happens when:
1. The init sub-function returns `r14 == 0` (reconnection complete)
2. AND the dispatch (at function entry) took the DEFAULT branch (not branch 6 or branch 9)

## The dispatch at function entry

At `0x0601B316`:
```asm
0601B316: mov.l r14,@-r15
0601B320: mov.l @(0x4,gbr),r0      ; r0 = GBR[1] = g_state
0601B322: mov r0,r13                ; r13 = g_state
0601B324: mov.l @(0x8,gbr),r0      ; r0 = GBR[2] = session_ctx
0601B326: mov r0,r12                ; r12 = session_ctx
0601B328: mov.l pc+,r11             ; r11 = 0x0602825A (function ptr)
0601B32A: mov.w pc+,r0              ; r0 = 0x00A4
0601B32C: mov.b @(R0,r12),r0        ; r0 = session_ctx[+0xA4]
0601B330: cmp/eq #6,r0
0601B332: bt -> 0x0601B37E         ; if 6: branch (does OTHER stuff, no 0xFF write)
0601B334: cmp/eq #9,r0
0601B336: bt -> 0x0601B368         ; if 9: branch (does OTHER stuff, no 0xFF write)
0601B338: bra -> 0x0601B3C0        ; default → 0xFF write path
```

**So `session_ctx[+0xA4]` controls which branch.** Anything that's NOT 6 AND NOT 9 takes the DEFAULT branch which writes 0xFF.

## Where session_ctx[+0xA4] is written

ESP_NOTICE handler (file 0x03F1C) at offset `0x06013F56`:
```asm
06013F44: mov.w pc+,r4              ; r4 = 0x00A2 (payload read offset)
06013F46: mov.l r0,@r15
06013F48: mov.l pc+,r3              ; r3 = 0x06019FF6 (read_u16be function)
06013F4A: jsr @r3                    ; r0 = read_u16be(payload + 0xA2)
06013F4E: mov r0,r13                 ; r13 = u16 result
... [more reads]
06013F54: mov.w pc+,r0              ; r0 = 0x00A4
06013F56: mov.b r3,@(R0,r14)         ; session_ctx[+0xA4] = r3 (low byte of result)
```

So `session_ctx[+0xA4]` = a byte derived from the ESP_NOTICE payload at offset `0xA2`.

## Our ESP_NOTICE payload — only 51 bytes

```python
esp = bytearray(51)
struct.pack_into('>H', esp, 0, 0)               # status
struct.pack_into('>H', esp, 2, session_param)   # offset 2
struct.pack_into('>H', esp, 4, connection_id)   # offset 4
esp[6] = 6                                       # game_mode
struct.pack_into('>I', esp, 8, 1)               # server_id
esp[12:28] = sjis_pad("DD Revival", 16)         # server_name
```

But the ESP_NOTICE handler tries to read at payload offset **0xA2 (162)** — way past our 51-byte payload! The actual byte returned by `read_u16be(payload+0xA2)` is whatever lies past the end of our payload buffer (probably zeros or garbage from the SCMD parser).

Result: `session_ctx[+0xA4]` becomes 0 (or random uninitialized), so:
- 0 != 6 AND 0 != 9 → DEFAULT branch → writes 0xFF to `g_state[+0x1B6B]`

## So why does cycle 3 fail?

If our analysis is right, EVERY ESP_NOTICE should set `session_ctx[+0xA4]` to 0, every reconnection should run the default branch, and `g_state[+0x1B6B] = 0xFF` should be written every cycle. That should make `FUN_0601B058` always take the init path which restores SV_Poll.

The fact that cycles 1-2 work but cycle 3 fails suggests one of these:

### Theory A: FUN_0601B058 is gated on something that fails on cycle 3
The per-frame callback at `[0x0605F420]` runs only when **`session_ctx[+0xABAB] != 0`** (per existing memory). After 2 cycles, that gate byte might become 0, blocking ALL further callback executions.

### Theory B: ctx[+0xA4] takes a different value on cycle 3
If the SCMD payload buffer happens to have non-zero data at offset 0xA2 on cycle 3 (from accumulated past sends), `session_ctx[+0xA4]` could become 6 or 9, taking a different branch that doesn't write `g_state[+0x1B6B] = 0xFF`. Then cycle 4's `FUN_0601B058` would take the non-init path and not restore SV_Poll.

### Theory C: The init sub-function at 0x0601B316 line 0x0601B374 returns non-zero on cycle 3
That function (called via `bsr` then `tst r14`) returns 0 = complete. If it returns non-zero, the `bf` at 0x0601B3C2 skips ALL writes — `g_state[+0x1B6B]` keeps its current value, which after a few cycles might no longer be 0xFF.

## Concrete fixes to TEST (in priority order)

### Fix 1 (highest priority — directly addressable)
**Make our ESP_NOTICE payload large enough.** Per the handler reads at offset 0xA2, the payload should be at least 0xA4 = 164 bytes (currently we send 51). Pad it out so reads land in deterministic bytes.

```python
esp = bytearray(180)  # Was 51 — handler reads at offset 0xA2-0xA5
# offset 0xA2-0xA5: deliberately leave as 0 so ctx[+0xA4]=0
# This makes default branch always take the 0xFF-write path
```

### Fix 2 (if Fix 1 doesn't help)
**Verify session_ctx[+0xABAB] doesn't become 0.** Search the binary for what writes 0 to that byte after multiple transitions. May require server-side ESP_NOTICE re-issue or another message.

### Fix 3 (deepest)
**Identify the init sub-function** at `0x0601B316 + ?` (the one called by `bsr` in the dispatch branches) and confirm it returns 0 across all cycles.

## What I conclusively established this session

1. **`FUN_0601B316`'s default branch at `0x0601B3C0`** is the WRITER of `g_state[+0x1B6B] = 0xFF`. 4 bytes written: 0x1B68, 0x1B69, 0x1B6A, 0x1B6B.

2. **Dispatch is gated on `session_ctx[+0xA4]`** (NOT 6 AND NOT 9 → write happens).

3. **`session_ctx[+0xA4]` comes from ESP_NOTICE payload offset 0xA2** — but our payload is only 51 bytes, so the handler reads garbage past the end. Padding the payload to ≥ 164 bytes would make the read deterministic.

4. **The init branch of `FUN_0601B058`** (which calls `FUN_0601B316`) restores SV_Poll gate from the saved value at `struct@(0x060610C8 + 0xE)`.

This is genuinely the deepest binary trace this project has had on the cycle-freeze. We have a specific, testable hypothesis: pad the ESP_NOTICE payload to 164+ bytes so the dispatch always takes the 0xFF-write path.
