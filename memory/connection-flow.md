# Dragon's Dream Connection Flow Analysis

## Binary: 0.BIN (504,120 bytes, SH-2 big-endian, base address 0x06010000)

---

## 1. Complete Connection Flow Overview

The connection follows a NIFTY-Serve BBS model. After modem CONNECT,
the **Saturn speaks first** with BBS commands. The server must respond
to each command with the expected prompt/response before the game
protocol begins.

```
Phase 1: MODEM INIT (Saturn -> Modem)
  AT\r            -> wait for "OK"
  ATZ\r           -> wait for "OK"
  AT&FW1X3\N2%C3  -> wait for "OK"
  ATDT<number>\r  -> wait for "CONNECT"

Phase 2: BBS LOGIN (Saturn -> Server, AFTER modem CONNECT)
  " P\r"          -> wait for "*" prompt
  "SET 1:0,...\r" -> wait for "*" prompt
  "C HRPG\r"      -> wait for "COM" in response

Phase 3: GAME PROTOCOL (SV framing layer)
  LOGIN_REQUEST   -> server processes, sends replies
  (game messages flow via SV fragments with CRC-16-CCITT)

Phase 4: DISCONNECT
  Server sends "*" prompt
  "OFF\r"         -> connection drops (NO CARRIER)
```

---

## 2. BBS Command Sequences (Exact Bytes)

### 2.1 Phase 2a: Initial Prompt (" P\r")

**Saturn sends (3 bytes):**
```
20 50 0D                         " P\r"
```

**Server must respond with (minimum):**
```
2A                               "*"
```
The Saturn scans for the byte `*` (0x2A) anywhere in the response.
The server should send `*\r\n` or similar. Any data containing `*`
will match. If `NO CARRIER` is received instead, the connection is
considered lost.

### 2.2 Phase 2b: Terminal Settings ("SET ...")

**Saturn sends (86 bytes):**
```
53 45 54 20 31 3A 30 2C 32 3A 30 2C 33 3A 30 2C
34 3A 31 2C 35 3A 30 2C 37 3A 30 2C 38 3A 30 2C
39 3A 30 2C 31 30 3A 30 2C 31 32 3A 30 2C 31 33
3A 30 2C 31 34 3A 30 2C 31 35 3A 30 2C 31 38 3A
30 2C 31 39 3A 30 2C 32 303A 30 2C 32 31 3A 30
2C 32 32 3A 30 0D

ASCII: "SET 1:0,2:0,3:0,4:1,5:0,7:0,8:0,9:0,10:0,12:0,13:0,14:0,15:0,18:0,19:0,20:0,21:0,22:0\r"
```

This is a NIFTY-Serve SET command configuring terminal parameters.
Note that parameter 4 is set to 1 (all others are 0). Missing
parameters 6, 11, 16, 17 are intentionally omitted.

**Server must respond with:**
```
2A                               "*"
```
Same as above - just send back any response containing `*`.

### 2.3 Phase 2c: Connect to Game ("C HRPG\r")

**Saturn sends (7 bytes):**
```
43 20 48 52 50 47 0D             "C HRPG\r"
```

"C HRPG" = NIFTY-Serve "Connect to HRPG" command (the game's
forum/service identifier on NIFTY-Serve).

**Server must respond with something containing "COM":**
```
434F4D                           "COM" (substring match)
```

Suggested server response: `"COM HRPG\r\n"` (mimicking NIFTY-Serve
"COMmand mode" or "COMnected" response).

**Error responses:**
- Response containing `lear` (from "clear") -> triggers error handler
  at code offset 0x010944. This likely means the game service is
  unavailable or the connection needs to be "cleared."
- `NO CARRIER` -> connection lost

### 2.4 Phase 2 Alternative: Reconnection (Phase 2 shortcut)

There is a second BBS login sequence (BBS_LOGIN_PHASE2) that skips
the ` P\r` and `SET` commands and goes directly to:
```
"C HRPG\r"      -> wait for "COM"
```
This is used for reconnection when terminal settings are already
configured.

### 2.5 Disconnect Sequence

**Server initiates by sending `*` prompt, then:**

