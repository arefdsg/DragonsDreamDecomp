// Dump/decompile the Win95 MAP_NOTICE fault handler.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;

public class Win95MapFaultProbe extends GhidraScript {
    private static final String FAULT_ADDR = "0040ad13";
    private static final String[] FUNCS = {
        "0040ad0c",
        "00407cc4",
        "0040d8c2",
        "0040d8ec"
    };

    @Override
    protected void run() throws Exception {
        Address fault = toAddr(FAULT_ADDR);
        dumpBytes(fault.subtract(96), 224);
        for (String text : FUNCS) {
            Address addr = toAddr(text);
            disassemble(addr);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                f = createFunction(addr, null);
            }
            dumpInstructions(addr, 90);
            if (f != null) {
                decompile(f);
            }
        }
    }

    private void dumpBytes(Address start, int count) throws Exception {
        byte[] buf = new byte[count];
        Memory mem = currentProgram.getMemory();
        mem.getBytes(start, buf);
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
