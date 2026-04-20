//Decompile selected Win95 Dragon's Dream functions.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class Win95Decompile extends GhidraScript {
    private static final String[] ADDRS = {
        "00401a39",
        "00401c71",
        "00402689",
        "0041c2ed",
        "0041c430",
        "0042bbe1",
        "0042bd43",
        "0046a3b0",
        "0046a4f0",
        "0046a500",
        "0046a700",
        "0046a8a0",
        "0046aa00",
        "0046ab00"
    };

    @Override
    protected void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (String text : ADDRS) {
            Address addr = toAddr(text);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                println("NO_FUNCTION " + text);
                continue;
            }
            println("==== FUNCTION " + f.getName() + " @ " + f.getEntryPoint() + " ====");
            DecompileResults res = ifc.decompileFunction(f, 30, monitor);
            if (!res.decompileCompleted()) {
                println("DECOMPILE_FAILED " + res.getErrorMessage());
                continue;
            }
            println(res.getDecompiledFunction().getC());
        }
        ifc.dispose();
    }
}