Saturn sends:
```
4F 46 46 0D                      "OFF\r"
```

Server responds by dropping the connection (Saturn expects `NO CARRIER`).

---

## 3. Modem Configuration Details

### 3.1 Modem Init String

Located at file offset `0x045F17`:
```
AT&FW1X3\N2%C3
```

Breakdown:
- `AT&F` - Factory reset
- `W1`   - Error correction reporting enabled
- `X3`   - Extended result codes (CONNECT speed, BUSY detection)
- `\N2`  - Auto-reliable (MNP/LAPM) mode
- `%C3`  - Both transmit and receive data compression

### 3.2 Speed Control Registers

Two S91 register settings found:
- `S91=0` at file offset `0x03D71C` (default transmit level)
- `S91=00` at file offset `0x03D724` (alternate transmit level)

### 3.3 Dial Commands

- `ATDT` at `0x03D704` (tone dialing)
- `ATDP` at `0x03D70C` (pulse dialing)

The modem init sequence uses `%M` as a placeholder for the modem
init string and `%D` as a placeholder for the dial command + number.
These are expanded at runtime.

### 3.4 "Infinity Dialing" Mode

String at `0x03D6D4`: `"*** infinity dialing go!! ***\r\n"`
This is a debug/retry mode that continuously attempts to dial.

---

## 4. ::host= Parameter

Located at file offset `0x03D6F4` (7 bytes + terminators):
```
0D 0A 3A 3A 68 6F 73 74 3D      "\r\n::host="
```

Referenced in code at file offset `0x0104AC` (constant pool entry).
The `\r\n` prefix suggests this is parsed from a multi-line input
(possibly the phone number field).

**Purpose:** Allows direct TCP connection without modem dialing.
When the user enters `::host=<address>` instead of a phone number,
the game bypasses modem dialing and connects directly to a TCP host.

This is critical for DreamPi/revival server use - the game can
connect directly over TCP when this parameter is used.

The code at `0x0104AC` is in the connection initialization function
alongside the dialing code, suggesting it's an alternative code path
that skips the modem init and dial phases entirely.

---

## 5. SV Framing Protocol

After the BBS login completes (COM response received), the connection
transitions to the SV (SerVice? SerVer?) framing protocol.

### 5.1 SV Fragment Format

```
+--------+--------+------------------+--------+--------+
| Header (2B, BE) |  Payload (N B)   |  CRC (2B, BE)   |
+--------+--------+------------------+--------+--------+

Header: 16 bits big-endian
  Bits [15:12] = Flags (4 bits)
    - Bit 15 (0x8000): Last/only fragment flag
    - Bits [14:12]: Fragment type/sequence
  Bits [11:0] = Payload size (12 bits, max 4095 = 0xFFF)

CRC: CRC-16-CCITT (polynomial 0x1021)
  - Lookup table at file offset 0x045F26 (256 entries, 512 bytes)
  - Standard CRC-16-CCITT table (verified all 256 entries match)
  - CRC computed over the header + payload bytes
```

### 5.2 SV Constants (at file offset 0x03EEB8)

```
0x00000010 = 16    (SV header/overhead parameter)
0x00000100 = 256   (fragment buffer size or queue depth)
0x00000800 = 2048  (max fragment payload size used in practice)
```

### 5.3 SV Status/Error Codes

Enum table at file offset `0x04DD8C`:

| Value | Name               | Description                        |
|-------|--------------------|------------------------------------|
| 0     | SV_OK              | Success                            |
| 1     | SV_NOT_OPEN        | Connection not open                |
| 2     | SV_NO_MEM          | Out of memory                      |
| 3     | SV_BAD_FRAG        | Bad fragment (checksum failed)     |
| 4     | SV_REMOTE_TIME_OUT | Remote end timed out               |
| 5     | SV_N_RETRIES       | Max retries exceeded               |
| 6     | SV_CAN_SEND        | Ready to send                      |
| 7     | SV_CAN_NOT_SEND    | Cannot send (buffer full)          |
| 8     | SV_DISC_PKT_IN     | Disconnect packet received         |
| 9     | SV_CONN_LOST       | Connection lost                    |

### 5.4 SV Keepalive

