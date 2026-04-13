# SV Library (lib_sv.c) - Network Framing Protocol Analysis

## Source File Reference
- Binary: `D:\DragonsDreamDecomp\extracted\0.BIN` (504,120 bytes, SH-2 big-endian)
- SV code regions: 0x012328-0x012540, 0x012540-0x012758, 0x012758-0x012910, 0x012910-0x012978, 0x012A80-0x012D60
- String/constant area: 0x03EEB0-0x03F0C0

---

## 1. CRITICAL FINDING: Text-Encoded Hex Protocol

**The SV library uses a TEXT-BASED protocol, not binary framing.** All fragment headers are sent as ASCII hex-encoded strings terminated by `\r\n`. This is designed for transmission over modem/BBS links where binary data could corrupt control characters.

### Evidence:

1. **"IV" magic prefix** - Fragment headers start with ASCII 'I' (0x49) and 'V' (0x56), confirmed by:
   - Send code at 0x0125AE-0x0125B8: `mov #0x49,r2 / mov.b r2,@r4 / ... / mov #0x56,r2 / mov.b r2,@r4`
   - Receive code at 0x012786: `cmp/eq #0x56,r0` (check for 'V' as second byte)

2. **Hex lookup table** at 0x03F0A4: `"0123456789ABCDEF"` used to convert binary nibbles to ASCII hex characters. Referenced by `mov.b @(r0,r6),r1` where r6 = table base and r0 = nibble index (0-15).

3. **Nibble extraction** at 0x0125C2: `and r5,r0` where r5=0x0F (loaded at 0x0125AA: `mov #15,r5`), followed by 4x `shar r0` to extract the next nibble.

4. **\r\n line termination** - Strings "S", "R", "\r\n" at 0x03EED8/0x03EEE0/0x03EFCC used as line delimiters.

5. **Newline scanning** at 0x012A9A: `cmp/eq #10,r0` (0x0A = LF) scans for line boundaries.

## 2. Key Constants (Confirmed from Binary)

At file offset 0x03EEB8, three 32-bit constants appear in sequence:

| Offset     | Value        | Decimal | Meaning              |
|------------|-------------|---------|----------------------|
| 0x03EEB8   | 0x00000010  | 16      | SV_HEADER_BUF_SIZE   |
| 0x03EEBC   | 0x00000100  | 256     | SV_MAX_FRAG_DATA     |
| 0x03EEC0   | 0x00000800  | 2048    | SV_BUFFER_SIZE       |

Other constants:
- Max message size: 0xFFF = 4095 bytes (from assertion: `size <= 0xfff`)
- Fragment queue: NRSV_FRAG_QUE_SIZE entries (assertion-checked)
- Ring buffer slots: 20 (from `mov #20,r3` and comparison at 0x012A12-0x012A1A)

## 3. Fragment Wire Format

### 3.1 Header Format (CORRECTED 2026-03-11)

**CRITICAL CORRECTION**: Previous analysis claimed `\r\n` was part of the IV header and that
the second 3 hex chars were a "checksum". Both were WRONG. Deep-dive disassembly of both
send and receive state machines confirms:

Each IV frame is:

```
IV<size_hex><complement_hex><raw_binary_payload>
```

Where:
- `IV` = 2-byte ASCII magic prefix (0x49, 0x56)
- `<size_hex>` = 3 lowercase hex chars encoding 12-bit payload size
- `<complement_hex>` = 3 lowercase hex chars encoding `(~size) & 0xFFF`
- `<raw_binary_payload>` = raw binary data (size bytes immediately follow, NO \r\n delimiter)

**Total header: 8 bytes exactly (IV + 6 hex chars). NO \r\n between header and payload.**

The complement provides integrity checking: `size XOR complement == 0xFFF`.

Hex encoding uses lowercase `"0123456789abcdef"` (encode table at 0x06056F5C).
Decoding accepts both cases via `toupper()` + `"0123456789ABCDEF"` (at 0x0604F0A4).

### 3.2 Example IV Headers (CORRECTED)

```
"IV012fed" + 18 bytes payload  → size=0x012 (18),  complement=0xFED, 0x012^0xFED=0xFFF ✓
"IV100eff" + 256 bytes payload → size=0x100 (256), complement=0xEFF, 0x100^0xEFF=0xFFF ✓
"IV002ffd" + 2 bytes payload   → size=0x002 (2),   complement=0xFFD, 0x002^0xFFD=0xFFF ✓
"IV050faf" + 80 bytes payload  → size=0x050 (80),  complement=0xFAF, 0x050^0xFAF=0xFFF ✓
```

