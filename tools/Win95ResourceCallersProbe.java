// Concise caller/decompile dump for the Win95 00406b92 resource expansion fault.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;

public class Win95ResourceCallersProbe extends GhidraScript {
    private static final String[] TARGETS = {
        "00406b92",
        "00406c63",
        "00406f3a",
        "00407011",
        "0040743d",
        "004079f8",
        "0042bfc2"
    };

    @Override
    protected void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        for (String text : TARGETS) {
            Address target = toAddr(text);
            Function f = getFunctionContaining(target);
            println("==== TARGET " + text + " " +
                    (f == null ? "null" : f.getName() + " @ " + f.getEntryPoint()) + " ====");
            if (f != null) {
                decompile(ifc, f);
            }
            dumpCallSites(target);
            if (f != null && !f.getEntryPoint().equals(target)) {
                dumpCallSites(f.getEntryPoint());
            }
        }

        ifc.dispose();
    }

    private void dumpCallSites(Address target) throws Exception {
        println("CALLS_TO " + target);
        long targetOffset = target.getOffset();
        Address start = toAddr("00401000");
        Address end = toAddr("004983ff");
        Memory mem = currentProgram.getMemory();
        byte[] buf = new byte[(int)(end.getOffset() - start.getOffset() + 1)];
        mem.getBytes(start, buf);
        int count = 0;
        for (int i = 0; i + 5 <= buf.length; i++) {
            if ((buf[i] & 0xff) != 0xe8) {
                continue;
            }
            int rel = (buf[i + 1] & 0xff) |
                      ((buf[i + 2] & 0xff) << 8) |
                      ((buf[i + 3] & 0xff) << 16) |
                      ((buf[i + 4]) << 24);
            long dest = start.getOffset() + i + 5 + rel;
            if (dest != targetOffset) {
                continue;
            }
            Address call = start.add(i);
            Function caller = getFunctionContaining(call);
            println(call + " caller=" +
                    (caller == null ? "null" : caller.getName() + "@" + caller.getEntryPoint()));
            dumpInstructions(call.subtract(24), 24);
            count++;
        }
        println("CALL_COUNT " + count);
    }

    private void dumpInstructions(Address start, int maxInstructions) {
        Instruction inst = getInstructionAt(start);
        if (inst == null) {
            inst = getInstructionAfter(start);
        }
        for (int i = 0; inst != null && i < maxInstructions; i++) {
            println("  " + inst.getAddress() + "  " + inst);
            inst = inst.getNext();
        }
    }

    private void decompile(DecompInterface ifc, Function f) throws Exception {
        DecompileResults res = ifc.decompileFunction(f, 45, monitor);
        if (res.decompileCompleted()) {
            println(res.getDecompiledFunction().getC());
        } else {
            println("DECOMPILE_FAILED " + res.getErrorMessage());
        }
    }
}