String at file offset `0x03EEC8`:
```
24 49 27 6D 20 61 6C 69 76 65 21 21 0D 0A
"$I'm alive!!\r\n"
```

The `$` prefix and `\r\n` suffix suggest this is a raw text keepalive
sent outside of SV framing, or it could be a debug marker. The `XX`
string at `0x03EEC4` (2 bytes) may be a placeholder for keepalive
frame headers.

Debug markers found:
- `S` at `0x03EEDC` - Send debug marker
- ` ` (space) at `0x03EEDE` - separator
- `R` at `0x03EEE0` - Receive debug marker

### 5.5 SV Library Source

All SV protocol code originates from `lib_sv.c` (string at `0x03EF1C`).
Key internal structures:
- `NRSV_FragQue` - Fragment queue for send/receive
- `NRSV_FRAG_QUE_SIZE` - Maximum queue size
- `psv->pbSendPtr` - Send buffer pointer
- Fragment size assertion: `size <= 0xFFF` (max 4095 bytes)

---

## 6. Game Message Format (Inside SV Frames)

### 6.1 Wire Format

```
[2 bytes: msg_type (big-endian)] [msg_type - 2 bytes: payload]
```

The `msg_type` value equals the total wire size of the message
(including the 2-byte msg_type header itself).

### 6.2 First Message: LOGIN_REQUEST

- msg_type = `0x019E` (414 decimal)
- Total wire size = 414 bytes (2-byte header + 412-byte payload)
- This is the first message the Saturn sends after SV initialization

### 6.3 Handler Table

197 client receive handlers at file offset `0x0435D8`.
Format: `[2B msg_type] [2B padding] [4B handler_address]`

First few client receive handlers:
| msg_type | Size | Name                    |
|----------|------|-------------------------|
| 0x019F   | 415  | UPDATE_CHARDATA_REQUEST |
| 0x02F9   | 761  | CHARDATA_REQUEST        |
| 0x02D2   | 722  | CHARDATA_REPLY          |
| 0x01AB   | 427  | CHARDATA_NOTICE         |
| 0x0046   |  70  | REGIST_HANDLE_REQUEST   |
| 0x0049   |  73  | SPEAK_REQUEST           |
| 0x004A   |  74  | SPEAK_REPLY             |
| 0x0076   | 118  | SPEAK_NOTICE            |
| 0x019D   | 413  | INFORMATION_NOTICE      |
| 0x01B9   | 441  | CURREGION_NOTICE        |

---

## 7. System Identification Strings

### 7.1 Save File Names
- `DRGNSDRMM` at `0x03D680` - Memory card save file name
- `DRGNSDRMT` at `0x03D68C` - Text data save file name
- `DRGNSDRMSYS` at `0x03FC0C` - System save file name

### 7.2 Game Identifier
- `NRPG0410` at `0x03FC18` - Game ID / version string
  (NRPG = Network RPG, 0410 = version 4.10?)

Used together with `DRGNSDRMSYS` in the save/load system
(references at code offsets `0x02ACB8`/`0x02ACBC`).

---

## 8. Server Implementation Requirements

### 8.1 Minimal BBS Handler

The server must handle this exact sequence after TCP connection:

```
1. WAIT for client to send data (Saturn speaks first!)
2. RECEIVE: " P\r" (0x20 0x50 0x0D)
3. SEND:    "*\r\n" (or any response containing 0x2A)
4. RECEIVE: "SET 1:0,2:0,3:0,4:1,5:0,...,22:0\r"
5. SEND:    "*\r\n"
6. RECEIVE: "C HRPG\r" (0x43 0x20 0x48 0x52 0x50 0x47 0x0D)
7. SEND:    "COM HRPG\r\n" (or any response containing "COM")
8. TRANSITION to SV protocol mode
```

### 8.2 SV Protocol Handler

After BBS login, the server must:

1. Parse SV fragments: `[2B header][payload][2B CRC-16-CCITT]`
2. Validate CRC on each received fragment
3. Reassemble multi-fragment messages
4. Parse game messages: `[2B msg_type][payload]`
5. Compute CRC on outgoing fragments
6. Handle keepalive/timeout (SV_REMOTE_TIME_OUT after inactivity)

