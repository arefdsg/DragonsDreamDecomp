// Trace callers around the Win95 Dragon's Dream socket wrapper.

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class Win95NetTrace extends GhidraScript {
    private static final String[] TARGETS = {
        "0042bd43", // create path
        "0042bdd9", // connect poll path
        "00423c10", // inbound payload decoder
        "0044991e", // inbound IV stream parser
        "00449bcc", // single-byte receive post hook
        "0042c138", // receive wrapper
        "0042c2ea", // send wrapper
        "0046a700", // create/open socket
        "0046a860", // send wrapper
        "0046a970", // recv wrapper
        "0046ab70", // connect/thread helper
        "0046ad70", // socket state/thread helper area
        "0046ae70"  // handle lookup
    };
    private static final String[] DATA_TARGETS = {
        "005aab30", // current/queued send head
        "005aacb0", // send queue list
        "005aacc0", // send thread/live flag
        "005af1e4", // inbound decoded length
        "005aea10", // inbound parser state
        "005aea14", // inbound payload buffer
        "005af1f0"  // inbound decoded message/state
    };

    @Override
    protected void run() throws Exception {
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        Set<Function> callers = new HashSet<Function>();

        for (String text : TARGETS) {
            Address addr = toAddr(text);
            Function target = getFunctionContaining(addr);
            println("==== TARGET " + text + " " + describe(target, addr) + " ====");
            if (target != null) {
                callers.add(target);
            }
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(addr);
            int count = 0;
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function caller = getFunctionContaining(from);
                println("  XREF " + from + " op=" + ref.getOperandIndex() + " in " + describe(caller, from));
                if (caller != null) {
                    callers.add(caller);
                }
                count++;
            }
            if (count == 0) {
                println("  XREF <none>");
            }
            println("");
        }

        for (String text : DATA_TARGETS) {
            Address addr = toAddr(text);
            println("==== DATA " + text + " ====");
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(addr);
            int count = 0;
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Address from = ref.getFromAddress();
                Function caller = getFunctionContaining(from);
                println("  REF " + from + " op=" + ref.getOperandIndex() + " in " + describe(caller, from));
                if (caller != null) {
                    callers.add(caller);
                }
                count++;
                if (count >= 80) {
                    println("  ... refs truncated");
                    break;
                }
            }
            if (count == 0) {
                println("  REF <none>");
            }
            println("");
        }

        println("==== CALLER DECOMPILE ====");
        for (Function caller : callers) {
            println("---- CALLER " + caller.getName() + " @ " + caller.getEntryPoint() + " ----");
            DecompileResults res = ifc.decompileFunction(caller, 30, monitor);
            if (!res.decompileCompleted()) {
                println("DECOMPILE_FAILED " + res.getErrorMessage());
                continue;
            }
            println(res.getDecompiledFunction().getC());
        }

        ifc.dispose();
    }

    private String describe(Function f, Address fallback) {
        if (f == null) {
            return "<no function> @ " + fallback;
        }
        return f.getName() + " @ " + f.getEntryPoint();
    }
}