### 3.3 NO Multi-Fragment at SV Layer (CORRECTED)

**Previous analysis claimed SV fragments large messages. This was WRONG.**

Each game message gets its own complete IV frame. There is no SV-level fragmentation.
If application-level chunking is needed (e.g., CHARDATA_REPLY multi-page), it happens
at the game message layer — each page is a separate game message with its own IV frame.

Maximum single IV payload: 4095 bytes (12-bit limit). Practical buffer limit: ~2000 bytes.
- Char '0': nibble=0 (bits 3:0 of byte 1)

This gives: byte0=0x01, byte1=0x00, first_field=0x010 = 16? Or if MSB-first: 0x100 = 256.

**IMPORTANT**: The exact nibble ordering needs live-testing to confirm. The send code writes low nibble first (`and r5,r0` before shifting), but the function call between writes may reorder values. The most likely format is standard big-endian hex (MSB first), giving:
- "100" = 0x100 = 256
- "000" = 0x000 = 0

### 3.3 Special Line Types

The protocol distinguishes lines by their prefix character after newline:

| Prefix | Meaning                    | Format                           |
|--------|----------------------------|----------------------------------|
| `I`    | Fragment header ("IV...")   | `IV<6 hex chars>\r\n<payload>`   |
| `$`    | Keepalive                  | `$I'm alive!!\r\n`              |
| `S`    | Send debug marker          | `S<data>\r\n`                    |
| `R`    | Receive debug marker       | `R<data>\r\n`                    |
| `E`    | Error notification         | `E<data>\r\n`                    |

The receive scanner at 0x012A90-0x012A9C looks for 0x0A (LF) as the line delimiter. When found, the next byte determines the line type.

## 4. Keepalive Mechanism

### 4.1 Keepalive String
```
Offset 0x03EEC8: "$I'm alive!!\r\n"  (15 bytes with terminator)
```

### 4.2 Detection

The keepalive is detected by checking the first character after a line boundary:
- Code at 0x012808: `cmp/eq #0x49,r0` checks for 'I' (but keepalive starts with '$')
- Code at 0x012710-0x012718: `cmp/eq #0x49,r0` checks for 'I'

This 'I' check at 0x012808 appears AFTER processing a received header, suggesting it detects the *response* to a keepalive (which would start with 'I' for "IV..."), or the keepalive itself may be an "IV" frame with special data.

**Most likely**: The keepalive `$I'm alive!!\r\n` is sent as a RAW text line (not inside an IV frame). The '$' prefix distinguishes it from data frames.

### 4.3 Timing

Value `0x0252` (594) found at 0x012748 may be the timeout in VBL ticks:
- At 60fps: 594/60 = ~10 seconds
- At 30fps: 594/30 = ~20 seconds

The server should send keepalives every 5-8 seconds to stay well within the timeout window.

### 4.4 "XX" Sentinel

At 0x03EEC4: the string "XX" appears right before the keepalive. This may be a placeholder or "dead" marker used during initialization. The init code writes 'X' characters as placeholders before real data is available.

## 5. Integrity Checking (CORRECTED 2026-03-11)

### 5.1 SV Layer: Size Complement (NOT Checksum)

**CORRECTION**: The 0x0FFF mask is for the payload SIZE field, not a checksum.
The second 3-hex-char field in the IV header is `(~payload_size) & 0xFFF` — a bitwise
complement of the size. This provides a simple integrity check on the size field itself.

There is NO data checksum at the SV framing layer.

Verification on receive:
1. Parse 3 hex chars → size
2. Parse 3 hex chars → complement
3. Check: `size ^ complement == 0xFFF`
4. If mismatch: reject frame

### 5.2 Application Layer: Byte Sum Checksum (at 0x060429B6)

A SEPARATE checksum exists at the application protocol layer (above SV framing):
- Function at `0x060429B6`: simple additive byte sum (`sum(bytes) & 0xFFFF`)
- 4-byte text field at message offset [2:6], formatted as `%04X` uppercase hex
- Verification: parse hex at [2:6], zero bytes [2:6], compute byte_sum, compare

