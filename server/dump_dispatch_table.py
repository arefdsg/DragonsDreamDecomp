#!/usr/bin/env python
"""Dump the complete handler dispatch table from Dragon's Dream 0.BIN"""

import struct
import sys

BINARY_PATH = r"D:\DragonsDreamDecomp\extracted\0.BIN"
TABLE_OFFSET = 0x435D8
NUM_ENTRIES = 197
ENTRY_SIZE = 8
BASE_ADDR = 0x06010000

def main():
    with open(BINARY_PATH, "rb") as f:
        data = f.read()
    
    print(f"Binary size: {len(data)} bytes")
    print(f"Table offset: 0x{TABLE_OFFSET:05X}")
    print(f"Entries: {NUM_ENTRIES}")
    print(f"Table size: {NUM_ENTRIES * ENTRY_SIZE} bytes (0x{NUM_ENTRIES * ENTRY_SIZE:X})")
    print(f"Table end: 0x{TABLE_OFFSET + NUM_ENTRIES * ENTRY_SIZE:05X}")
    print()
    
    entries = []
    
    for i in range(NUM_ENTRIES):
        offset = TABLE_OFFSET + i * ENTRY_SIZE
        msg_type, pad, handler_addr = struct.unpack_from(">HHI", data, offset)
        
        # Calculate file offset of handler
        if handler_addr >= BASE_ADDR:
            handler_file_offset = handler_addr - BASE_ADDR
        else:
            handler_file_offset = None
        
        # Check if handler is RTS stub (0x000B = rts, 0x0009 = nop before rts)
        is_rts = False
        rts_info = ""
        if handler_file_offset is not None and handler_file_offset + 2 <= len(data):
            first_word = struct.unpack_from(">H", data, handler_file_offset)[0]
            if first_word == 0x000B:
                is_rts = True
                rts_info = "RTS"
            elif handler_file_offset + 4 <= len(data):
                second_word = struct.unpack_from(">H", data, handler_file_offset + 2)[0]
                if first_word == 0x0009 and second_word == 0x000B:
                    is_rts = True
                    rts_info = "NOP+RTS"
        
        entries.append({
            "index": i,
            "msg_type": msg_type,
            "pad": pad,
            "handler_addr": handler_addr,
            "handler_file_offset": handler_file_offset,
            "is_rts": is_rts,
            "rts_info": rts_info,
        })
    
    # Print full table
    print("=" * 95)
    print(f"{'Idx':>4}  {'MsgType':>8}  {'Pad':>6}  {'HandlerAddr':>12}  {'FileOffset':>11}  {'Type':>8}")
    print("=" * 95)
    
    for e in entries:
        fo_str = f"0x{e['handler_file_offset']:05X}" if e['handler_file_offset'] is not None else "N/A"
        type_str = e['rts_info'] if e['is_rts'] else "HANDLER"
        print(f"{e['index']:>4}  0x{e['msg_type']:04X}    0x{e['pad']:04X}  0x{e['handler_addr']:08X}    {fo_str}  {type_str:>8}")
    
    print("=" * 95)
    print()
    
    # Summary stats
    rts_count = sum(1 for e in entries if e['is_rts'])
    handler_count = NUM_ENTRIES - rts_count
    print(f"SUMMARY: {NUM_ENTRIES} total entries, {handler_count} real handlers, {rts_count} RTS stubs")
    print()
    
    # Group by msg_type range
    ranges = [
        (0x0000, 0x00FF, "System/Core (0x00xx)"),
        (0x0100, 0x01FF, "Login/Character (0x01xx)"),
        (0x0200, 0x02FF, "Game World (0x02xx)"),
        (0x0300, 0x03FF, "Extended (0x03xx)"),
    ]
    
    print("=" * 70)
    print("FUNCTIONAL CATEGORIES BY MSG_TYPE RANGE")
    print("=" * 70)
    
    for lo, hi, label in ranges:
        group = [e for e in entries if lo <= e['msg_type'] <= hi]
        if not group:
            continue
        rts_in_group = sum(1 for e in group if e['is_rts'])
        real_in_group = len(group) - rts_in_group
        print(f"\n  {label}: {len(group)} entries ({real_in_group} handlers, {rts_in_group} RTS stubs)")
        print(f"  {'MsgType':>8}  {'FileOffset':>11}  {'Type':>8}")
        print(f"  {'-'*35}")
        for e in group:
            fo_str = f"0x{e['handler_file_offset']:05X}" if e['handler_file_offset'] is not None else "N/A"
            type_str = e['rts_info'] if e['is_rts'] else "HANDLER"
            print(f"  0x{e['msg_type']:04X}    {fo_str}  {type_str:>8}")
    
    # Check for any msg_types outside known ranges
    unknown = [e for e in entries if e['msg_type'] > 0x03FF]
    if unknown:
        print(f"\n  UNKNOWN RANGE (>0x03FF): {len(unknown)} entries")
        for e in unknown:
            fo_str = f"0x{e['handler_file_offset']:05X}" if e['handler_file_offset'] is not None else "N/A"
            type_str = e['rts_info'] if e['is_rts'] else "HANDLER"
            print(f"  0x{e['msg_type']:04X}    {fo_str}  {type_str:>8}")
    
    print()
    
    # Print sorted by msg_type for easy lookup
    print("=" * 70)
    print("SORTED BY MSG_TYPE (for quick reference)")
    print("=" * 70)
    sorted_entries = sorted(entries, key=lambda e: e['msg_type'])
    for e in sorted_entries:
        fo_str = f"0x{e['handler_file_offset']:05X}" if e['handler_file_offset'] is not None else "N/A"
        type_str = e['rts_info'] if e['is_rts'] else "HANDLER"
        print(f"  0x{e['msg_type']:04X}  ->  {fo_str}  ({type_str})")
    
    # Check for duplicates
    msg_types = [e['msg_type'] for e in entries]
    seen = {}
    dupes = []
    for e in entries:
        mt = e['msg_type']
        if mt in seen:
            dupes.append((mt, seen[mt], e['index']))
        else:
            seen[mt] = e['index']
    
    if dupes:
        print(f"\nWARNING: {len(dupes)} duplicate msg_types found:")
        for mt, idx1, idx2 in dupes:
            print(f"  0x{mt:04X} at indices {idx1} and {idx2}")
    else:
        print(f"\nNo duplicate msg_types found (all {NUM_ENTRIES} are unique).")
    
    # Validate non-zero pad values
    nonzero_pad = [e for e in entries if e['pad'] != 0]
    if nonzero_pad:
        print(f"\nEntries with non-zero padding:")
        for e in nonzero_pad:
            print(f"  idx={e['index']} msg_type=0x{e['msg_type']:04X} pad=0x{e['pad']:04X}")
    else:
        print("All padding fields are zero (as expected).")

if __name__ == "__main__":
    main()
