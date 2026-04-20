// Dump code and candidate function context around the Win95 page-fault address.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.mem.Memory;

public class Win95FaultProbe extends GhidraScript {
    private static final String FAULT_ADDR = "004080bd";
    private static final String FUNC_ADDR = "004080b3";

    @Override
    protected void run() throws Exception {
        Address addr = toAddr(FAULT_ADDR);
        Memory mem = currentProgram.getMemory();
        println("FAULT " + FAULT_ADDR);
        println("IMAGE_BASE " + currentProgram.getImageBase());
        println("BLOCK " + mem.getBlock(addr));

        dumpBytes(addr.subtract(96), 192);

        Function containing = getFunctionContaining(addr);
        println("FUNCTION_CONTAINING " +
            (containing == null ? "null" : containing.getName() + " @ " + containing.getEntryPoint()));

        Address candidate = toAddr(FUNC_ADDR);
        if (candidate != null) {
            println("CANDIDATE_PROLOGUE " + candidate);
            disassemble(candidate);
            Function f = getFunctionAt(candidate);
            if (f == null) {
                f = createFunction(candidate, null);
            }
            dumpInstructions(candidate, 80);
            if (f != null) {
                decompile(f);
                dumpReferences(candidate);
                dumpCallSites(candidate);
            }
        } else {
            println("CANDIDATE_PROLOGUE null");
            disassemble(addr.subtract(64));
            dumpInstructions(addr.subtract(64), 80);
        }
    }

    private void dumpReferences(Address target) {
        println("REFERENCES_TO " + target);
        Reference[] refs = getReferencesTo(target);
        for (Reference ref : refs) {
            println(ref.getFromAddress() + " " + ref.getReferenceType());
        }
    }

    private void dumpCallSites(Address target) throws Exception {
        println("CALLS_TO_BYTES " + target);
        byte[] needle = new byte[] { (byte) 0xe8, 0, 0, 0, 0 };
        long targetOffset = target.getOffset();
        Address start = toAddr("00401000");
        Address end = toAddr("004983ff");
        Memory mem = currentProgram.getMemory();
        byte[] buf = new byte[(int)(end.getOffset() - start.getOffset() + 1)];
        mem.getBytes(start, buf);
        for (int i = 0; i + 5 <= buf.length; i++) {
            if (buf[i] != needle[0]) {
                continue;
            }
            int rel = (buf[i + 1] & 0xff) |
                      ((buf[i + 2] & 0xff) << 8) |
                      ((buf[i + 3] & 0xff) << 16) |
                      ((buf[i + 4] & 0xff) << 24);
            long dest = start.getOffset() + i + 5 + rel;
            if (dest == targetOffset) {
                Address call = start.add(i);
                println(call + " CALL_REL32");
                Function caller = getFunctionContaining(call);
                println("  CALLER " + (caller == null ? "null" : caller.getName() + " @ " + caller.getEntryPoint()));
                dumpInstructions(call.subtract(32), 24);
            }
        }
    }

    private void dumpBytes(Address start, int count) throws Exception {
        byte[] buf = new byte[count];
        currentProgram.getMemory().getBytes(start, buf);
        println("BYTES " + start + " +" + count);
        for (int i = 0; i < count; i += 16) {
            StringBuilder line = new StringBuilder();
            line.append(start.add(i)).append(": ");
            for (int j = 0; j < 16 && i + j < count; j++) {
                line.append(String.format("%02x ", buf[i + j] & 0xff));
            }
            println(line.toString());
        }
    }

    private Address findPrologue(Address addr, int maxBack) throws Exception {
        Memory mem = currentProgram.getMemory();
        byte[] buf = new byte[maxBack];
        Address start = addr.subtract(maxBack);
        mem.getBytes(start, buf);
        for (int i = maxBack - 3; i >= 0; i--) {
            int b0 = buf[i] & 0xff;
            int b1 = buf[i + 1] & 0xff;
            int b2 = buf[i + 2] & 0xff;
            if (b0 == 0x55 && b1 == 0x8b && b2 == 0xec) {
                return start.add(i);
            }
        }
        return null;
    }

    private void dumpInstructions(Address start, int maxInstructions) throws Exception {
        println("INSTRUCTIONS_FROM " + start);
        Instruction inst = getInstructionAt(start);
        if (inst == null) {
            inst = getInstructionAfter(start);
        }
        for (int i = 0; inst != null && i < maxInstructions; i++) {
            println(inst.getAddress() + "  " + inst);
            inst = inst.getNext();
        }
    }

    private void decompile(Function f) throws Exception {
        println("DECOMPILE " + f.getName() + " @ " + f.getEntryPoint());
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        DecompileResults res = ifc.decompileFunction(f, 30, monitor);
        if (res.decompileCompleted()) {
            println(res.getDecompiledFunction().getC());
        } else {
            println("DECOMPILE_FAILED " + res.getErrorMessage());
        }
        ifc.dispose();
    }
}
