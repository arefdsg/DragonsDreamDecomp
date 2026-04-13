# Dragon's Dream: Revival Server Engineering Manual

**Version 2.0 -- April 2026**

**Game:** Dragon's Dream (Fujitsu x SEGA, December 1997, Japan-only)
**Product:** GS-7114, V1.003, released 1997-10-27
**Platform:** Sega Saturn MMORPG, SH-2 big-endian
**Binary:** `extracted/0.BIN` -- 504,120 bytes, load address `0x06010000` (Work RAM-H)
**Goal:** Revival server restoring online functionality on unmodified Saturn hardware

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Protocol Stack](#2-protocol-stack)
3. [Wire Format (SCMD)](#3-wire-format-scmd)
4. [SV Framing (lib_sv.c)](#4-sv-framing-lib_svc)
5. [Session Protocol](#5-session-protocol)
6. [BBS Phase](#6-bbs-phase)
7. [SCMD Dispatch](#7-scmd-dispatch)
8. [Paired Wait Mechanism](#8-paired-wait-mechanism)
9. [Connection Flow](#9-connection-flow)
10. [Login Flow](#10-login-flow)
11. [GOTOLIST / Zone Transition](#11-gotolist--zone-transition)
12. [Tavern Flow](#12-tavern-flow)
13. [Key RAM Addresses](#13-key-ram-addresses)
14. [Server v4 Architecture](#14-server-v4-architecture)
15. [Current Status and Known Issues](#15-current-status-and-known-issues)

---

## 1. Project Overview

Dragon's Dream is a Sega Saturn MMORPG developed by Fujitsu and published by SEGA in December 1997, exclusive to Japan. Players connected via the Saturn NetLink modem (14.4k) to NIFTY-Serve, a Japanese online service, to access the game servers. The original infrastructure was decommissioned in the early 2000s.

This project is a complete protocol-level reverse engineering of the client binary, producing a revival server that restores full online functionality using original, unmodified Saturn hardware connected through a DreamPi network bridge.

### 1.1 Binary Details

```
File:          extracted/0.BIN (504,120 bytes)
Load address:  0x06010000 (Work RAM-H)
Architecture:  Hitachi SH-2, big-endian, 16-bit instructions

Code regions:
  0x000000-0x000200  Startup/vectors
  0x000200-0x010000  Main game code (state machines, UI, world logic)
  0x010000-0x015000  Network code (BBS, SV, session, SCMD, dispatch)
  0x015000-0x03D000  Game logic (handlers, battle, shop, party, events)
  0x03D000-0x04D000  Data (strings, constants, tables, lookup data)
  0x04D000-0x07B000  Assets (compressed graphics, map data, fonts)
```

### 1.2 Saturn Memory Map

| Address Range | Size | Description |
|---|---|---|
| `0x06000000-0x060FFFFF` | 1 MB | Work RAM-H (code + data) |
| `0x00200000-0x002FFFFF` | 1 MB | Work RAM-L |
| `0x20200000-0x202FFFFF` | 1 MB | Work RAM-L (cache-through mirror) |
| `0x00180000-0x0018FFFF` | 64 KB | Backup RAM (battery-backed saves) |

### 1.3 Testing Environment

- Real Sega Saturn hardware with NetLink modem
- DreamPi for network bridging (transparent mode, `handler=transparent` in `config.ini`)
- `::host=<address>` parameter (at binary offset `0x03D6F4`) bypasses modem dialing for direct TCP
- Server runs on local network, port 8020

### 1.4 Decompilation Status

| Component | Status |
|---|---|
| SV Framing Layer | COMPLETE -- send/receive state machines fully decompiled |
| Session Protocol | COMPLETE -- establishment, DATA frames, checksums, sequence numbers |
| BBS Command Phase | COMPLETE -- all scripts and response matching logic decompiled |
| Wire Format | COMPLETE -- 8-byte header structure confirmed with binary evidence |
| Message Dispatch | COMPLETE -- 197-entry handler table, linear scan, sentinel-terminated |
| Server-to-Client Handlers | COMPLETE -- 173 substantive + 24 empty (rts) handlers decompiled |
| Client-to-Server Messages | COMPLETE -- all 104 message payload layouts documented |
| Connection State Machine | COMPLETE -- states 0-8, bit-7 flag, INIT sending logic |
| Login State Machine | COMPLETE -- states 0-7, controller polling, button dispatch |
| Gate Mechanism | COMPLETE -- game world / login state transitions |

---

## 2. Protocol Stack

The network protocol is a 5-layer stack. All post-BBS traffic is encapsulated through every layer.

```
+-----------------------------------------------------------+
| Layer 5: SCMD Game Messages                                |
| [2B param1][2B msg_type][4B payload_size][payload]         |
| 310 named message types, 197 client-side handlers          |
+-----------------------------------------------------------+
| Layer 4: Session Protocol (0x00/0xA6 frames)               |
| Sequence tracking (byte offsets), checksums, establishment  |
| 0x00 = server->client, 0xA6 = client->server               |
+-----------------------------------------------------------+
| Layer 3: SV Framing (lib_sv.c)                             |
| "IV" + 3hex(size) + 3hex(~size&0xFFF) + raw_payload       |
| Each message = one IV frame, max 4095 bytes                |
+-----------------------------------------------------------+
| Layer 2: BBS Commands                                      |
| " P\r"->"*\r\n", "SET\r"->"*\r\n", "C NETRPG\r"->"COM\r\n" |
+-----------------------------------------------------------+
| Layer 1: TCP / Modem Byte Stream                           |
| NetLink modem or DreamPi transparent bridge                |
+-----------------------------------------------------------+
```

**Invariants derived from binary analysis:**

1. Server MUST NOT send raw non-IV bytes while client is CONNECTED (SV_RecvFrame at file `0x0126DA`: any non-`'I'` byte + state CONNECTED triggers `error_dialog(1)` at `0x0602272E`)
2. Sequence numbers are cumulative BYTE OFFSETS, not frame counters (evidence: client INIT seq=0, 74B SCMD, next client frame seq=74; `session[116] = seq + copy_length`)
3. msg_type is a unique identifier, NOT a wire size (evidence: LOGIN_REQUEST msg_type=0x019E but payload=60B)
4. Server must send first after BBS phase -- Saturn deadlocks without initial server establishment frame
5. Client keepalive `$I'm alive!!\r\n` (at file `0x03EEC8`) is CLIENT-to-SERVER only; server keepalives must be IV-wrapped session ACK frames (flags=0x01, copy_length=0)

---

## 3. Wire Format (SCMD)

Every game message on the wire has an 8-byte header followed by payload.

```
Offset  Size  Field          Description
------  ----  -----          -----------
0       2     param1         Usually 0x0000 (dispatch ignores this field)
2       2     msg_type       Message type identifier (uint16 BE)
4       4     payload_size   Payload byte count (uint32 BE)
8       N     payload        Application data (N = payload_size bytes)
```

**Total wire size = 8 + payload_size.**

### 3.1 msg_type Is NOT Wire Size

Previous analysis incorrectly claimed msg_type equalled total wire size. Binary evidence disproves this:

| Message | msg_type | Actual Payload | Wire Size |
|---|---|---|---|
| LOGIN_REQUEST | 0x019E (414) | 60B | 68B |
| CHARDATA2_NOTICE | 0x0B6C (2924) | 16B | 24B |
| STANDARD_REPLY | 0x0048 (72) | VARIABLE | VARIABLE |

The msg_type values in the message table (file `0x04612C`) are unique monotonically increasing identifiers. The payload_size header field at offset [4:8] is authoritative for determining message boundaries.

### 3.2 Binary Evidence: Send Path

`scmd_new_message` (file `0x149EC`): writes param1 to buffer[0:2], msg_type to buffer[2:4], zeros buffer[4:8]. `scmd_send` (file `0x14E3C`): writes nMsgSize to buffer[4:8], then calls `SV_send(buffer, nMsgSize+8)`. The +8 accounts for the header.

### 3.3 Binary Evidence: Receive Path

Primary dispatch (file `0x003420`): reads msg_type from `buffer[2:4]`, passes `buffer+8` (payload pointer) to the matched handler. Dispatch does NOT read payload_size from header[4:8].

### 3.4 Server Implementation

```python
import struct

def build_game_msg(msg_type: int, payload: bytes, param1: int = 0) -> bytes:
    header = struct.pack('>HHI', param1, msg_type, len(payload))
    return header + payload

def parse_game_msg(data: bytes):
    param1, msg_type, payload_size = struct.unpack('>HHI', data[:8])
    payload = data[8:8 + payload_size]
    return msg_type, payload, param1
```

---

## 4. SV Framing (lib_sv.c)

The SV (SerVice) library provides lightweight framing over the modem/TCP byte stream. Source file: `lib_sv.c` (from assertion strings at file `0x03EF1C`).

### 4.1 IV Frame Format

Each SV frame is an 8-byte ASCII header immediately followed by raw binary payload:

```
IV<size_hex><complement_hex><raw_binary_payload>
```

| Component | Bytes | Description |
|---|---|---|
| `IV` | 2 | ASCII magic prefix (0x49, 0x56) |
| `<size_hex>` | 3 | Lowercase hex encoding of 12-bit payload size |
| `<complement_hex>` | 3 | Lowercase hex encoding of `(~size) & 0xFFF` |
| `<payload>` | size | Raw binary data (immediately follows, NO `\r\n` delimiter) |

**Total header: exactly 8 bytes.** There is NO `\r\n` between header and payload. There is NO checksum at the SV layer -- the complement field provides integrity on the size field only (`size XOR complement == 0xFFF`).

### 4.2 IV Frame Examples

```
"IV012fed" + 18 bytes   -> size=0x012(18),  comp=0xFED, 0x012^0xFED=0xFFF
"IV100eff" + 256 bytes  -> size=0x100(256), comp=0xEFF, 0x100^0xEFF=0xFFF
"IV002ffd" + 2 bytes    -> size=0x002(2),   comp=0xFFD, 0x002^0xFFD=0xFFF
```

### 4.3 Hex Encoding

- Encode table at `0x06056F5C`: `"0123456789abcdef"` (lowercase)
- Decode table at `0x0604F0A4`: `"0123456789ABCDEF"` (uppercase)
- Decode accepts both cases via `toupper()` before lookup

### 4.4 No Fragmentation

There is NO SV-level fragmentation. Each game message gets its own complete IV frame. Application-level chunking (e.g., CHARDATA_REPLY multi-page) uses separate game messages, each with its own IV frame.

Maximum IV payload: **4095 bytes** (12-bit size limit). Practical buffer limit: ~2000 bytes (SV_BUFFER_SIZE at file `0x03EEC0` = 0x800 = 2048).

### 4.5 SV Receive State Machine (file 0x0126DA)

`SV_RecvFrame` is a 3-state parser:

**State 0 -- Waiting for IV:**
- Scans byte-by-byte for `'I'` (0x49) then `'V'` (0x56)
- **CRITICAL:** Any non-`'I'` byte while connection state `[0x06062374]==2` (CONNECTED) triggers `error_dialog(1)` = communication error. This is why the server MUST NOT send raw keepalives or any non-IV bytes while the client is connected.

**State 1 -- Parsing Hex Digits:**
- Receives 6 hex chars, uppercased via `toupper()`
- First 3 chars -> payload_size
- Last 3 chars -> complement (verified via XOR)
- Transitions to State 2

**State 2 -- Receiving Payload:**
- Receives exactly `size` bytes of raw data
- Counter at `state+0x7F2` tracks bytes received
- When complete: delivers payload to delivery function at `0x060423C8`
- Resets to State 0

### 4.6 SV Send State Machine (file 0x01253E)

`sv_open` builds IV headers and sends byte-by-byte from the send queue at `0x060623D8`:
- Queue: max 20 entries, each 8 bytes `[4B data_ptr, 4B size]`
- Messages dequeued FIFO
- Each message gets its own IV frame

### 4.7 Keepalive

| Direction | Format | Notes |
|---|---|---|
| Client->Server | `$I'm alive!!\r\n` (file `0x03EEC8`) | Raw text, starts with `$` (NOT `I`) |
| Server->Client | IV-wrapped session ACK frame | flags=0x01, copy_length=0 |

The server MUST send IV-wrapped session ACK frames as keepalives, not raw text. The client's `$` prefix is safe because `$` (0x24) != `I` (0x49) so SV_RecvFrame in state 0 distinguishes them.

### 4.8 Timeouts

- SV timeout: ~10 seconds (value `0x0252` = 594 VBL ticks at 60fps, at file `0x012748`)
- Server should send keepalives every 5-8 seconds

### 4.9 SV Constants (file 0x03EEB8)

| File Offset | Value | Description |
|---|---|---|
| `0x03EEB8` | 0x10 (16) | SV_HEADER_BUF_SIZE |
| `0x03EEBC` | 0x100 (256) | SV_MAX_FRAG_DATA |
| `0x03EEC0` | 0x800 (2048) | SV_BUFFER_SIZE |

### 4.10 SV Error Codes

| Code | Name | Description |
|---|---|---|
| 0 | SV_OK | Success |
| 1 | SV_NOT_OPEN | Connection not opened |
| 2 | SV_NO_MEM | Memory allocation failed |
| 3 | SV_BAD_FRAG | Size complement mismatch |
| 4 | SV_REMOTE_TIME_OUT | No data within timeout |
| 5 | SV_N_RETRIES | Too many retransmissions |
| 6 | SV_CAN_SEND | Ready to send (status) |
| 7 | SV_CAN_NOT_SEND | Send buffer full |
| 8 | SV_DISC_PKT_IN | Disconnect packet received |
| 9 | SV_CONN_LOST | Connection lost |

### 4.11 SV Key Functions

| Function | File Offset | Memory Addr | Description |
|---|---|---|---|
| SV_Init | 0x01219E | 0x0602219E | Clears SV context at 0x202E4B3C |
| SV_Setup | 0x0121F8 | 0x060221F8 | Registers callbacks, inits session, sets [0x202E4B3C]=1 |
| SV_Poll | 0x0120E8 | 0x060220E8 | Called from main loop (file 0x000156), calls sv_open + SV_RecvFrame |
| sv_open | 0x01253E | 0x0602253E | Send state machine (builds IV header, sends byte-by-byte) |
| SV_RecvFrame | 0x0126DA | 0x060226DA | 3-state receive parser |

---

## 5. Session Protocol

ALL post-BBS messages go through session framing, which sits between SV IV framing and SCMD game messages.

**Protocol stack:** SCMD -> Session Protocol (0x00/0xA6) -> SV IV Framing -> TCP

### 5.1 Frame Types

| Byte [0] | Direction | Encoding | Description |
|---|---|---|---|
| `0x00` | Server->Client | Raw binary | DATA or control frame |
| `0xA6` | Client->Server | Escape-encoded | DATA or status frame |

### 5.2 Server-to-Client DATA Frame (0x00-type)

```
Offset  Size  Type       Field
------  ----  ----       -----
0       1     U8         0x00 (type marker)
1       1     U8         flags (bit0=has_seq, bit1=has_data, bit6=alt_data)
2       2     U16 BE     checksum (sum all bytes with [2:6] zeroed, & 0xFFFF)
4       2     zeros      (cleared for checksum computation)
6       2     zeros      (reserved/padding)
8       4     U32 BE     seq_byte_offset (outgoing cumulative byte count)
12      4     U32 BE     ack_num (must be > session[112], monotonically increasing)
16      2     U16 BE     copy_length (SCMD byte count)
18      2     zeros      (padding)
20      N     bytes      SCMD data (copy_length bytes)
```

For a DATA frame carrying SCMD, flags = `0x03` (bit0 + bit1).

### 5.3 FLAGS Byte

| Bit | Mask | Name | Description |
|---|---|---|---|
| 0 | 0x01 | has_seq_data | MUST set for seq/ack fields to be read |
| 1 | 0x02 | has_data | SCMD data present at offset 20 |
| 3 | 0x08 | ESTABLISH | Session establishment (in [8:10] sub-flags) |
| 6 | 0x40 | alt_data | Alternative data path |

**Without bit 0:** The delivery function at `0x060423C8` reads stale values from session context. Frame is silently dropped. Evidence: delivery function checks bit0 before reading seq/ack fields.

### 5.4 Sequence Numbers Are BYTE OFFSETS

Sequence numbers are cumulative byte offsets, NOT frame counters.

Evidence: Client INIT (seq=0, 74B SCMD) -> next client frame seq=74. After dispatch, Saturn updates `session[116] = seq + copy_length`. Server's `send_seq` starts at 0, incremented by SCMD size (copy_length) after each frame.

**ack_num:** Must be > `session[112]` (starts 0, updated after each accepted frame via `cmp/hi`). Set ack = client's last seq + copy_length + 1 (monotonically increasing).

### 5.5 Checksum

Additive byte sum computed at `0x060429B6`:

```python
def session_checksum(frame: bytearray) -> int:
    total = 0
    for i, b in enumerate(frame):
        if 2 <= i < 6:  # skip checksum field
            continue
        total += b
    return total & 0xFFFF
```

- Server 0x00-type: checksum stored at `[2:4]` as uint16 BE
- Client 0xA6-type: checksum stored at `[2:6]` as 4 ASCII hex chars (uppercase)

### 5.6 Session Establishment

After BBS phase completes, the server must send a **256-byte session establishment frame** to transition the client from CONNECTING to CONNECTED state:

```
Offset  Size  Value      Description
0       1     0x00       Server->client type
1       1     0x00       flags: NO has_data (non-data path)
2       2     checksum   uint16 BE checksum (computed with [2:6] zeroed)
4       2     0x0000     cleared for checksum
6       2     0x0000     reserved
8       2     0x0008     ESTABLISH flag (bit 3) -- REQUIRED
10      246   zeros      padding to 256 bytes total
```

The ESTABLISH flag (bit 3 in sub-flags at offset [8:10]) is REQUIRED. Without it, the delivery function at `0x060423C8` never sets `[0x06062374] = 2` (CONNECTED state) at address `0x060428CE`.

**Do NOT set bit 4 (0x0010)** -- that sets receive window from `[10:12]`, and window=0 blocks client sends.

### 5.7 Client-to-Server 0xA6 Frame

```
Offset  Size  Type       Field
------  ----  ----       -----
0       1     U8         0xA6 (type marker)
1       1     U8         flags
2       4     ASCII hex  checksum (4 uppercase hex chars)
6       1     U8         escape_byte (typically 0x1C)
7       1     U8         sub-flags
8+      var   escaped    escape-encoded data:
                         4 decoded bytes -> uint32 sequence
                         4 decoded bytes -> uint32 val2
                         4 raw bytes (skipped)
                         remaining -> SCMD data
```

**Escape encoding:** If `byte == escape_byte`, next byte XOR 0x60 = original value.

### 5.8 ACK-Only Frame (Server Keepalive)

```
Offset  Size  Value      Description
0       1     0x00       Server->client type
1       1     0x01       flags: has_seq_data only (NO has_data)
2       2     checksum   uint16 BE checksum
4       2     0x0000     padding
6       2     0x0000     padding
8       4     send_seq   Current seq (NOT incremented by this frame)
12      4     ack        ACK value (> session[112])
16      2     0x0000     copy_length = 0 (no SCMD)
18      2     0x0000     padding
```

This frame does NOT advance `send_seq`, does NOT dispatch any SCMD message, and serves as the server-to-client keepalive mechanism.

---

## 6. BBS Phase

After TCP connection (or modem CONNECT), the Saturn initiates a NIFTY-Serve BBS login sequence driven by a script table engine.

### 6.1 Command Sequence

```
Phase 1: Saturn sends " P\r" (3 bytes: 0x20 0x50 0x0D)
         Server responds: "*\r\n" (any response containing "*")

Phase 2: Saturn sends "SET 1:0,2:0,3:0,4:1,...,22:0\r" (86 bytes)
         Server responds: "*\r\n"

Phase 3: Saturn sends "C NETRPG\r" (or "C HRPG\r") (7-10 bytes)
         Server responds: "COM\r\n" (any response containing "COM")
```

**Critical implementation notes:**
- Saturn sends `\r` only (no `\n`) at end of each command
- Response matching is **substring-based** -- Saturn scans the receive buffer for match strings
- `*` matches any response containing byte `0x2A`
- `COM` matches any response containing those 3 bytes in sequence
- Error response containing `lear` (from "clear") triggers error handler
- `NO CARRIER` triggers connection-lost handler

### 6.2 BBS Script Engine (file 0x010128)

The BBS phase is driven by script tables. Each table entry is 12 bytes:

```c
struct BBS_Entry {
    uint32_t type;      // 1=SEND, 2=WAIT, 3=END
    uint32_t data;      // SEND: string_ptr, WAIT: timeout, END: 0
    uint32_t param;     // SEND: 0, WAIT: response_table_ptr, END: 0
};
```

### 6.3 Script Tables

| Table | File Offset | Purpose |
|---|---|---|
| MODEM_INIT | `0x045D3C` | AT commands: AT, ATZ, user config |
| BBS_LOGIN | `0x045DA8` | P, SET commands, wildcard match |
| BBS_CONNECT | `0x045DD8` | C HRPG, expects COM response |
| BBS_DISCONNECT | `0x045DFC` | OFF command, expects NO CARRIER |
| MODEM_HANGUP | `0x045C6C` | ATH hangup |

### 6.4 Response Tables

Each response table is an array of 8-byte entries `[4B match_str_ptr, 4B handler]`:

| Table Offset | Used After | Success Match | Error Matches |
|---|---|---|---|
| `0x045CF4` | `" P\r"` / `SET` | `"*"` | `"NO CARRIER"` |
| `0x045D0C` | `"C HRPG\r"` | `"COM"` | `"lear"`, `"NO CARRIER"` |
| `0x045D2C` | `"OFF\r"` | `"NO CARRIER"` | (none) |

---

## 7. SCMD Dispatch

### 7.1 Handler Dispatch Table (file 0x435D8)

The handler table contains **197 entries**, each 8 bytes:

```
Offset  Size  Field
0       2     msg_type (uint16 BE)
2       2     padding (always 0x0000)
4       4     handler_addr (uint32 BE, SH-2 memory address)
```

**CORRECTED 2026-04-10:** The format is `[msg_type:2][pad:2][handler:4]` starting at file `0x435D8`. Previous analysis incorrectly used `[handler:4][msg_type:2][pad:2]` starting at `0x435DC`, which caused all handler mappings to be shifted.

The table is NOT sorted. It is scanned linearly until a match is found. An entry with `msg_type = 0x0000` serves as the sentinel (end of table).

### 7.2 Primary Dispatch Function (file 0x003420)

```c
void dispatch_handler(uint8_t* msg_buffer) {
    uint16_t incoming_type = *(uint16_t*)(msg_buffer + 2);  // msg_type at offset 2

    for (int i = 0; i < handler_count; i++) {
        uint16_t entry_type = handler_table[i].msg_type;
        if (entry_type == 0) break;  // sentinel
        if (entry_type == incoming_type) {
            handler_table[i].handler(msg_buffer + 8);  // pass payload ptr
            return;
        }
    }

    // Special case: ACTION_CHAT_NOTICE (0x0274) handled outside table
    if (incoming_type == 0x0274) {
        action_chat_handler(msg_buffer);
    }
}
```

Handlers receive `r4 = buffer + 8` (pointer to payload data). The dispatch does NOT read `payload_size` from `header[4:8]`.

### 7.3 SCMD Library Functions

| Function | File Offset | Memory Addr | Description |
|---|---|---|---|
| `scmd_new_message` | `0x149EC` | `0x060249EC` | Init buffer: param1 + msg_type, sets `session_ctx+6 = msg_type` |
| `scmd_add_byte` | `0x14A32` | `0x06024A32` | Add 1 byte to payload |
| `scmd_add_word` | `0x14B04` | `0x06024B04` | Add 2 bytes (uint16 BE) to payload |
| `scmd_add_long` | `0x14BDC` | `0x06024BDC` | Add 4 bytes (uint32 BE) to payload |
| `scmd_add_data` | `0x14CD0` | `0x06024CD0` | Add N bytes from pointer to payload |
| `scmd_send` | `0x14E3C` | `0x06024E3C` | Set payload_size in header, queue for send, sets `session_ctx+14 = 0x0E10` (3600) |

**Buffer base:** `0x202E6148` (Work RAM-L, cache-through)
**nMsgSize:** `0x06062498` (current payload byte count)
**Maximum buffer:** 4800 bytes (assertion-checked)

### 7.4 Init Flags / Deferred Send System

After ESP_NOTICE sets `g_state[0x8E..0x91] = 1`, the dispatch function at `0x06024442` checks these flags on each main loop iteration:

| Flag Offset | Auto-sends | Message Type |
|---|---|---|
| `g_state+0x8E` | STANDARD_REPLY | 0x0048 |
| `g_state+0x8F` | PARTY_BREAKUP_NOTICE | 0x025F |
| `g_state+0x90` | CMD_BLOCK_REPLY | 0x02D4 |
| `g_state+0x91` | SYSTEM_NOTICE | 0x006D |

Each flag is cleared after the message is sent. These flags are also set by `init_zone_transition` (file `0x010554`).

---

## 8. Paired Wait Mechanism

The paired wait mechanism is **cooperative, not blocking**. It integrates into the normal main loop without busy-waiting.

### 8.1 Table Location

File `0x043484` (memory `0x06053484`): 84 entries, each 4 bytes `[send:2 BE][reply:2 BE]`, sentinel-terminated by `send_type=0x0000`. Additional login/session pairs precede this at file `0x043424`.

### 8.2 Mechanism Steps

| Step | Function | Address | Action |
|---|---|---|---|
| 1 | `scmd_new_message(0, msg_type)` | `0x060249EC` | Sets `session_ctx+6 = msg_type` (the wait tracker) at instruction `0x06024A26: mov.w r0,@(6,r2)` |
| 2 | `scmd_send()` | `0x06024E3C` | Sets `session_ctx+14 = 0x0E10` (3600 frames = 60s timeout) |
| 3 | Tick function (per frame) | `0x06013112` | Decrements `session_ctx+14` by 1 each frame |
| 4 | `scmd_dispatch_inner()` | `0x0601341C` | On ANY incoming msg: calls handler, then checks paired table. If `paired[i].send == ctx+6 AND paired[i].reply == received_type` -> clears `ctx+6 = 0` |
| 5 | Main loop check | `0x0601015A` | If `ctx+6 != 0 AND ctx+14 == 0` -> timeout error / disconnect |

### 8.3 Key Properties

- ALL incoming messages are dispatched through their handlers normally during the wait. The paired table check is an ADDITIONAL step after each handler call.
- Unpaired messages (e.g., 0x0247 self-data push, 0x024D member full refresh) are processed regardless of wait state.
- `scmd_new_message()` writes msg_type for EVERY send, meaning the wait tracker is set for every client message.
- If the received msg is not the expected paired reply, ctx+6 stays set and the timeout continues counting down.
- Server can send msg_type 0x0274 (ACTION_CHAT_NOTICE) to force-cancel any pending paired wait (writes 0xFFFF to ctx+4, clears ctx+6).

### 8.4 Paired Message Table (84 entries at file 0x043484)

| Idx | Client Sends | Server Replies | Category |
|---|---|---|---|
| 0 | 0x020E | 0x020F | Tavern sit |
| 1 | 0x024B | 0x024C | Tavern member list update |
| 2 | 0x024E | 0x024F | Tavern find |
| 3 | 0x0219 | 0x021A | Tavern stand |
| 4 | 0x0245 | 0x0246 | Tavern sign/action |
| 5 | 0x0254 | 0x0255 | Tavern move seat |
| 6 | 0x0250 | 0x0251 | Tavern sekiban |
| 7 | 0x0202 | 0x0203 | Shop list |
| 8 | 0x01FE | 0x01FF | Shop enter |
| 9 | 0x01FC | 0x01FD | Shop item |
| 10 | 0x01F2 | 0x01F3 | Shop buy |
| 11 | 0x01F4 | 0x01F5 | Shop sell |
| 12 | 0x0200 | 0x0201 | Shop exit |
| 13-22 | 0x029D-0x02B8 | 0x029E-0x02B8 | Bulletin board (dir/read/write/delete/mkdir/rmdir) |
| 23 | 0x01A2 | 0x01A3 | Party list |
| 24 | 0x01A4 | 0x022B | Party entry (non-sequential reply) |
| 25 | 0x01E6 | 0x01E7 | Allow join |
| 26 | 0x025B | 0x025C | Cancel join |
| 27 | 0x022C | 0x022F | Party unite (gap in reply) |
| 28 | 0x0230 | 0x0231 | Allow unite |
| 29 | 0x023B | 0x023C | Area list |
| 30 | 0x01AF | 0x01B0 | Teleport list |
| 31 | 0x023E | 0x023F | Explain/help |
| 32 | 0x04E0 | 0x0046 | Special registration |
| 33 | 0x0233 | 0x0234 | Mirror dungeon |
| 34 | 0x0240 | 0x0241 | Find user 2 |
| 35 | 0x0298 | 0x0299 | Class list |
| 36 | 0x029A | 0x029B | Class change |
| 37 | 0x01C1 | 0x01C4 | Move type 1 |
| 38 | 0x01C2 | 0x01C4 | Move type 2 (shares reply with 37) |
| 39 | 0x01AC | 0x01AD | Camp enter |
| 40 | 0x01DF | 0x01E0 | Set move mode |
| 41 | 0x02F7 | 0x02F8 | Give up |
| 42 | 0x01D3 | 0x01D4 | Set position |
| 43 | 0x01D6 | 0x02D8 | (non-sequential) |
| 44 | 0x02D9 | 0x02DA | (leader accept) |
| 45 | 0x01B3 | 0x01B4 | Camp exit |
| 46 | 0x0204 | 0x0205 | Equip |
| 47 | 0x026C | 0x026D | Disarm |
| 48 | 0x02E8 | 0x02E9 | Use skill |
| 49 | 0x02F5 | 0x02F6 | Change parameters |
| 50 | 0x0243 | 0x0244 | Encounter monster |
| 51 | 0x0221 | 0x0222 | Battle command |
| 52 | 0x0224 | 0x0225 | Battle change mode |
| 53 | 0x0296 | 0x0297 | Battle effect end |
| 54 | 0x01EA | 0x01EB | Battle end |
| 55 | 0x01E3 | 0x01E4 | Cancel encounter |
| 56 | 0x0235 | 0x0236 | (battle join) |
| 57 | 0x01CF | 0x01D0 | Exec event |
| 58 | 0x0293 | 0x0294 | Give item |
| 59 | 0x02D0 | 0x02D1 | Use item |
| 60 | 0x0289 | 0x028D | Sell (gap in reply) |
| 61 | 0x028E | 0x028F | Buy |
| 62 | 0x0290 | 0x0291 | Trade cancel |
| 63 | 0x02ED | 0x02EE | Compound |
| 64 | 0x0275 | 0x0276 | Confirm level up |
| 65 | 0x0277 | 0x0278 | Level up |
| 66 | 0x02B9 | 0x02BA | Skill list |
| 67 | 0x02E0 | 0x02E1 | Learn skill |
| 68 | 0x02E2 | 0x02E3 | Skill up |
| 69 | 0x02E4 | 0x02E5 | Equip skill |
| 70 | 0x02E6 | 0x02E7 | Disarm skill |
| 71 | 0x0268 | 0x0269 | Select theme |
| 72 | 0x026A | 0x026B | Check theme |
| 73 | 0x02A9 | 0x02AA | Mail list |
| 74 | 0x02AB | 0x02AC | Get mail |
| 75 | 0x02AD | 0x02AE | Send mail |
| 76 | 0x02AF | 0x02B0 | Delete mail |
| 77 | 0x02BB | 0x02BC | Colosseum waiting |
| 78 | 0x02BE | 0x02BF | Colosseum exit |
| 79 | 0x02C1 | 0x02C2 | Colosseum list |
| 80 | 0x02C3 | 0x02C4 | Colosseum entry |
| 81 | 0x02C5 | 0x02C6 | Colosseum cancel |
| 82 | 0x02C8 | 0x02C9 | Colosseum field entry |
| 83 | 0x02CD | 0x02CE | Colosseum ranking |

### 8.5 Login/Session Pairs (file 0x043424, preceding main table)

| Client Sends | Server Replies | Category |
|---|---|---|
| 0x0035 | 0x01E8 | INIT -> ESP_NOTICE |
| 0x019E | 0x019F | Login request -> Update chardata |
| 0x01AA | 0x02F9 | Update chardata reply -> Chardata request |
| 0x0B6C | 0x02F9 | Chardata2 notice -> Chardata request |
| 0x019A | 0x019B | Logout -> GOTOLIST |
| 0x019C | 0x019D | GOTOLIST notice -> Information notice |
| 0x01B7 | 0x01B8 | Find user -> Find user reply |
| 0x026F | 0x0270 | Store list -> Store enter |
| 0x0271 | 0x0272 | Game world -> Store in |
| 0x020C | 0x020D | Seat list req -> Seat list |
| 0x0216 | 0x0217 | Tavern entry -> Tavern entry ack |
| 0x01F8 | 0x01F9 | Table list req -> Table list |
| 0x02FA | 0x01F9 | Alt table list -> Table list (shares reply) |
| 0x01FA | 0x01FB | Tavern exit -> Tavern exit ack |

---

## 9. Connection Flow

### 9.1 Connection State Machine (file 0x0103C0)

- **Struct base:** R14 = `0x06061D80`
- **State byte:** `struct[0xBF]` at `0x06061E3F` (lower 7 bits = state, bit 7 = already-initialized flag)

```
State 0 (init) -> 1 (modem) -> 2 (BBS login) -> 3 (wait connect)
  -> 4 (send INIT) -> 5 (session, steady state)
       |
       v
State 0 <- 8 (cooldown) <- 7 (TCP disconnect) <- 6 (BBS disconnect)
```

| State | File Offset | Description |
|---|---|---|
| 0-2 | `0x0103C0` | Modem init, config, BBS login script |
| 3 | `0x010600` | Polls `[0x06062374]==2` (CONNECTED). 600-frame (~10s) timeout. On connect: state=4 |
| 4 | `0x010626` | Sends INIT (0x0035). Sets bit 7 -> `state=0x84` (prevents re-sending). Transitions to state 5 |
| 5 | `0x01071A` | Session protocol steady state. First entry: clears session_ctx[6], calls session init. Poll: runs session protocol. On completion: state 7 |
| 6 | `0x0106EC` | BBS disconnect: sends "OFF\r", waits for "NO CARRIER" |
| 7 | `0x0107EC` | TCP teardown. Clears `g_state[0x1D01]`. Transitions to state 8 (reconnect) or returns |
| 8 | `0x010834` | Reconnect cooldown: 100 frames (normal) or 20 frames (fast). On timeout: state 0 (full restart) |

**Bit 7 flag:** Once INIT (0x0035) is sent in state 4, bit 7 is set permanently. This prevents re-sending 0x0035 on reconnection -- the client NEVER re-sends 0x0035 after the first time.

### 9.2 Complete Connection Sequence

```
1. TCP connection established (modem CONNECT or ::host= direct)
2. BBS phase: " P\r"->"*\r\n", "SET..."->"*\r\n", "C NETRPG\r"->"COM\r\n"
3. Saturn enters state 3: calls SV_Setup -> [0x06062374]=1 (CONNECTING)
4. SV_Poll starts: SV_RecvFrame scans for 'I','V' header (send queue empty)
5. State 3 polls [0x06062374]==2 with 600-frame (~10s) timeout
6. SERVER sends 256-byte session establishment IV frame (ESTABLISH flag 0x0008)
7. Delivery function at 0x060423C8 sets [0x06062374]=2 (CONNECTED) at 0x060428CE
8. State advances 3->4: Saturn sends 0xA6 session response (18B IV frame)
9. State advances 4->5: Saturn sends INIT (0x0035) to server
10. Server responds with ESP_NOTICE (0x01E8) + UPDATE_CHARDATA_REQ (0x019F)
11. Login flow begins (see Section 10)
```

**SV_RecvFrame resets to state 0 after EACH delivery** -- all frames must be IV-wrapped.

**NO separate ack is needed** -- the single establishment frame with ESTABLISH flag transitions the client to CONNECTED.

**send_seq must be PRESERVED across re-establishment** during zone transitions. Evidence from hardware test: successful session showed seq 1201->1260, 1576->1635. Resetting to 0 produced garbage seq=3153728.

---

## 10. Login Flow

### 10.1 Login States 0-7 (file 0x0603C100)

Login states 0-7 are ALL LOCAL (no SCMD messages). They handle:
- Controller polling
- Button dispatch
- Character selection UI
- The parent function sends 0x019E (LOGIN_REQUEST) after state 7 completes.

### 10.2 Message Sequence

```
Client: 0x0035 (INIT, sent once in connection state 4, bit 7 prevents re-send)
  Server: ESP_NOTICE (0x01E8, 51B) + UPDATE_CHARDATA_REQ (0x019F, 24B)
    ** BOTH are required. Without 0x019F, Saturn times out after ~66s. **

User presses button at title screen.

Client: 0x019E (LOGIN_REQUEST, 60B)
  Server: 0x019F (UPDATE_CHARDATA_REQUEST, 24B) -- REQUIRED as paired reply
  Server: 0x01AA (UPDATE_CHARDATA_REPLY)
  Server: 0x02F9 (CHARDATA_REQUEST, 72 or 172B)
  Server: 0x02D2 (CHARDATA_REPLY) -- TYPE 1: char_list
  Server: 0x02D2 (CHARDATA_REPLY) -- TYPE 2: char_detail (triggers BRAM save)
  Server: 0x02D2 (CHARDATA_REPLY) -- TYPE 3: inventory
  Server: 0x019D (INFORMATION_NOTICE)

Client: 0x019A (LOGOUT, gotolist_count=1)
  Server: 0x019B (GOTOLIST, with zone entries)

Client selects zone from GOTOLIST -> game world entry sequence begins.
```

### 10.3 ESP_NOTICE (0x01E8) -- Handler at file 0x3F1C -- 51 bytes

First server message in login flow. Resets entire game state.

```
Offset  Size  Type       Field                    Destination
0       2     U16 BE     status                   g_state+0x04
2       2     U16 BE     session_param            g_state+0x0264
4       2     U16 BE     connection_id            g_state+0xA2
6       1     U8         game_mode                g_state+0xA4
7       1     U8         sub_mode                 g_state+0xA5
8       4     U32 BE     server_id                g_state+0x94
12      16    Shift-JIS  server_name              g_state+0xA6
28      12    bytes      session_data             g_state+0x7C88
40      11    bytes      config_bytes             g_state+0x7C94..0x7C9F
```

**Side effects:** Sets `g_state[0x8E..0x91] = 1` (init flags triggering deferred sends). Clears battle state, disappear cursor, mission roster, clock count. Clears SV msg_type and global flag byte.

### 10.4 CHARDATA_REPLY (0x02D2) -- Handler at file 0x3858

Three data types in multi-page format:

```
HEADER (8 bytes):
  [0] char_type (1/2/3), [1] page_number, [2] total_pages, [3] num_entries, [4:8] chunk_size

TYPE 1 (char_list, 24B/entry):
  [0:16] char_name, [16:18] experience, [18] class, [19] race, [20] gender, [21] level, [22] status

TYPE 2 (char_detail, 52B/entry) -- TRIGGERS BACKUP RAM SAVE:
  [0:2] char_slot_id, [2] class, [3] sub_class, [4:20] char_name,
  [20:22] experience, [22:30] stat_bytes, [32:36] gold, [36:52] equipment_slots

TYPE 3 (inventory, 24B/entry):
  [0:16] item_data, [16:24] discarded
```

### 10.5 Post-Login: ESP+UPDATE Required After Zone Transitions

After zone transition re-establishment, the server must send ESP_NOTICE (0x01E8) + UPDATE_CHARDATA_REQ (0x019F) again. The client NEVER re-sends 0x0035 (connection SM bit 7 set permanently). Evidence: hardware test without them produced black screen; with them, client resumed normally.

---

## 11. GOTOLIST / Zone Transition

### 11.1 GOTOLIST Rendering

GOTOLIST (0x019B) is rendered as a **list/menu**, NOT a world map. Entry[8..9] position field: HIGH byte = VDP2 char selector, LOW byte = display param. map_x=0 produces a visible icon.

### 11.2 Navigation Behavior

- **B button** = cancel, enters current zone directly
- **C button on matching entry** (where `server_info == zone_cd_id`) = enters game world

### 11.3 Zone Transition Sequence

When the user selects a destination that does NOT match `zone_cd_id`:

```
Client: 0x019C (GOTOLIST_NOTICE, mismatch)
Server: 0x019D (INFORMATION_NOTICE)
Server: 0x02EF (EXEC_EVENT_NOTICE, 4B: zone_id)
  -> Saturn begins zone transition via init_zone_transition (file 0x010554)
  -> 31-step reset sequence: clears state, sets init flags [0x8E-0x91]=1, calls gate_set(0)
  -> SV re-establishment required (session preserved, send_seq NOT reset)
  -> Server must send ESP_NOTICE + UPDATE_CHARDATA_REQ after re-establishment
  -> Client resumes GOTOLIST from cached entries
```

### 11.4 Zone Transition Bug: _zone_transition_done Flag

Zone transition via 0x02EF on cycle 2+ corrupts client state due to the `_zone_transition_done` flag. Evidence: second zone transition causes client hang. The server v4 works around this by tracking `_zone_cd_id` and `_zone_transition_count` and ensuring proper `server_info` matching.

### 11.5 server_info Rules

- **Pre-tavern (first GOTOLIST):** Natural `server_info = zone_id`. The entry matching `zone_cd_id` triggers game world entry.
- **Post-tavern (subsequent GOTOLISTs):** VARIED values required. Exactly 1 matching entry, others mismatched. All-matching values cause client hang (evidence from hardware tests: all `[4,4,4]` -> instant freeze; varied `[4,3,5]` -> client fine).

### 11.6 Gate Mechanism

- `gate_set` at `0x0603B488`: writes to `session_ctx[0xDDFE]` and `session_ctx[0xE8C2]`
- `game_world_sm` at `0x0603B51C`: PATH 2 checks `session_ctx[0xDDFE]==1` for entry
- Gate function at `0x0603B6F0`: checks `session_ctx[0xE8C2]==1`
- `init_zone_transition` at `0x06010554`: calls `gate_set(0)`, resets both flags
- `backup_ram_load` at `0x06010710`: loads 3 BRAM files, OVERWRITES gate flags
- Gate mechanism is COMPLETELY SEPARATE from connection state management (connection SM states 0-8 never touch gate flags)

### 11.7 Game World Entry Sequence

```
Client: 0x026F (STORE_LIST)
Server: 0x0270 (STORE_ENTER ack)
Client: 0x0271 (STORE_IN)
Server: 0x0272 (STORE_IN_REQUEST)
  First entry:  status=1 (2B) -> client sends 0x019A -> tavern interior
  Subsequent:   status=0 + store_flag=0 (3B) -> field/dungeon mode
```

---

## 12. Tavern Flow

### 12.1 Handler Dispatch Table (Tavern Entries)

All handlers verified against corrected dispatch table format `[msg_type:2][pad:2][handler:4]` at file `0x435D8`.

| Entry | msg_type | Handler File | Description |
|---|---|---|---|
| 28 | 0x0270 | 0x04AF4 | STORE_ENTER -- game world entry ack |
| 29 | 0x0272 | 0x04BFE | STORE_IN -- reads status, if 0: writes store_flag to ctx+0xA0 |
| 31 | 0x020D | 0x04C3A | Seat list: 12 slots (22B each at ctx+0x6C94) |
| 35 | 0x0217 | 0x04E7E | Tavern entry ack |
| 39 | 0x01F9 | 0x04EC6 | Table list: 10 slots (48B each at ctx+0x6DA8) |
| 41 | 0x01FB | 0x05060 | Tavern exit ack |
| 42 | 0x021B | 0x050A4 | User list notification -- **NO-OP** (reads 4B, discards) |
| 43 | 0x020F | 0x050D0 | **SIT REPLY**: reads [2B status][2B unused], if status==0: strcpy(ctx+0x74EC, ctx+0x7515), always clears ctx+0x7515 |
| 44 | 0x024C | 0x05112 | **MEMBER DELTA UPDATE**: checks status, process_member_entries, NO clear |
| 45 | 0x024D | 0x05152 | **MEMBER FULL REFRESH**: clears 8 slots, process_member_entries, ALWAYS processes |
| 46 | 0x024F | 0x05290 | **FIND RESULT**: reads [2B status][2B count_discarded][4B find_result -> ctx+0x9C]. NO member processing |
| 47 | 0x021A | 0x052CE | Stand up ack |
| 49 | 0x0246 | 0x052FA | Sign/action reply: reads [2B status][2B unused], if status==0: strcpy, clears ctx+0x7515 |
| 50 | 0x0247 | 0x0533C | **SELF DATA**: memmove(ctx+0x74EC, payload+16, 40). UNCONDITIONAL. Clears ctx+0x7514 |
| 51 | 0x0255 | 0x0538C | Move seat reply |

### 12.2 Complete Sit Flow (Confirmed Sequence)

```
Client sends: 0x020E (SIT_REQUEST, 6B: U32 target_id + U16 cmd)
  If target=0: client clears ctx+0x7515, sends without table lookup
  If target!=0: client searches ctx+0x6DA8 (stride 48) for matching table_id,
                copies entry name to ctx+0x7515

Server responds with THREE messages -- 0x020F FIRST:
  1. 0x020F (SIT_REPLY, 4B: [2B status=0][2B unused=0])
     Handler at 0x050D0: strcpy(ctx+0x74EC, ctx+0x7515) -- when target=0,
     ctx+0x7515 is empty, so this BLANKS ctx+0x74EC. Paired wait exits (ctx+6 cleared).

  2. 0x0247 (SELF_DATA, 56B: [16B header][40B table name data])
     Handler at 0x0533C: memmove(ctx+0x74EC, payload+16, 40) -- UNCONDITIONALLY
     restores table name. Processed by main loop AFTER paired wait exits.

  3. 0x024D (MEMBER_FULL_REFRESH: [2B status][2B count][4B context][N x 36B entries])
     Handler at 0x05152: clears all 8 member slots (172B each), processes entries.
     Server push (NOT in paired table). Processed by main loop after paired wait exits.

All three sent in rapid succession (same TCP segment). After paired wait exits:
  Main loop SV_Poll delivers 0x0247 -> ctx+0x74EC = table name
  Main loop SV_Poll delivers 0x024D -> ctx+0x6F88 = count, ctx+0x6F8C+ = members
  UI draws with complete data.
```

### 12.3 STRCPY Blanking: The State Transition Trigger

The strcpy in 0x020F's handler (`strcpy(ctx+0x74EC, ctx+0x7515)`) is the critical state transition. When `target=0`, ctx+0x7515 is empty, so strcpy blanks ctx+0x74EC. This is why 0x0247 MUST be processed AFTER 0x020F -- it restores the name that strcpy blanked.

**Ordering constraint:** 0x020F (paired ack, exits wait) -> 0x0247 (restores name) -> 0x024D (populates members). Reversing the order (e.g., 0x0247 before 0x020F) causes the name to be blanked after it was set, resulting in a freeze.

### 12.4 Member Entry Wire Format (36 bytes per entry)

Used by both 0x024C (delta update) and 0x024D (full refresh):

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

Entry stride verified by full SH-2 disassembly of processor at `0x060151D2`.

### 12.5 Session Context Memory Map (GBR[2] = 0x202CB000)

| Offset | Size | Written by | Description |
|---|---|---|---|
| +0x0004 | 2 | 0x020F, 0x024C, 0x024F | Status word (U16) |
| +0x009C | 4 | 0x024F | Find result (U32) |
| +0x00A0 | 2 | 0x0272 | Store type/flag |
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

### 12.6 Complete Tavern Entry Flow

```
1. Game world entry: 0x026F -> 0x0270 (ack) -> 0x0271 -> 0x0272 (STORE_IN status=1)
2. GOTOLIST cycle: 0x019A -> 0x019B (destinations)
3. User selects matching entry -> 0x026F (game world entry)
4. Client sends 0x01F8 -> server sends 0x01F9 (table list, 3 entries)
5. User navigates and selects table
6. Client sends 0x020E (target=0, cmd=8)
7. Server sends: 0x020F + 0x0247 + 0x024D
8. User is now seated -- UI shows member list view
9. Client may send 0x024B -> server responds 0x024C (delta update)
10. Client sends 0x0219 (stand up) -> server sends 0x021A
11. Client sends 0x01FA (tavern exit) -> server sends 0x01FB (8B)
```

---

## 13. Key RAM Addresses

| Address | Name | Description |
|---|---|---|
| `0x06062374` | Connection state | SV connection state: 0=disconnected, 1=connecting, 2=connected. Offset 0x60 in session struct. |
| `0x202E4B3C` | SV context | SV library context (Work RAM-L, cache-through). Cleared by SV_Init at file `0x01219E`. |
| `0x06062314` | SV session struct | SV layer session state (96+ bytes). |
| `0x060623D8` | Send queue | SV send queue (20 entries, 8 bytes each: [4B data_ptr, 4B size]). |
| `0x06062498` | nMsgSize | Current SCMD message payload size. |
| `0x202E6148` | SCMD buffer | SCMD message build buffer (cache-through, max 4800B). |
| `0x0605F26C` | g_state | Global game state structure. Referenced via GBR[1]. |
| `0x202CB000` | session_ctx | Session context (game data). Referenced via GBR[2]. |
| `0x06060EBC` | GBR pointer table | GBR register: [0]=0x06052530 (func ptrs), [1]=0x0605F26C (g_state), [2]=0x202CB000 (session ctx). |
| `0x06052530` | GBR[0] func table | 256 function pointer entries (4B each). Index 160 = sit function at `0x060232DC`. |
| `0x06061D80` | Conn state struct | Connection state machine base (R14). |
| `0x06061E3F` | Conn state byte | Connection state dispatch variable (R14+0xBF). Bits 0-6=state, bit 7=initialized. |
| `0x0605F432` | Global flag byte | Map/state flags (bit 1=map grid, bit 2=known map). |
| `0x0606967C` | Controller input | Active-high button bitmask (NOT of raw hardware). |
| `0x0606967E` | Button change | (new XOR old) AND new -- edge detection. |
| `0x06060E76` | Display input | Latched button state for game logic. |

### 13.1 Main Loop Phases (file 0x000156)

```
Phase 1: transition_anim
Phase 2: SV_Poll (calls sv_open + SV_RecvFrame)
Phase 3: (skipped in some contexts)
Phase 4: event_handler_fptr (SKIPS Phase 6 when active)
Phase 5: (processing)
Phase 6: g_state[0x01AD] dispatch
Phase 7: event loop
Phase 8: VBlank
```

### 13.2 Task System (file 0x028310)

Deferred task system with vtable dispatch:
- vtable[6] = `gate_set` (writes session_ctx[0xDDFE]+[0xE8C2])
- vtable[15] = `game_world_sm` (game world state machine at `0x0603B51C`)

---

## 14. Server v4 Architecture

### 14.1 Overview

- **Location:** `server/dragons_dream_server_v4/` (22 Python files)
- **Launch:** `python -m dragons_dream_server_v4 --port 8020`
- **Database:** SQLite persistence
- **Coverage:** 108/108 paired handlers implemented
- **Content:** 30 items, 20 monsters, 16 skills, 9 zones, 5 shops

### 14.2 Module Structure

The server is organized as a Python package with specialized handler modules:

- `handlers_login.py` -- Login flow (0x0035, 0x019E, chardata)
- `handlers_movement.py` -- Field movement (0x01C1/0x01C2 -> 0x01C4)
- `handlers_combat.py` -- Full combat engine (encounter, BTL_CMD, end sequence)
- `handlers_shop.py` -- Shop operations (enter, buy, sell, exit)
- `handlers_inventory.py` -- Equipment (equip, disarm, use_item with stat recalc)
- `handlers_skills.py` -- Skill management (list, learn, upgrade, equip/unequip)
- `handlers_leveling.py` -- Level up, class change
- `handlers_social.py` -- Chat, mail, bulletin board, tavern
- `handlers_party.py` -- Party list, entry, join, unite

### 14.3 Protocol Implementation

The server implements the full protocol stack:
1. BBS command phase (substring-based response matching)
2. SV IV framing (encode/decode)
3. Session protocol (establishment, DATA frames, checksums, byte-offset sequence numbers)
4. SCMD message construction (8-byte header + payload)
5. Paired wait compliance (correct reply msg_types for all 108 pairs)

### 14.4 Combat Engine

Full turn-based combat with binary-verified message formats:
- `0x0243` MONSTERWARN -> `0x0244` ENCOUNTMONSTER_REQUEST (2B)
- `0x01C9` ENCOUNTMONSTER_REPLY (10+Nx32B) -> `0x01CA` notice (0B) -> `0x021F` BATTLEMODE_NOTICE (2+Nx32B)
- Turn loop: `0x0221` BTL_CMD (12B) -> `0x0222` ack (2B) -> `0x0223` action (24B) -> `0x0227` result (44+Nx56B)
- End: `0x01C8` gold (12B+groups) -> `0x01EA` client ack -> `0x01EB` end (2B) -> `0x02F4` position restore (16B)

### 14.5 Admin GUI

Built-in admin interface for monitoring connections and managing game state.

---

## 15. Current Status and Known Issues

### 15.1 Confirmed Working on Hardware

- Full login flow: BBS -> session establishment -> ESP_NOTICE -> character data -> GOTOLIST
- Zone transition with re-establishment (send_seq preserved)
- Tavern entry: game world -> STORE_IN -> table list display
- Deferred send system (init flags 0x8E-0x91)

### 15.2 Pending Hardware Test

- **Tavern sit fix:** Corrected sit sequence (0x020F first, then 0x0247, then 0x024D) with corrected payload formats and ordering. Three root causes were identified and fixed:
  1. Dispatch table format was wrong (caused 0x024F to be sent instead of 0x024D) -- fixed 2026-04-10
  2. Payload formats were wrong (24B entries instead of 36B) -- fixed 2026-04-10
  3. STRCPY blanking: 0x020F must be sent FIRST so 0x0247 restores the name after strcpy blanks it -- fixed 2026-04-12

### 15.3 Known Constraints

- Zone transition via 0x02EF on cycle 2+ can corrupt client state due to `_zone_transition_done` flag. Server tracks `_zone_cd_id` and `_zone_transition_count` as workaround.
- Post-tavern GOTOLIST requires VARIED server_info values (exactly 1 matching). All-matching values cause client hang.
- Maximum IV payload is 4095 bytes (12-bit limit). Practical limit ~2000B.
- SCMD buffer maximum is 4800 bytes (assertion-checked at `0x06024A32`).
- Client keepalive `$I'm alive!!\r\n` is client-to-server only. Server must use IV-wrapped ACK frames.

---

*This manual documents facts verified against the binary at `extracted/0.BIN` (504,120 bytes, SH-2 big-endian, base 0x06010000). All handler addresses, memory offsets, and protocol details are derived from disassembly. No content is speculated or reconstructed.*
