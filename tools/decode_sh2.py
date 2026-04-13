#!/usr/bin/env python3
"""SH-2 instruction decoder for Dragon's Dream binary analysis."""

import struct
import sys

with open('extracted/0.BIN', 'rb') as f:
    DATA = f.read()

BASE = 0x06010000

def read_u16(offset):
    return struct.unpack('>H', DATA[offset:offset+2])[0]

def read_u32(offset):
    return struct.unpack('>I', DATA[offset:offset+4])[0]

def decode_sh2(start_offset, count=120):
    pc = BASE + start_offset
    lines = []
    i = 0
    off = start_offset
    while i < count:
        if off + 2 > len(DATA):
            break
        insn = read_u16(off)
        desc = decode_one(insn, pc, off)
        lines.append("  0x%08X [0x%05X]  %04X  %s" % (pc, off, insn, desc))
        off += 2
        pc += 2
        i += 1
    return lines

def decode_one(insn, pc, off):
    hi4 = (insn >> 12) & 0xF
    hi8 = (insn >> 8) & 0xFF
    lo4 = insn & 0xF
    lo8 = insn & 0xFF
    rn = (insn >> 8) & 0xF
    rm = (insn >> 4) & 0xF

    # Special single instructions
    if insn == 0x000B: return "RTS"
    if insn == 0x0009: return "NOP"
    if insn == 0x002B: return "RTE"
    if insn == 0x0008: return "CLRT"
    if insn == 0x0018: return "SETT"
    if insn == 0x0028: return "CLRMAC"
    if insn == 0x0019: return "DIV0U"
    if insn == 0x001B: return "SLEEP"

    # MOV.L @(disp,PC),Rn
    if hi4 == 0xD:
        disp = lo8
        addr = ((pc + 4) & ~3) + disp * 4
        foff = addr - BASE
        if 0 <= foff < len(DATA) - 3:
            val = read_u32(foff)
            return "MOV.L @(0x%08X),R%d  ; =0x%08X" % (addr, rn, val)
        return "MOV.L @(0x%08X),R%d" % (addr, rn)

    # MOV.W @(disp,PC),Rn
    if hi4 == 0x9:
        disp = lo8
        addr = (pc + 4) + disp * 2
        foff = addr - BASE
        if 0 <= foff < len(DATA) - 1:
            val = read_u16(foff)
            return "MOV.W @(0x%08X),R%d  ; =0x%04X" % (addr, rn, val)
        return "MOV.W @(0x%08X),R%d" % (addr, rn)

    # MOV #imm,Rn
    if hi4 == 0xE:
        imm = lo8
        if imm > 127: imm -= 256
        return "MOV #%d,R%d" % (imm, rn)

    # ADD #imm,Rn
    if hi4 == 0x7:
        imm = lo8
        if imm > 127: imm -= 256
        return "ADD #%d,R%d" % (imm, rn)

    # 0x6xxx
    if hi4 == 0x6:
        ops = {0:"MOV.B @R%d,R%d", 1:"MOV.W @R%d,R%d", 2:"MOV.L @R%d,R%d", 3:"MOV R%d,R%d",
               4:"MOV.B @R%d+,R%d", 5:"MOV.W @R%d+,R%d", 6:"MOV.L @R%d+,R%d", 7:"NOT R%d,R%d",
               8:"SWAP.B R%d,R%d", 9:"SWAP.W R%d,R%d", 0xA:"NEGC R%d,R%d", 0xB:"NEG R%d,R%d",
               0xC:"EXTU.B R%d,R%d", 0xD:"EXTU.W R%d,R%d", 0xE:"EXTS.B R%d,R%d", 0xF:"EXTS.W R%d,R%d"}
        if lo4 in ops:
            return ops[lo4] % (rm, rn)

    # 0x2xxx
    if hi4 == 0x2:
        ops = {0:"MOV.B R%d,@R%d", 1:"MOV.W R%d,@R%d", 2:"MOV.L R%d,@R%d",
               4:"MOV.B R%d,@-R%d", 5:"MOV.W R%d,@-R%d", 6:"MOV.L R%d,@-R%d",
               7:"DIV0S R%d,R%d", 8:"TST R%d,R%d", 9:"AND R%d,R%d", 0xA:"XOR R%d,R%d",
               0xB:"OR R%d,R%d", 0xC:"CMP/STR R%d,R%d", 0xD:"XTRCT R%d,R%d",
               0xE:"MULU.W R%d,R%d", 0xF:"MULS.W R%d,R%d"}
        if lo4 in ops:
            return ops[lo4] % (rm, rn)

    # 0x3xxx
    if hi4 == 0x3:
        ops = {0:"CMP/EQ R%d,R%d", 2:"CMP/HS R%d,R%d", 3:"CMP/GE R%d,R%d",
               4:"DIV1 R%d,R%d", 5:"DMULU.L R%d,R%d", 6:"CMP/HI R%d,R%d",
               7:"CMP/GT R%d,R%d", 8:"SUB R%d,R%d", 0xA:"SUBC R%d,R%d",
               0xC:"ADD R%d,R%d", 0xD:"DMULS.L R%d,R%d", 0xE:"ADDC R%d,R%d",
               0xF:"ADDV R%d,R%d"}
        if lo4 in ops:
            return ops[lo4] % (rm, rn)

    # 0x8xxx
    if hi4 == 0x8:
        subop = (insn >> 8) & 0xF
        if subop == 0x0:
            return "MOV.B R0,@(%d,R%d)" % (insn & 0xF, rm)
        if subop == 0x1:
            return "MOV.W R0,@(%d,R%d)" % ((insn & 0xF) * 2, rm)
        if subop == 0x4:
            return "MOV.B @(%d,R%d),R0" % (insn & 0xF, rm)
        if subop == 0x5:
            return "MOV.W @(%d,R%d),R0" % ((insn & 0xF) * 2, rm)
        if subop == 0x8:
            imm = lo8
            if imm > 127: imm -= 256
            return "CMP/EQ #%d,R0" % imm
        if subop == 0x9:
            disp = lo8
            if disp > 127: disp -= 256
            return "BT 0x%08X" % (pc + 4 + disp * 2)
        if subop == 0xB:
            disp = lo8
            if disp > 127: disp -= 256
            return "BF 0x%08X" % (pc + 4 + disp * 2)
        if subop == 0xD:
            disp = lo8
            if disp > 127: disp -= 256
            return "BT/S 0x%08X" % (pc + 4 + disp * 2)
        if subop == 0xF:
            disp = lo8
            if disp > 127: disp -= 256
            return "BF/S 0x%08X" % (pc + 4 + disp * 2)

    # MOV.L Rm,@(disp,Rn)
    if hi4 == 0x1:
        return "MOV.L R%d,@(%d,R%d)" % (rm, lo4 * 4, rn)

    # MOV.L @(disp,Rm),Rn
    if hi4 == 0x5:
        return "MOV.L @(%d,R%d),R%d" % (lo4 * 4, rm, rn)

    # BRA
    if hi4 == 0xA:
        disp = insn & 0xFFF
        if disp > 0x7FF: disp -= 0x1000
        return "BRA 0x%08X" % (pc + 4 + disp * 2)

    # BSR
    if hi4 == 0xB:
        disp = insn & 0xFFF
        if disp > 0x7FF: disp -= 0x1000
        return "BSR 0x%08X" % (pc + 4 + disp * 2)

    # 0x4xxx
    if hi4 == 0x4:
        sublo = lo8
        if sublo == 0x0B: return "JSR @R%d" % rn
        if sublo == 0x2B: return "JMP @R%d" % rn
        if sublo == 0x0E: return "LDC R%d,SR" % rn
        if sublo == 0x1E: return "LDC R%d,GBR" % rn
        if sublo == 0x2E: return "LDC R%d,VBR" % rn
        if sublo == 0x07: return "LDC.L @R%d+,SR" % rn
        if sublo == 0x17: return "LDC.L @R%d+,GBR" % rn
        if sublo == 0x0A: return "LDS R%d,MACH" % rn
        if sublo == 0x1A: return "LDS R%d,MACL" % rn
        if sublo == 0x2A: return "LDS R%d,PR" % rn
        if sublo == 0x06: return "LDS.L @R%d+,MACH" % rn
        if sublo == 0x16: return "LDS.L @R%d+,MACL" % rn
        if sublo == 0x26: return "LDS.L @R%d+,PR" % rn
        if sublo == 0x03: return "STC SR,R%d" % rn  # Note: varies by variant
        if sublo == 0x13: return "STC GBR,R%d" % rn
        if sublo == 0x23: return "STC VBR,R%d" % rn
        if sublo == 0x02: return "STS.L MACH,@-R%d" % rn
        if sublo == 0x12: return "STS.L MACL,@-R%d" % rn
        if sublo == 0x22: return "STS.L PR,@-R%d" % rn
        if sublo == 0x15: return "CMP/PL R%d" % rn
        if sublo == 0x11: return "CMP/PZ R%d" % rn
        if sublo == 0x10: return "DT R%d" % rn
        if sublo == 0x00: return "SHLL R%d" % rn
        if sublo == 0x01: return "SHLR R%d" % rn
        if sublo == 0x04: return "ROTL R%d" % rn
        if sublo == 0x05: return "ROTR R%d" % rn
        if sublo == 0x20: return "SHAL R%d" % rn
        if sublo == 0x21: return "SHAR R%d" % rn
        if sublo == 0x08: return "SHLL2 R%d" % rn
        if sublo == 0x09: return "SHLR2 R%d" % rn
        if sublo == 0x18: return "SHLL8 R%d" % rn
        if sublo == 0x19: return "SHLR8 R%d" % rn
        if sublo == 0x28: return "SHLL16 R%d" % rn
        if sublo == 0x29: return "SHLR16 R%d" % rn
        if sublo == 0x24: return "ROTCL R%d" % rn
        if sublo == 0x25: return "ROTCR R%d" % rn
        if lo4 == 0xC: return "SHAD R%d,R%d" % (rm, rn)
        if lo4 == 0xD: return "SHLD R%d,R%d" % (rm, rn)
        if lo4 == 0xF: return "MAC.W @R%d+,@R%d+" % (rm, rn)

    # 0xCxxx GBR-relative
    if hi8 == 0xC4: return "MOV.B @(%d,GBR),R0" % lo8
    if hi8 == 0xC5: return "MOV.W @(%d,GBR),R0" % (lo8 * 2)
    if hi8 == 0xC6: return "MOV.L @(%d,GBR),R0" % (lo8 * 4)
    if hi8 == 0xC0: return "MOV.B R0,@(%d,GBR)" % lo8
    if hi8 == 0xC1: return "MOV.W R0,@(%d,GBR)" % (lo8 * 2)
    if hi8 == 0xC2: return "MOV.L R0,@(%d,GBR)" % (lo8 * 4)
    if hi8 == 0xC8: return "TST #0x%02X,@(R0,GBR)" % lo8
    if hi8 == 0xC9: return "AND #0x%02X,@(R0,GBR)" % lo8
    if hi8 == 0xCA: return "XOR #0x%02X,@(R0,GBR)" % lo8
    if hi8 == 0xCB: return "OR #0x%02X,@(R0,GBR)" % lo8
    if hi8 == 0xC7:
        addr = ((pc + 4) & ~3) + lo8 * 4
        return "MOVA @(0x%08X),R0" % addr

    # 0x0xxx misc
    if hi4 == 0x0:
        if lo4 == 0x4: return "MOV.B R%d,@(R0,R%d)" % (rm, rn)
        if lo4 == 0x5: return "MOV.W R%d,@(R0,R%d)" % (rm, rn)
        if lo4 == 0x6: return "MOV.L R%d,@(R0,R%d)" % (rm, rn)
        if lo4 == 0xC: return "MOV.B @(R0,R%d),R%d" % (rm, rn)
        if lo4 == 0xD: return "MOV.W @(R0,R%d),R%d" % (rm, rn)
        if lo4 == 0xE: return "MOV.L @(R0,R%d),R%d" % (rm, rn)
        if lo4 == 0x7: return "MUL.L R%d,R%d" % (rm, rn)
        if lo4 == 0xF: return "MAC.L @R%d+,@R%d+" % (rm, rn)
        if lo4 == 0x2:
            if lo8 == 0x02: return "STC SR,R%d" % rn
            if lo8 == 0x12: return "STC GBR,R%d" % rn
            if lo8 == 0x22: return "STC VBR,R%d" % rn
        if lo4 == 0xA:
            if lo8 == 0x0A: return "STS MACH,R%d" % rn
            if lo8 == 0x1A: return "STS MACL,R%d" % rn
            if lo8 == 0x2A: return "STS PR,R%d" % rn
        if lo4 == 0x3: return "BSRF R%d" % rn
        if lo4 == 0xB and rm == 0: return "RTS"  # redundant but safe

    return "??? (0x%04X)" % insn

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: decode_sh2.py <file_offset_hex> [count]")
        sys.exit(1)

    offset = int(sys.argv[1], 16)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 120

    print("=== Decoding at file offset 0x%05X (addr 0x%08X) ===" % (offset, BASE + offset))
    for line in decode_sh2(offset, count):
        print(line)
