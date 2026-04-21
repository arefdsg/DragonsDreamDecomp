// Dump/decompile Win95 UPDATE_CHARDATA_REQUEST (0x019F) handler.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class Win95UpdateChardataProbe extends GhidraScript {
    private static final String[] FUNCS = {
        "00407e16",
        "00407dbd",
        "00407e28",
        "00407c7c",
        "0040d8ec",
        "0040d8c2"
    };

    @Override
    protected void run() throws Exception {
        for (String text : FUNCS) {
            Address addr = toAddr(text);
            disassemble(addr);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                f = createFunction(addr, null);
            }
            dumpInstructions(addr, 100);
            if (f != null) {
                decompile(f);
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
