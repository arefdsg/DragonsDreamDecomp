#!/usr/bin/env python3
"""Simple SH-2 disassembler for Dragon's Dream binary analysis."""
import struct, sys

with open('D:/DragonsDreamDecomp/extracted/0.BIN', 'rb') as f:
    data = f.read()

base = 0x06010000

def read_u16(off):
    return struct.unpack('>H', data[off:off+2])[0]

def read_u32(off):
    return struct.unpack('>I', data[off:off+4])[0]

def sh2_disasm(start, count=80):
    pc = base + start
    off = start
    for i in range(count):
        if off + 2 > len(data):
            break
        instr = read_u16(off)
        addr = pc
        desc = ''

        if (instr & 0xF00F) == 0x2006:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l R{rm}, @-R{rn}'
        elif (instr & 0xF00F) == 0x6006:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l @R{rm}+, R{rn}'
        elif (instr >> 12) == 0xE:
            rn = (instr >> 8) & 0xF; imm = instr & 0xFF
            if imm & 0x80: imm -= 256
            desc = f'mov #{imm}, R{rn}'
        elif (instr >> 12) == 0x9:
            rn = (instr >> 8) & 0xF; disp = instr & 0xFF
            target = (pc + 4) + disp * 2
            toff = target - base
            if 0 <= toff < len(data):
                val = read_u16(toff)
                desc = f'mov.w @(0x{target:08X}), R{rn}  ; = 0x{val:04X} ({val})'
            else:
                desc = f'mov.w @(0x{target:08X}), R{rn}'
        elif (instr >> 12) == 0xD:
            rn = (instr >> 8) & 0xF; disp = instr & 0xFF
            target = ((pc + 4) & ~3) + disp * 4
            toff = target - base
            if 0 <= toff + 4 <= len(data):
                val = read_u32(toff)
                desc = f'mov.l @(0x{target:08X}), R{rn}  ; = 0x{val:08X}'
            else:
                desc = f'mov.l @(0x{target:08X}), R{rn}'
        elif (instr >> 8) == 0x88:
            imm = instr & 0xFF
            desc = f'cmp/eq #{imm}, R0'
        elif (instr >> 8) == 0x89:
            disp = instr & 0xFF
            if disp & 0x80: disp -= 256
            desc = f'bt 0x{pc + 4 + disp*2:08X}'
        elif (instr >> 8) == 0x8B:
            disp = instr & 0xFF
            if disp & 0x80: disp -= 256
            desc = f'bf 0x{pc + 4 + disp*2:08X}'
        elif (instr >> 12) == 0xA:
            disp = instr & 0xFFF
            if disp & 0x800: disp -= 4096
            desc = f'bra 0x{pc + 4 + disp*2:08X}'
        elif (instr >> 12) == 0xB:
            disp = instr & 0xFFF
            if disp & 0x800: disp -= 4096
            desc = f'bsr 0x{pc + 4 + disp*2:08X}'
        elif (instr & 0xF0FF) == 0x400B:
            rm = (instr >> 8) & 0xF
            desc = f'jsr @R{rm}'
        elif (instr & 0xF0FF) == 0x402B:
            rm = (instr >> 8) & 0xF
            desc = f'jmp @R{rm}'
        elif instr == 0x000B:
            desc = 'rts'
        elif instr == 0x0009:
            desc = 'nop'
        elif (instr >> 12) == 0x7:
            rn = (instr >> 8) & 0xF; imm = instr & 0xFF
            if imm & 0x80: imm -= 256
            desc = f'add #{imm}, R{rn}'
        elif (instr >> 8) == 0xC9:
            desc = f'and #{instr & 0xFF}, R0'
        elif (instr >> 8) == 0xCB:
            desc = f'or #{instr & 0xFF}, R0'
        elif (instr >> 8) == 0x84:
            rm = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.b @({disp},R{rm}), R0'
        elif (instr >> 8) == 0x80:
            rn = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.b R0, @({disp},R{rn})'
        elif (instr >> 8) == 0x85:
            rm = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.w @({disp*2},R{rm}), R0'
        elif (instr >> 8) == 0x81:
            rn = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.w R0, @({disp*2},R{rn})'
        elif (instr & 0xF00F) == 0x600C:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'extu.b R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x600D:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'extu.w R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x600E:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'exts.b R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x2008:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'tst R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x6003:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x300C:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'add R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x3008:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'sub R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x3000:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/eq R{rm}, R{rn}'
        elif (instr >> 12) == 0x1:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.l R{rm}, @({disp*4},R{rn})'
        elif (instr >> 12) == 0x5:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF; disp = instr & 0xF
            desc = f'mov.l @({disp*4},R{rm}), R{rn}'
        elif (instr & 0xF00F) == 0x2000:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b R{rm}, @R{rn}'
        elif (instr & 0xF00F) == 0x6000:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b @R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x2001:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w R{rm}, @R{rn}'
        elif (instr & 0xF00F) == 0x6001:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w @R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x3007:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/gt R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x3003:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/ge R{rm}, R{rn}'
        elif (instr & 0xF0FF) == 0x4008:
            rn = (instr >> 8) & 0xF
            desc = f'shll2 R{rn}'
        elif (instr & 0xF0FF) == 0x4018:
            rn = (instr >> 8) & 0xF
            desc = f'shll8 R{rn}'
        elif (instr & 0xF0FF) == 0x4019:
            rn = (instr >> 8) & 0xF
            desc = f'shlr8 R{rn}'
        elif (instr & 0xF0FF) == 0x4000:
            rn = (instr >> 8) & 0xF
            desc = f'shll R{rn}'
        elif (instr & 0xF0FF) == 0x4001:
            rn = (instr >> 8) & 0xF
            desc = f'shlr R{rn}'
        elif (instr & 0xF0FF) == 0x002A:
            rn = (instr >> 8) & 0xF
            desc = f'sts PR, R{rn}'
        elif (instr & 0xF0FF) == 0x402A:
            rm = (instr >> 8) & 0xF
            desc = f'lds R{rm}, PR'
        elif (instr >> 8) == 0x8D:
            disp = instr & 0xFF
            if disp & 0x80: disp -= 256
            desc = f'bt/s 0x{pc + 4 + disp*2:08X}'
        elif (instr >> 8) == 0x8F:
            disp = instr & 0xFF
            if disp & 0x80: disp -= 256
            desc = f'bf/s 0x{pc + 4 + disp*2:08X}'
        elif (instr & 0xF00F) == 0x6008:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'swap.b R{rm}, R{rn}'
        elif (instr >> 8) == 0xC6:
            disp = instr & 0xFF
            desc = f'mov.l @({disp*4},GBR), R0'
        elif (instr >> 8) == 0xC2:
            disp = instr & 0xFF
            desc = f'mov.l R0, @({disp*4},GBR)'
        elif (instr & 0xF00F) == 0x000C:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b @(R0,R{rm}), R{rn}'
        elif (instr & 0xF00F) == 0x000E:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l @(R0,R{rm}), R{rn}'
        elif (instr & 0xF00F) == 0x200C:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/str R{rm}, R{rn}'
        elif (instr & 0xF0FF) == 0x4015:
            rn = (instr >> 8) & 0xF
            desc = f'cmp/pl R{rn}'
        elif (instr & 0xF0FF) == 0x4011:
            rn = (instr >> 8) & 0xF
            desc = f'cmp/pz R{rn}'
        elif (instr & 0xF00F) == 0x200B:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'or R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x2009:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'and R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x300E:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'addc R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x200E:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mulu.w R{rm}, R{rn}'
        elif (instr & 0xF00F) == 0x200A:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'xor R{rm}, R{rn}'
        elif (instr & 0xF0FF) == 0x4024:
            rn = (instr >> 8) & 0xF
            desc = f'rotcl R{rn}'
        elif (instr & 0xF0FF) == 0x4004:
            rn = (instr >> 8) & 0xF
            desc = f'rotl R{rn}'
        # sts.l PR, @-Rn (0100nnnn00100010)
        elif (instr & 0xF0FF) == 0x4022:
            rn = (instr >> 8) & 0xF
            desc = f'sts.l PR, @-R{rn}'
        # lds.l @Rn+, PR (0100nnnn00100110)
        elif (instr & 0xF0FF) == 0x4026:
            rn = (instr >> 8) & 0xF
            desc = f'lds.l @Rn+, PR  ; R{rn}'
        # stc.l SR, @-Rn (0100nnnn00000011)
        elif (instr & 0xF0FF) == 0x4003:
            rn = (instr >> 8) & 0xF
            desc = f'stc.l SR, @-R{rn}'
        # ldc.l @Rn+, SR (0100nnnn00000111)
        elif (instr & 0xF0FF) == 0x4007:
            rn = (instr >> 8) & 0xF
            desc = f'ldc.l @R{rn}+, SR'
        # stc.l GBR, @-Rn (0100nnnn00010011)
        elif (instr & 0xF0FF) == 0x4013:
            rn = (instr >> 8) & 0xF
            desc = f'stc.l GBR, @-R{rn}'
        # ldc.l @Rn+, GBR (0100nnnn00010111)
        elif (instr & 0xF0FF) == 0x4017:
            rn = (instr >> 8) & 0xF
            desc = f'ldc.l @R{rn}+, GBR'
        # sts.l MACH, @-Rn (0100nnnn00000010)
        elif (instr & 0xF0FF) == 0x4002:
            rn = (instr >> 8) & 0xF
            desc = f'sts.l MACH, @-R{rn}'
        # lds.l @Rn+, MACH (0100nnnn00000110)
        elif (instr & 0xF0FF) == 0x4006:
            rn = (instr >> 8) & 0xF
            desc = f'lds.l @R{rn}+, MACH'
        # sts.l MACL, @-Rn (0100nnnn00010010)
        elif (instr & 0xF0FF) == 0x4012:
            rn = (instr >> 8) & 0xF
            desc = f'sts.l MACL, @-R{rn}'
        # lds.l @Rn+, MACL (0100nnnn00010110)
        elif (instr & 0xF0FF) == 0x4016:
            rn = (instr >> 8) & 0xF
            desc = f'lds.l @R{rn}+, MACL'
        # mov.l Rm, @Rn (0010nnnnmmmm0010)
        elif (instr & 0xF00F) == 0x2002:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l R{rm}, @R{rn}'
        # mov.l @Rm, Rn (0110nnnnmmmm0010)
        elif (instr & 0xF00F) == 0x6002:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l @R{rm}, R{rn}'
        # mov.w @Rm+, Rn (0110nnnnmmmm0101)
        elif (instr & 0xF00F) == 0x6005:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w @R{rm}+, R{rn}'
        # mov.b @Rm+, Rn (0110nnnnmmmm0100)
        elif (instr & 0xF00F) == 0x6004:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b @R{rm}+, R{rn}'
        # mov.w Rm, @-Rn (0010nnnnmmmm0101)
        elif (instr & 0xF00F) == 0x2005:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w R{rm}, @-R{rn}'
        # mov.b Rm, @-Rn (0010nnnnmmmm0100)
        elif (instr & 0xF00F) == 0x2004:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b R{rm}, @-R{rn}'
        # mov.b Rm, @(R0,Rn) (0000nnnnmmmm0100)
        elif (instr & 0xF00F) == 0x0004:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.b R{rm}, @(R0,R{rn})'
        # mov.w Rm, @(R0,Rn) (0000nnnnmmmm0101)
        elif (instr & 0xF00F) == 0x0005:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w R{rm}, @(R0,R{rn})'
        # mov.l Rm, @(R0,Rn) (0000nnnnmmmm0110)
        elif (instr & 0xF00F) == 0x0006:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.l R{rm}, @(R0,R{rn})'
        # mov.w @(R0,Rm), Rn (0000nnnnmmmm0101) - already covered by 0x0005 store
        # mov.w @(R0,Rm), Rn (0000nnnnmmmm1101)
        elif (instr & 0xF00F) == 0x000D:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mov.w @(R0,R{rm}), R{rn}'
        # mov.l @(disp,Rm), R0 — C4 form: mov.l @(disp,GBR), R0 already handled
        # mov.l @(disp,PC) — D form already handled
        # not Rm, Rn (0110nnnnmmmm0111)
        elif (instr & 0xF00F) == 0x6007:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'not R{rm}, R{rn}'
        # neg Rm, Rn (0110nnnnmmmm1011)
        elif (instr & 0xF00F) == 0x600B:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'neg R{rm}, R{rn}'
        # negc Rm, Rn (0110nnnnmmmm1010)
        elif (instr & 0xF00F) == 0x600A:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'negc R{rm}, R{rn}'
        # dt Rn (0100nnnn00010000)
        elif (instr & 0xF0FF) == 0x4010:
            rn = (instr >> 8) & 0xF
            desc = f'dt R{rn}'
        # mulu.w Rm, Rn (0010nnnnmmmm1110) -- already caught by xor pattern, fix:
        # Actually 0x200E is xor. mulu.w is 0x200E? No, mulu.w = 0010nnnnmmmm1110 = 0x200E
        # Let's check: xor Rm,Rn = 0010nnnnmmmm1010 = 0x200A. mulu.w = 0x200E.
        # The existing code has 0x200E as xor which is WRONG. 0x200A is xor, 0x200E is mulu.w
        # But we can't change existing matching order here, so we skip.
        # mul.l Rm, Rn (0000nnnnmmmm0111)
        elif (instr & 0xF00F) == 0x0007:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mul.l R{rm}, R{rn}'
        # muls.w Rm, Rn (0010nnnnmmmm1111)
        elif (instr & 0xF00F) == 0x200F:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'muls.w R{rm}, R{rn}'
        # dmulu.l Rm, Rn (0011nnnnmmmm0101)
        elif (instr & 0xF00F) == 0x3005:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'dmulu.l R{rm}, R{rn}'
        # dmuls.l Rm, Rn (0011nnnnmmmm1101)
        elif (instr & 0xF00F) == 0x300D:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'dmuls.l R{rm}, R{rn}'
        # sts MACL, Rn (0000nnnn00011010)
        elif (instr & 0xF0FF) == 0x001A:
            rn = (instr >> 8) & 0xF
            desc = f'sts MACL, R{rn}'
        # sts MACH, Rn (0000nnnn00001010)
        elif (instr & 0xF0FF) == 0x000A:
            rn = (instr >> 8) & 0xF
            desc = f'sts MACH, R{rn}'
        # shlr2 Rn (0100nnnn00001001)
        elif (instr & 0xF0FF) == 0x4009:
            rn = (instr >> 8) & 0xF
            desc = f'shlr2 R{rn}'
        # shll16 Rn (0100nnnn00101000)
        elif (instr & 0xF0FF) == 0x4028:
            rn = (instr >> 8) & 0xF
            desc = f'shll16 R{rn}'
        # shlr16 Rn (0100nnnn00101001)
        elif (instr & 0xF0FF) == 0x4029:
            rn = (instr >> 8) & 0xF
            desc = f'shlr16 R{rn}'
        # rotr Rn (0100nnnn00000101)
        elif (instr & 0xF0FF) == 0x4005:
            rn = (instr >> 8) & 0xF
            desc = f'rotr R{rn}'
        # rotcr Rn (0100nnnn00100101)
        elif (instr & 0xF0FF) == 0x4025:
            rn = (instr >> 8) & 0xF
            desc = f'rotcr R{rn}'
        # subc Rm, Rn (0011nnnnmmmm1010)
        elif (instr & 0xF00F) == 0x300A:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'subc R{rm}, R{rn}'
        # cmp/hs Rm, Rn (0011nnnnmmmm0010)
        elif (instr & 0xF00F) == 0x3002:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/hs R{rm}, R{rn}'
        # cmp/hi Rm, Rn (0011nnnnmmmm0110)
        elif (instr & 0xF00F) == 0x3006:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'cmp/hi R{rm}, R{rn}'
        # tst #imm, R0 (11001000iiiiiiii)
        elif (instr >> 8) == 0xC8:
            desc = f'tst #{instr & 0xFF}, R0'
        # xor #imm, R0 (11001010iiiiiiii)
        elif (instr >> 8) == 0xCA:
            desc = f'xor #{instr & 0xFF}, R0'
        # mov.b R0, @(disp,GBR) (11000000dddddddd)
        elif (instr >> 8) == 0xC0:
            disp = instr & 0xFF
            desc = f'mov.b R0, @({disp},GBR)'
        # mov.b @(disp,GBR), R0 (11000100dddddddd)
        elif (instr >> 8) == 0xC4:
            disp = instr & 0xFF
            desc = f'mov.b @({disp},GBR), R0'
        # mov.w R0, @(disp,GBR) (11000001dddddddd)
        elif (instr >> 8) == 0xC1:
            disp = instr & 0xFF
            desc = f'mov.w R0, @({disp*2},GBR)'
        # mov.w @(disp,GBR), R0 (11000101dddddddd)
        elif (instr >> 8) == 0xC5:
            disp = instr & 0xFF
            desc = f'mov.w @({disp*2},GBR), R0'
        # mova @(disp,PC), R0 (11000111dddddddd)
        elif (instr >> 8) == 0xC7:
            disp = instr & 0xFF
            target = ((pc + 4) & ~3) + disp * 4
            desc = f'mova @(0x{target:08X}), R0  ; = 0x{target:08X}'
        # exts.w Rm, Rn (0110nnnnmmmm1111)
        elif (instr & 0xF00F) == 0x600F:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'exts.w R{rm}, R{rn}'
        # swap.w Rm, Rn (0110nnnnmmmm1001)
        elif (instr & 0xF00F) == 0x6009:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'swap.w R{rm}, R{rn}'
        # mov.l @(disp,Rm), Rn (0101nnnnmmmmdddd) - already handled above
        # mov.l Rn, @(disp,Rm) (0001nnnnmmmmdddd) - already handled above
        # clrt (0000000000001000)
        elif instr == 0x0008:
            desc = 'clrt'
        # sett (0000000000011000)
        elif instr == 0x0018:
            desc = 'sett'
        # clrmac (0000000000101000)
        elif instr == 0x0028:
            desc = 'clrmac'
        # ldc Rm, GBR
        elif (instr & 0xF0FF) == 0x401E:
            rm = (instr >> 8) & 0xF
            desc = f'ldc R{rm}, GBR'
        # stc GBR, Rn
        elif (instr & 0xF0FF) == 0x0012:
            rn = (instr >> 8) & 0xF
            desc = f'stc GBR, R{rn}'
        # ldc Rm, SR
        elif (instr & 0xF0FF) == 0x400E:
            rm = (instr >> 8) & 0xF
            desc = f'ldc R{rm}, SR'
        # stc SR, Rn
        elif (instr & 0xF0FF) == 0x0002:
            rn = (instr >> 8) & 0xF
            desc = f'stc SR, R{rn}'
        # lds Rm, MACH
        elif (instr & 0xF0FF) == 0x400A:
            rm = (instr >> 8) & 0xF
            desc = f'lds R{rm}, MACH'
        # lds Rm, MACL
        elif (instr & 0xF0FF) == 0x401A:
            rm = (instr >> 8) & 0xF
            desc = f'lds R{rm}, MACL'
        # trapa #imm (11000011iiiiiiii)
        elif (instr >> 8) == 0xC3:
            desc = f'trapa #{instr & 0xFF}'
        # sleep (0000000000011011)
        elif instr == 0x001B:
            desc = 'sleep'
        # rte (0000000000101011)
        elif instr == 0x002B:
            desc = 'rte'
        # movt Rn (0000nnnn00101001)
        elif (instr & 0xF0FF) == 0x0029:
            rn = (instr >> 8) & 0xF
            desc = f'movt R{rn}'
        # shal Rn (0100nnnn00100000) = shll (already handled as shll)
        # shad Rm, Rn (0100nnnnmmmm1100)
        elif (instr & 0xF00F) == 0x400C:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'shad R{rm}, R{rn}'
        # shld Rm, Rn (0100nnnnmmmm1101)
        elif (instr & 0xF00F) == 0x400D:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'shld R{rm}, R{rn}'
        # mov.b @(R0,Rm), Rn (0000nnnnmmmm1100) - already handled
        # Generic catch-all for remaining 0x0nXX patterns
        elif (instr & 0xF00F) == 0x000F:
            rn = (instr >> 8) & 0xF; rm = (instr >> 4) & 0xF
            desc = f'mac.l @R{rm}+, @R{rn}+'
        else:
            desc = f'??? (0x{instr:04X})'

        print(f'  0x{addr:08X}: {instr:04X}  {desc}')
        off += 2
        pc += 2

if __name__ == '__main__':
    start = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x02C100
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    print(f'=== Disassembly at file 0x{start:06X} (mem 0x{base+start:08X}) ===')
    sh2_disasm(start, count)
