"""
Protocol encoding/decoding: SV IV framing, game message building, utilities.
Verbatim from v3 — DO NOT MODIFY wire format logic.
"""
import struct


def sv_encode(payload: bytes) -> bytes:
    """Wrap payload in IV frame: 8-byte header + raw data. NO \\r\\n."""
    size = len(payload)
    if size > 4095:
        raise ValueError(f"IV payload too large: {size} > 4095")
    complement = (~size) & 0xFFF
    header = f"IV{size:03x}{complement:03x}".encode('ascii')
    return header + payload


def build_game_msg(msg_type: int, payload: bytes = b'', param1: int = 0) -> bytes:
    """Build game message: [2B param1][2B msg_type][4B payload_size][payload]"""
    header = struct.pack('>HHI', param1, msg_type, len(payload))
    return header + payload


def parse_game_msg(data: bytes):
    """Parse game message. Returns (msg_type, payload, param1) or (None,None,None)."""
    if len(data) < 8:
        return None, None, None
    param1, msg_type, payload_size = struct.unpack('>HHI', data[:8])
    payload = data[8:8 + payload_size]
    return msg_type, payload, param1


def sjis_pad(text: str, size: int) -> bytes:
    """Encode text as Shift-JIS, pad/truncate to exact size with null bytes."""
    try:
        encoded = text.encode('shift_jis')
    except (UnicodeEncodeError, LookupError):
        encoded = text.encode('ascii', errors='replace')
    if len(encoded) >= size:
        return encoded[:size]
    return encoded + b'\x00' * (size - len(encoded))


def hexdump(data: bytes, prefix: str = "") -> str:
    """Short hex dump for logging."""
    if len(data) <= 32:
        return prefix + data.hex()
    return prefix + data[:32].hex() + f"... ({len(data)} bytes total)"


def full_hexdump(data: bytes, label: str = "") -> str:
    """Full multi-line hex dump with ASCII for protocol debugging."""
    lines = [f"--- {label} ({len(data)} bytes) ---"]
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  {i:04X}: {hex_part:<48s}  {ascii_part}")
    return '\n'.join(lines)