**NOTE**: The relationship of this application checksum to the game wire format is
UNCERTAIN. It may apply to a sub-protocol or specific message types, not all messages.
The SCMD send path does NOT call this checksum function. Further investigation needed.

## 6. Message Queuing (CORRECTED — No Fragmentation)

### 6.1 Send Queue

The SV layer maintains a send queue at `0x060623D8`:
- Max 20 entries, each 8 bytes: `[4B data_pointer, 4B size]`
- Messages are dequeued FIFO and sent one at a time
- Each dequeued message gets its own complete IV frame

### 6.2 Receive State Machine (from detailed disassembly)

Receive state stored at `state_struct + 28`:

**State 0 (Waiting for IV)**:
- Byte-by-byte: expects 'I' (0x49), then 'V' (0x56)
- If unexpected byte but == 'I', restarts as potential new frame

**State 1 (Parsing Hex Digits)**:
- Receives 6 hex chars, uppercased via toupper()
- First 3 → payload_size (shift-left-4 + add accumulator at state+0x7F0)
- Last 3 → complement (consumed but not stored separately)
- After 6 digits → State 2

**State 2 (Receiving Payload)**:
- Receives exactly `size` bytes of raw data into buffer at state+0x20
- Counter at state+0x7F2 tracks bytes received
- When complete: delivers to application via function at `0x060423C8`
- Resets to State 0

### 6.3 Delivery

Complete payload delivered to `0x06062314` (destination buffer).
Application dispatch reads msg_type from buffer[2:4] and routes to handler.

## 7. Connection State Machine

### 7.1 States

The SV library tracks connection state at offset 8 of the state structure:

| Value | State         | Description                                  |
|-------|---------------|----------------------------------------------|
| 0     | CLOSED        | Not initialized / disconnected               |
| 1     | OPENING       | Connection established, handshake in progress |
| 2     | CONNECTED     | Fully connected, data transfer active        |

### 7.2 State Transitions

Code at 0x0123D0-0x012400 checks state:
```
0x0123D0: mov.l @(8,r14),r0    ; load state
0x0123D2: tst r0,r0            ; state == 0?  -> CLOSED
0x0123E4: mov.l @(8,r14),r0
0x0123E6: cmp/eq #1,r0         ; state == 1?  -> OPENING
0x0123F8: mov.l @(8,r14),r0
0x0123FA: cmp/eq #2,r0         ; state == 2?  -> CONNECTED
```

Transition code at 0x012640:
```
mov.l r10,@(8,r14)    ; store state = 2 (r10 was loaded with 2 at 0x012624)
```

This transition from 1 to 2 happens after successfully exchanging initial IV headers.

### 7.3 Connection Handshake (CORRECTED 2026-03-11)

**There is NO separate SV-layer handshake.** After BBS commands (SET/C HRPG),
the protocol is symmetric and message-driven:

1. Server WAITS for client to speak first
2. Client queues its first game message and sends it as an IV frame
3. Server receives the IV frame, processes the game message, sends response
4. Normal message exchange continues
3. After successful exchange, state transitions to 2 (CONNECTED)
4. Normal data and keepalive exchange begins

The init function at 0x012478 initializes the SV structure with:
- Space characters (0x20) as field placeholders
- 'C' and ':' characters (possibly "C:" prefix for command mode)
- Zero counters and null pointers

## 8. SV State Structure Layout

| Offset | Size  | Field            | Description                              |
|--------|-------|------------------|------------------------------------------|
| 0      | 4     | queueIndex       | Ring buffer write index (wraps at 20)    |
| 4      | 4     | queueReadIndex   | Ring buffer read index                   |
| 8      | 4     | connState        | Connection state (0/1/2)                 |
| 12     | 12    | headerBuf        | Temp buffer for building "IVxxxxxx\r\n"  |
| 24     | 2     | totalFragCount   | Expected fragments for current message   |
| 26     | 2     | recvFragCount    | Fragments received so far                |
| 28     | 4     | lastResult       | Last operation result / error code       |
| 32+    | var   | sendRecvBufs     | Send/receive data buffers (2048 each)    |

The structure also contains fields at large offsets (2034, 2036, etc.) which correspond to positions within the 2048-byte buffers:
- Offset ~2034: Near end of first buffer (2048 - 14 = 2034)
- Offset ~2036: Buffer boundary marker

