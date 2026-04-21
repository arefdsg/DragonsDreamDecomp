// Dump the Win95 resource lookup path behind the stable 0040d8c6 page fault.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;

public class Win95ResourceFaultProbe extends GhidraScript {
    private static final String[] FUNCS = {
        "00406b92",
        "00406f3a",
        "00406f7d",
        "0040647a",
        "00407011",
        "0043bb0c",
        "0043b37a",
        "0043bcd1",
        "0043b549"
    };

    private static final String[] DATA = {
        "004b3b5c",
        "004b3d70",
        "004b3d90",
        "004b3d9c",
        "004b4668",
        "00500710",
        "00500c80",
        "00515878"
    };

    @Override
    protected void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        for (String text : FUNCS) {
            Address addr = toAddr(text);
            disassemble(addr);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                f = createFunction(addr, null);
            }
            println("==== FUNCTION " + text + " -> " +
                    (f == null ? "null" : f.getName() + " @ " + f.getEntryPoint()) + " ====");
            dumpInstructions(addr.subtract(32), 180);
            if (f != null) {
                decompile(ifc, f);
                dumpReferences(f.getEntryPoint());
                dumpCallSites(f.getEntryPoint());
            }
        }

        for (String text : DATA) {
            Address addr = toAddr(text);
            println("==== DATA " + text + " ====");
            dumpBytes(addr, 128);
            dumpReferences(addr);
        }

        ifc.dispose();
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
        long targetOffset = target.getOffset();
        Address start = toAddr("00401000");
        Address end = toAddr("004983ff");
        Memory mem = currentProgram.getMemory();
        byte[] buf = new byte[(int)(end.getOffset() - start.getOffset() + 1)];
        mem.getBytes(start, buf);
        for (int i = 0; i + 5 <= buf.length; i++) {
            if ((buf[i] & 0xff) != 0xe8) {
                continue;
            }
            int rel = (buf[i + 1] & 0xff) |
                      ((buf[i + 2] & 0xff) << 8) |
                      ((buf[i + 3] & 0xff) << 16) |
                      ((buf[i + 4]) << 24);
            long dest = start.getOffset() + i + 5 + rel;
            if (dest == targetOffset) {
                Address call = start.add(i);
                println(call + " CALL_REL32");
                Function caller = getFunctionContaining(call);
                println("  CALLER " + (caller == null ? "null" :
                        caller.getName() + " @ " + caller.getEntryPoint()));
                dumpInstructions(call.subtract(48), 40);
            }
        }
    }

    private void dumpInstructions(Address start, int maxInstructions) {
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

    private void dumpBytes(Address start, int count) throws Exception {
        byte[] buf = new byte[count];
        currentProgram.getMemory().getBytes(start, buf);
        for (int i = 0; i < count; i += 16) {
            StringBuilder line = new StringBuilder();
            line.append(start.add(i)).append(": ");
            for (int j = 0; j < 16 && i + j < count; j++) {
                line.append(String.format("%02x ", buf[i + j] & 0xff));
            }
            line.append("  ");
            for (int j = 0; j < 16 && i + j < count; j++) {
                int b = buf[i + j] & 0xff;
                line.append((b >= 0x20 && b < 0x7f) ? (char)b : '.');
            }
            println(line.toString());
        }
    }

    private void decompile(DecompInterface ifc, Function f) throws Exception {
        println("DECOMPILE " + f.getName() + " @ " + f.getEntryPoint());
        DecompileResults res = ifc.decompileFunction(f, 45, monitor);
        if (res.decompileCompleted()) {
            println(res.getDecompiledFunction().getC());
        } else {
            println("DECOMPILE_FAILED " + res.getErrorMessage());
        }
    }
}
