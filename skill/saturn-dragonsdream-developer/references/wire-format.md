# Dragon's Dream Wire Format — CORRECTED Analysis

## Binary: `D:\DragonsDreamDecomp\extracted\0.BIN` (504,120 bytes, SH-2 big-endian)
## Date: 2026-03-11, UPDATED with corrections

---

## 1. Message Wire Format (CONFIRMED)

Every game message on the wire has an **8-byte header** followed by payload:

```
Offset  Size  Field          Description
------  ----  -----          -----------
0       2     param1         Usually 0x0000 (purpose unclear, ignored by dispatch)
2       2     msg_type       Message type identifier (uint16 BE) — NOT the wire size!
4       4     payload_size   Payload byte count (uint32 BE) — actual number of payload bytes
8       N     payload        Application data (N = payload_size bytes)
```

**Total wire size = 8 + payload_size**
**msg_type is a unique identifier, NOT equal to wire size!**

### CRITICAL CORRECTION (2026-03-11 UPDATE):
Previous analysis claimed msg_type = total wire size. **THIS WAS WRONG.**

Evidence:
- LOGIN_REQUEST: msg_type=0x019E (414), actual payload=60B, wire=68B
- CHARDATA2_NOTICE (client-sent): msg_type=0x0B6C (2924), actual payload=16B, wire=24B
- STANDARD_REPLY: msg_type=0x0048 (72), payload=VARIABLE (takes length parameter)

The msg_type values in the message table (0x04612C) are unique message identifiers
that happen to increase monotonically. They are NOT sizes.

### Key Implications:
- Messages can have VARIABLE payload sizes (e.g., STANDARD_REPLY)
- The payload_size header field is authoritative for determining how much data to read
- Server must read payload_size from header[4:8] to know message boundaries
- The same msg_type can carry different payload sizes depending on direction/context

---

## 2. Evidence: SCMD Library Send Path

### 2.1 scmd_new_message (file 0x149EC, mem 0x060249EC)

Called with r4=param1 (usually 0), r5=msg_type:

```
buffer[0:2] = param1      (mov.w r2,@r14)
buffer[2:4] = msg_type    (mov.w r0,@(2,r14))
buffer[4:8] = 0x00000000  (mov.l r4,@(4,r14) where r4=0)
nMsgSize = 0              (mov.l r4,@r3 where r4=0, r3=nMsgSize_ptr)
SV_context[6] = msg_type  (mov.w r0,@(6,r2))
```

Send buffer base address: 0x202E6148 (Work RAM-L, cache-through)
nMsgSize global variable: 0x06062498

### 2.2 scmd_add_byte (file 0x14A32, mem 0x06024A32)

Writes a single byte at `buffer + 8 + nMsgSize`, then increments nMsgSize.
Assertion: `nMsgSize + 1 < MAXMSGBUF_SIZE` (4800 bytes max)

### 2.3 scmd_add_word (file 0x14B04, mem 0x06024B04)

Writes 2 bytes (uint16 BE) at `buffer + 8 + nMsgSize`, then nMsgSize += 2.
Assertion: `nMsgSize + 2 < MAXMSGBUF_SIZE`

### 2.4 scmd_add_long (file 0x14BDC, mem 0x06024BDC)

Writes 4 bytes (uint32 BE) at `buffer + 8 + nMsgSize`, then nMsgSize += 4.
Assertion: `nMsgSize + 4 < MAXMSGBUF_SIZE`

### 2.5 scmd_add_data (file 0x14CD0, mem 0x06024CD0)

Copies N bytes from source at `buffer + 8 + nMsgSize`, then nMsgSize += N.
Called with r4=source_ptr, r5=length.
Assertion: `nMsgSize + length < MAXMSGBUF_SIZE`

### 2.6 scmd_send (file 0x14E3C, mem 0x06024E3C)

Sets payload_size in header and calls SV layer:

```
buffer[4:8] = nMsgSize     (mov.l r2,@(4,r14) — overwrites the zeros with actual payload size)
r5 = nMsgSize + 8          (add #8,r5 — total wire size = header + payload)
r4 = buffer_base           (mov r14,r4)
jmp SV_send(r4, r5)        (jmp @r2 where r2 = 0x060222CC)
```

SV_context[14] = 0x0E10 (3600) — probably timeout value in ms

### 2.7 SV send function (file 0x122CC, mem 0x060222CC)

Takes r4=data_ptr, r5=total_size. Enqueues the data for SV fragmentation
starting from r4[0] through r4[r5-1]. ALL 8 header bytes are included.

---

## 3. Evidence: Dispatch Receive Path

### 3.1 Primary dispatch (file 0x3420, mem 0x06013420)

```
r12 = receive_buffer_ptr   (mov r4,r12)
msg_type = buffer[2:4]     (mov.w @(2,r12),r0)

For each handler table entry:
  if entry.msg_type == received_msg_type:
    r4 = r12               (mov r12,r4)
    call handler            (jsr @r2)
    r4 += 8                 (add #8,r4 — DELAY SLOT, executes before handler)
```

Handlers receive r4 = buffer + 8 = pointer to payload data.
Dispatch does NOT read payload_size from header[4:8].

---

## 4. param1 Analysis

param1 is usually 0. The dispatch function does NOT read buffer[0:2].
For LOGIN_REQUEST, param1 comes from SV_context[0x0264] (not always 0).

**For server implementation: set param1 = 0 for all messages.**

---

## 5. Verified Payload Sizes (from SCMD send code analysis)

| Message | msg_type | Client Payload | Notes |
|---------|----------|---------------|-------|
| (unknown) | 0x0035 | ~37B | 8B data + ~24B + 2B word + 3B bytes |
| LOGIN_REQUEST | 0x019E | 60B | Fixed layout: 2W+16D+12B+2L+4B+16B |
| CHARDATA2_NOTICE | 0x0B6C | 16B | Just 16 bytes of data (client-sent) |
| STANDARD_REPLY | 0x0048 | VARIABLE | Takes (length, data_ptr) params + 1 zero byte |
| UPDATE_CHARDATA_REPLY | 0x01AA | ~20B | 1W + 5W + scmd_send |

### NOTE: Server-sent payloads may differ from client-sent!
The same msg_type could carry different payload sizes depending on
which side sends it. The receiver uses payload_size from the header.

---

## 6. Server Implementation Requirements

To send a message from the server:

```python
def build_wire_message(msg_type: int, payload: bytes) -> bytes:
    param1 = 0
    payload_size = len(payload)
    header = struct.pack('>HHI', param1, msg_type, payload_size)
    return header + payload
```

To parse a message received from the client:

```python
def parse_wire_message(data: bytes) -> tuple:
    param1, msg_type, payload_size = struct.unpack('>HHI', data[:8])
    payload = data[8:8+payload_size]
    return msg_type, payload
```

**IMPORTANT:** Do NOT assume payload_size = msg_type - 8.
Use the actual payload_size field from the header.

The SV framing layer wraps these wire messages in IV fragments.