## 9. Error Codes

| Code | Name              | Meaning                                      |
|------|-------------------|----------------------------------------------|
| 0    | SV_OK             | Success                                      |
| 1    | SV_NOT_OPEN       | Connection not opened                        |
| 2    | SV_NO_MEM         | Memory allocation failed                     |
| 3    | SV_BAD_FRAG       | Checksum mismatch on received fragment       |
| 4    | SV_REMOTE_TIME_OUT| No data received within timeout (~10 sec)    |
| 5    | SV_N_RETRIES      | Too many retransmission attempts             |
| 6    | SV_CAN_SEND       | Ready to send (status, not error)            |
| 7    | SV_CAN_NOT_SEND   | Send buffer full                             |
| 8    | SV_DISC_PKT_IN    | Disconnect packet received                   |
| 9    | SV_CONN_LOST      | Connection lost (carrier lost)               |

Assertions:
```
ASSERTION FAILED: nrsv_err == SV_OK FILE lib_sv.c, LINE %d
ASSERTION FAILED: nrsv_err == SV_OK || nrsv_err == SV_NO_MEM FILE lib_sv.c, LINE %d
ASSERTION FAILED: psv->pbSendPtr != NULL FILE lib_sv.c, LINE %d
ASSERTION FAILED: NRSV_FragQue.dwSize < NRSV_FRAG_QUE_SIZE FILE lib_sv.c, LINE %d
ASSERTION FAILED: size <= 0xfff FILE lib_sv.c, LINE %d
```

## 10. Debug/Diagnostic Strings

| Offset     | String                  | Purpose                        |
|-----------|-------------------------|--------------------------------|
| 0x03EEC4  | "XX"                    | Placeholder/sentinel           |
| 0x03EEC8  | "$I'm alive!!\r\n"      | Keepalive string               |
| 0x03EED8  | "S"                     | Send direction marker (debug)  |
| 0x03EEDC  | " " (space)             | Separator (debug)              |
| 0x03EEE0  | "R"                     | Receive direction marker       |
| 0x03EFC4  | "E"                     | Error marker                   |
| 0x03EFC8  | "R:"                    | Receive prefix (debug output)  |
| 0x03EFCC  | "\r\n"                  | Line terminator                |
| 0x03EF1C  | "lib_sv.c"              | Source filename for assertions |
| 0x03EF28  | "FragQue full\n\r"      | Queue overflow warning         |
| 0x03F058  | "#sv error occured\r\n" | Error notification             |
| 0x03F068  | "================"      | Debug separator                |
| 0x03F07C  | ">>>>>>>>>>>>>>>>"      | Debug send direction           |
| 0x03F090  | "<<<<<<<<<<<<<<<<<"     | Debug receive direction        |
| 0x03F0A4  | "0123456789ABCDEF"      | Hex encoding lookup table      |

## 11. Wire Protocol Summary for Server Implementation (CORRECTED 2026-03-11)

### 11.1 Protocol Stack

```
+------------------------------------------+
| Game Messages (LOGIN_REQUEST, etc.)       |
| [2B param1][2B msg_type][4B size][payload]|
+------------------------------------------+
| SV Framing Layer (lib_sv.c)              |
| Each message wrapped in one IV frame     |
| "IV" + 3hex(size) + 3hex(~size) + data   |
+------------------------------------------+
| Keepalive ("$I'm alive!!\r\n")           |
+------------------------------------------+
| TCP / Modem byte stream                  |
+------------------------------------------+
```

### 11.2 Server Must Implement

1. **IV Frame Encoding** (to send a message):
   ```python
   def send_iv_frame(sock, payload: bytes):
       size = len(payload)
       complement = (~size) & 0xFFF
       header = f"IV{size:03x}{complement:03x}".encode('ascii')  # 8 bytes
       sock.sendall(header + payload)
   ```

2. **IV Frame Parsing** (to receive a message):
   - Scan byte-by-byte for 'I' (0x49), then 'V' (0x56)
   - Read 6 hex chars: first 3 → size, last 3 → complement
   - Validate: `size ^ complement == 0xFFF`
   - Read exactly `size` bytes of raw binary payload

3. **NO fragmentation needed** — each game message = one IV frame