### 8.3 CRC-16-CCITT Implementation

```python
CRC_TABLE = [...]  # Standard CRC-16-CCITT table (polynomial 0x1021)

def crc16_ccitt(data, crc=0xFFFF):
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ CRC_TABLE[((crc >> 8) ^ byte) & 0xFF]
    return crc
```

Note: The initial CRC value and whether the final CRC is inverted
needs to be verified from the actual SV code. Standard CCITT uses
initial value 0xFFFF and may or may not invert the result.

### 8.4 Key Timeouts

- BBS response timeout: 10 units per command (from WAIT entries)
- Modem dial timeout: 40 units for CONNECT response
- SV keepalive: periodic `$I'm alive!!\r\n` messages

---

## 9. Response Table Details (Command Table at 0x045C58)

### 9.1 Table Structure

Each command sequence is an array of 12-byte entries:
```
struct CmdEntry {
    uint32_t type;       // 01=SEND, 02=WAIT, 03=END
    uint32_t param;      // SEND: 0, WAIT: timeout, END: 0
    uint32_t ptr;        // SEND: string_ptr, WAIT: resp_table_ptr, END: 0
};
```

### 9.2 Response Tables

Each response table is an array of 8-byte entries:
```
struct RespEntry {
    uint32_t match_str;  // Pointer to match string (0 = end)
    uint32_t handler;    // Handler function (0 = success/continue)
};
```

Response matching is substring-based: the Saturn scans incoming data
for any of the match strings in the table.

### 9.3 Command Sequence Table Entries (file offsets)

| Offset   | Name             | Referenced from code |
|----------|------------------|---------------------|
| 0x045C6C | MODEM_HANGUP     | (inline)            |
| 0x045D3C | MODEM_INIT       | 0x0105B0            |
| 0x045DA8 | BBS_LOGIN_PHASE1 | 0x0105BC            |
| 0x045DD8 | BBS_LOGIN_PHASE2 | 0x0105B8            |
| 0x045DFC | BBS_DISCONNECT   | 0x0107D4            |

### 9.4 Response Tables (file offsets)

| Offset   | Used After         | Success Match | Error Matches          |
|----------|--------------------|---------------|------------------------|
| 0x045C5C | AT (hangup)        | "OK"          | (none)                 |
| 0x045CB4 | AT/ATZ/modem_init  | "OK"          | "ERROR"                |
| 0x045CCC | ATDT dial          | "CONNECT"     | "NO CARRIER","DELAYED","BUSY" |
| 0x045CF4 | " P\r" / "SET"     | "*"           | "NO CARRIER"           |
| 0x045D0C | "C HRPG\r"         | "COM"         | "lear", "NO CARRIER"   |
| 0x045D2C | "OFF\r"            | "NO CARRIER"  | (none)                 |

---

## 10. Critical Notes for Server Development

1. **Server must NOT speak first.** The IV handshake (IV100000)
   approach is wrong. The Saturn waits for no server greeting.

2. **BBS commands use `\r` (0x0D) only** - no `\n` (0x0A) in
   Saturn-sent commands. Server responses can use `\r\n`.

3. **Substring matching** - The Saturn doesn't parse full lines.
   It scans the receive buffer for matching substrings. So
   `"*\r\n"` matches the `"*"` pattern, and `"COM HRPG\r\n"`
   matches the `"COM"` pattern.

4. **The transition from BBS to SV protocol** happens immediately
   after the "COM" response is matched. There is no explicit
   handshake or mode switch command.

5. **SV fragments have CRC-16-CCITT checksums.** The Saturn will
   reject fragments with bad checksums (SV_BAD_FRAG error).

6. **The `::host=` parameter** allows direct TCP connection without
   modem. This is the intended mechanism for DreamPi/revival use.

7. **`NRPG0410`** is the game identifier, possibly used in save
   data headers. The server may need to recognize this.

8. **The `$I'm alive!!\r\n` keepalive** is part of the SV protocol
   layer. The server must either send or respond to keepalive
   messages to prevent SV_REMOTE_TIME_OUT disconnection.
