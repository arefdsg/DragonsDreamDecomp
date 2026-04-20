// Focused decompile for Win95 Dragon's Dream reliable-session functions.

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class Win95FocusedDecompile extends GhidraScript {
    private static final String[] ADDRS = {
        "004233e6",
        "00423492",
        "00423613",
        "0042383c",
        "00423849",
        "00423bef",
        "00423c10",
        "00424176",
        "0042418f",
        "004241e3",
        "00424218",
        "00424228",
        "0042424c",
        "0042427f",
        "004242e9",
        "00424376",
        "0042449a",
        "004245b6",
        "00424610",
        "004496f2",
        "00449775",
        "0044991e"
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