4. **Keepalive**:
   - Send `$I'm alive!!\r\n` every 5-8 seconds
   - Detect incoming keepalives (bytes starting with '$')
   - The '$' prefix distinguishes keepalives from IV frames ('I' prefix)

5. **Connection Flow**:
   ```
   [Modem CONNECT / TCP established]
   <- Client sends: " P\r"
   -> Server responds: "*\r\n"
   <- Client sends: "SET\r"
   -> Server responds: "*\r\n"
   <- Client sends: "C HRPG\r"
   -> Server responds: "COM HRPG\r\n"
   [SV Layer Active — NO separate handshake]
   <- Client sends first IV frame (game message)
   -> Server parses and responds with IV frame
   [Normal message exchange + keepalives]
   ```

6. **Timeouts**:
   - Client expects data within ~10 seconds (594 VBL ticks at 60fps)
   - Must send keepalive or data before timeout expires

### 11.3 Complete Server Example

```python
import struct

def build_game_message(msg_type: int, payload: bytes) -> bytes:
    """Build 8-byte header + payload for a game message."""
    param1 = 0
    header = struct.pack('>HHI', param1, msg_type, len(payload))
    return header + payload

def wrap_iv_frame(message: bytes) -> bytes:
    """Wrap a game message in an SV IV frame."""
    size = len(message)
    complement = (~size) & 0xFFF
    iv_header = f"IV{size:03x}{complement:03x}".encode('ascii')
    return iv_header + message

def send_game_message(sock, msg_type: int, payload: bytes):
    """Build game message, wrap in IV frame, send."""
    game_msg = build_game_message(msg_type, payload)
    frame = wrap_iv_frame(game_msg)
    sock.sendall(frame)

# Example: Send ESP_NOTICE (0x01E8) with 51-byte payload
esp_payload = struct.pack('>HH', 0, session_param) + ... # 51 bytes
send_game_message(sock, 0x01E8, esp_payload)
```

## 12. Resolved Questions (2026-03-11)

1. **Hex encoding**: Standard lowercase hex (confirmed from encode table "0123456789abcdef").
   Decode accepts both cases via toupper().

2. **"Checksum" field**: It's NOT a checksum — it's `(~size) & 0xFFF`, a bitwise complement
   of the size field for integrity checking.

3. **Fragment tracking**: N/A — there is NO fragmentation at the SV layer.
   Each message = one IV frame. Application-level chunking (CHARDATA_REPLY pages) uses
   separate game messages.

4. **Connection handshake**: NO SV-layer handshake. After BBS commands, server WAITS
   for client to send first IV frame.

5. **"S", "R", "E" prefix lines**: Debug output only, NOT sent on the wire.

6. **Binary payload**: Raw binary bytes follow the 8-byte IV header directly.
   NOT hex-encoded.

7. **Keepalive format variant**: The exact byte sequence for keepalive -- is it `$I'm alive!!\r\n` literally, or could the '$' be an IV header variant? The '$' (0x24) is NOT 'I' (0x49), so the 'I' check at 0x012808 might indicate data frames are distinguished from keepalives by the first character.

## 13. RAM Addresses (SV Global Variables)

Frequently referenced RAM addresses in SV literal pools:

| Address      | Frequency | Likely Purpose                   |
|-------------|-----------|----------------------------------|
| 0x0604EF1C  | Very high | SV state structure base          |
| 0x0604EF88  | High      | SV secondary state / recv buf    |
| 0x0604EFC4  | Medium    | SV send state                    |
| 0x0604EFC8  | Medium    | SV send state field              |
| 0x0604EFCC  | Medium    | SV send state field              |
| 0x0604EFD0  | Medium    | SV connection indicator          |
| 0x0604EEDC  | Medium    | SV config data                   |
| 0x0604EEE4  | Medium    | SV config field                  |
| 0x0604EF28  | Medium    | SV state alternate ref           |
| 0x0604EF38  | Low       | SV state field                   |
| 0x06069508  | High      | Debug print function             |
| 0x0603FE28  | High      | Memory alloc / shared function   |
| 0x06020D70  | High      | I/O handler function             |
| 0x060623E0  | Medium    | Shared utility function          |
| 0x06062374  | Medium    | Shared utility function          |
| 0x06062484  | Medium    | Shared utility function          |
| 0x06062490  | Medium    | Shared utility function          |
| 0x060623D8  | Medium    | Shared utility function          |
