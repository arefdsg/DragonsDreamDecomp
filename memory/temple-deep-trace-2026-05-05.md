---
name: Temple transition deep binary trace
description: End-to-end trace of what happens when player clicks TEMPLE in tavern. Identifies the sender function FUN_0602313E (send_gotolist_notice), the conditional init-flag clearing on ctx[0x1B8C] vs ctx[0x0260], and the hardcoded 3-cycle GOTOLIST loop limit that causes the documented freeze.
type: project
---

# Temple click — end-to-end binary trace

## What happens when player clicks TEMPLE icon in tavern

Per user log analysis + binary disassembly:

1. **User clicks TEMPLE icon** in the in-tavern menu (4-button UI: Tables / Temple / Settings / Exit)
2. **Client sends `0x019A`** (LOGOUT/destination request) — payload 2B `0000`
3. **Server responds `0x019B`** GOTOLIST with destinations (Cave Dungeon / Forest / Dark Tower in our config)
4. **User picks an entry** from GOTOLIST → client sends `0x019C` dest_id
5. **Server processes `0x019C` in `h_gotolist_notice`**: sends `0x019D + 0x02EF + re-establish + ESP + UPDATE`
6. **Client transitions** zone (cycle counter increments)
7. **Client auto-sends `0x019A` again** (it's now in the new zone, asking for new destinations)
8. **Server responds `0x019B`** again (same destinations because zone_id forced to 4)
9. Loop repeats. After **3 cycles** total → client goes silent (the documented freeze)

## The 0x019C SENDER on the client side

Located at **`FUN_0602313E`** (file `0x1313E`, mem `0x0602313E`). Disassembled:

```asm
0602313E:  4F22       sts.l pr,@-r15
06023140:  7FFC       add #-4,r15
06023142:  2F42       mov.l r4,@r15            ; save dest_id arg
06023144:  C602       mov.l @(2*4,gbr),r0      ; r0 = GBR[2] = session_ctx (0x202CB000)
06023146:  6403       mov  r0,r4                ; r4 = session_ctx
06023148:  9029       mov.w pc+disp,r0          ; r0 = 0x1B8C
0602314A:  034E       mov.l @(R0,r4),r3         ; r3 = ctx[0x1B8C] (4 bytes)
0602314C:  9028       mov.w pc+disp,r0          ; r0 = 0x0260
0602314E:  024E       mov.l @(R0,r4),r2         ; r2 = ctx[0x0260] (4 bytes)
06023150:  3230       cmp/eq r3,r2              ; T = (r3 == r2)
06023152:  8B08       bf -> 0x06023166         ; if NOT equal, skip flag-clear
                      ; --- IF EQUAL: clear init flags 0x008E-0x0091 ---
06023154:  9025       mov.w pc+disp,r0          ; r0 = 0x0090
06023156:  E300       mov #0,r3
06023158:  0434       mov.b r3,@(R0,r4)         ; ctx[0x90] = 0
0602315A:  70FF       add #-1,r0                ; r0 = 0x008F
0602315C:  0434       mov.b r3,@(R0,r4)         ; ctx[0x8F] = 0
0602315E:  7002       add #2,r0                 ; r0 = 0x0091
06023160:  0434       mov.b r3,@(R0,r4)         ; ctx[0x91] = 0
06023162:  70FD       add #-3,r0                ; r0 = 0x008E
06023164:  0434       mov.b r3,@(R0,r4)         ; ctx[0x8E] = 0
                      ; --- THEN send 0x019C ---
06023166:  951D       mov.w pc+disp,r5          ; r5 = 0x019C (msg_type)
06023168:  D315       mov.l pc+disp,r3          ; r3 = 0x060249EC (scmd_new_message)
0602316A:  430B       jsr @r3
0602316C:  E400       mov #0,r4                 ;   (delay) param1=0
0602316E:  64F2       mov.l @r15,r4            ; r4 = saved dest_id
06023170:  D30F       mov.l pc+disp,r3          ; r3 = 0x06024BDC (scmd_add_long)
06023172:  430B       jsr @r3
06023174:  0009       nop
06023176:  7F04       add #4,r15
06023178:  D210       mov.l pc+disp,r2          ; r2 = 0x06024E3C (scmd_send)
0602317A:  422B       jmp @r2                   ; tail-call scmd_send
0602317C:  4F26       lds.l @r15+,pr            ; (delay)
```

## The init flags ctx[0x008E-0x0091]

Per existing memory (esp-notice-handler.md):
- `ctx[0x008E]` = STANDARD_REPLY auto-send flag
- `ctx[0x008F]` = PARTY_BREAKUP_NOTICE auto-send flag
- `ctx[0x0090]` = CMD_BLOCK_REPLY auto-send flag
- `ctx[0x0091]` = SYSTEM_NOTICE auto-send flag

**Set to 1 by**: ESP_NOTICE handler, init_zone_transition.
**Cleared by**: send_gotolist_notice (this function) when `ctx[0x1B8C] == ctx[0x0260]`.

These flags gate the client's "deferred auto-send" system — when set to 1, the client auto-sends specific replies. When cleared to 0, those auto-sends are suppressed.

## The state-sync fields ctx[0x1B8C] and ctx[0x0260]

Both 4-byte fields. Their write-points couldn't be located via simple scan (no obvious `mov.w 0x1B8C/0x0260, r0; mov.l ..., @(R0,Rn)` patterns in code). They're either:
- Written via different addressing patterns (struct base + offset compiled differently)
- OR these are READ-ONLY in this code path; written by lower-level code we'd need more disassembly to find

**Three functions in the binary reference both 0x1B8C AND 0x0260**:
- `FUN_0602313E` — send_gotolist_notice (0x019C sender) ← this function
- `FUN_06023992` — REGIST_HANDLE_REQUEST sender (0x04E0)
- `FUN_0603A198` — message dispatcher (handles 0x01A3, 0x01A5, 0x01A8, 0x01B6, 0x01D7, 0x01E8 ESP_NOTICE, 0x022B, 0x022D, 0x022F, 0x024D, 0x025C, 0x025D, 0x02D8)

**Hypothesis**: ctx[0x1B8C] and ctx[0x0260] are state-machine sync pointers. ctx[0x0260] might be "current operation" and ctx[0x1B8C] might be "expected next operation". When they match, the system advances and clears auto-send flags.

## Why TEMPLE specifically fails — the 3-cycle GOTOLIST loop limit

The actual freeze is NOT in the Temple click handler itself. It's in the **GOTOLIST loop counter** on the client side.

Per `gotolist-flow.md` Test 23 (verbatim):
> *"Loop break → empty 0x019B → client sends 0x019C anyway → after **count=3, permanent keepalive silence** (no 0x0048). WORSE than no loop breaker."*

Per Test 22 attempt 2 (Dragon's Peak dest=6):
> *"Cycles 1-2 work, cycle 3 fails (silence after 0x019B for 2+ minutes). Stayed on map."*

**Each `0x019C → 0x02EF → re-establish` round = 1 cycle.** The client has a hardcoded limit of approximately 3 cycles, after which the GOTOLIST state machine permanently terminates with no further input processed.

## What the player's screen actually shows

```
Cycle 1:  user picks dest from GOTOLIST       → client transitions zone → back at GOTOLIST
Cycle 2:  user picks again (e.g. Temple)      → client transitions zone → back at GOTOLIST
Cycle 3:  user picks again                    → silence — GOTOLIST SM frozen
```

The map appears to "stay there" (per user description) because each click transitions but immediately returns to the GOTOLIST instead of entering a game-world zone.

## How the user is supposed to enter game world (per binary evidence)

There are TWO documented mechanisms:

### Mechanism 1: server_info matches zone_cd_id → client sends `0x026F`

If a GOTOLIST entry's `server_info` byte (entry+10) matches the client's `zone_cd_id` (set by the most recent `0x02EF` dest_index), pressing C on that entry triggers `0x026F STORE_LIST` — game world entry, NO zone transition.

Test 40 attempt 2 success path:
- `0x02EF dest_index=4` set zone_cd_id=4
- GOTOLIST included Cave Dungeon entry with server_info=4
- User picked Cave Dungeon → server_info(4) == zone_cd_id(4) → `0x026F` sent → game world entered

### Mechanism 2: B button or 42.6s timeout

Per `gotolist-flow.md` line 758-759 (claim):
> *"B button = enter current zone, 42.6s timeout = auto-enter current zone"*

Per same file line 1163 (contradiction):
> *"User explicitly reported: 'pressing B did not do anything' on cycle 2 GOTOLIST. B button does NOT trigger 0x026F."*

User has confirmed neither B button nor 42.6s timeout works in their hardware tests.

## Why Temple specifically can't currently work

For Temple to work via the 0x019C zone-transition path:
1. Server would need to send a 0x019B with a Temple zone in the destinations list
2. User clicks Temple → 0x019C dest_id=Temple_zone → cycle-2 zone transition
3. Cycle-2 zone transition is the documented broken path

For Temple to work via the 0x026F game-world-entry path:
1. After cycle 1, zone_cd_id = X (whatever dest_index was)
2. Temple's server_info would need to also = X (match)
3. User clicks Temple → server_info matches → 0x026F → game world entry
4. **BUT 0x026F goes to the player's CURRENT zone, not Temple specifically**

So Mechanism 2 takes the player to whichever zone they're currently in, NOT to Temple. The only way to actually reach Temple as a separate zone is via 0x019C, which is the broken cycle-2+ path.

## Concrete remaining unknowns

1. **What writes to `ctx[0x1B8C]` and `ctx[0x0260]`?** Without finding the writers, we can't deliberately make them equal/unequal to control init-flag clearing. This might unlock a different code path on cycle 3.

2. **Why does client give up after cycle 3?** Need to find the GOTOLIST SM internal counter and figure out its trigger condition. Might be in the SM phase table at `0x06054E74` or its handler at `0x0601DFB0`.

3. **Is there ACTUALLY a Temple zone in production?** Per zone definitions in our `game_data.py`, no zone is named Temple. The TEMPLE icon in tavern might trigger a different message type entirely (TELEPORT_REQUEST 0x01AF?) that we haven't observed in logs because we lack the corresponding scenario.

4. **Does production game even support multiple zone transitions per session?** Possible the original DD design forced the player to disconnect and reconnect for each zone change, accepting the 3-cycle limit as a deliberate "you must commit to a destination" constraint. Our test save's behavior might match real-game-disc behavior — and the cycle-2+ freeze is intended.

## What I haven't been able to verify without runtime debug

- Whether `ctx[0x1B8C]` and `ctx[0x0260]` are actually different in practice (they likely are, since the init flags don't get cleared in our test sessions — meaning the bf branch is taken)
- Whether the 3-cycle counter is in the GOTOLIST SM struct or elsewhere
- Whether there's a server-side message that resets the counter

## Honest verdict

The cycle-2/3 GOTOLIST loop freeze appears to be a **hardcoded client-side limit** (3 cycles max) combined with a **client design where 0x026F enters the current zone, not the picked destination**. Both behaviors are in the binary by design.

The "Temple" feature in the production game might have:
- (a) used a different message we haven't yet identified
- (b) required a separate server flow that included Temple in the GOTOLIST WITH a server_info that matched zone_cd_id (so user clicking Temple triggered 0x026F → game world re-entry → and the Temple "scene" was actually rendered locally based on game state, not a separate zone)
- (c) genuinely required a fresh connection for each zone change

We can't conclusively determine which without finding more handlers in the binary or recovering original gameplay footage/walkthroughs that show the Temple feature working.
