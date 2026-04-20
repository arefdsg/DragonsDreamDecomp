//Reports cross references for key Dragon's Dream Win95 networking strings.

import java.util.Arrays;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class Win95Probe extends GhidraScript {
    private static final List<String> TARGETS = Arrays.asList(
        "Socket opened.",
        "Socket released.",
        "PSI_ERR_SYSTEM",
        "C HRPG",
        "C NETRPG",
        "SET 1:0,2:0,3:0,4:1",
        "Version %s%s %s conn.",
        "Lan net",
        "INFOWEB",
        "WAITTIME",
        "IPADR",
        "8020",
        "CMI_Create exec",
        "NETPWORD",
        "SavePassword"
    );

    @Override
    protected void run() throws Exception {
        println("PROGRAM " + currentProgram.getName());
        println("IMAGE_BASE " + currentProgram.getImageBase());
        println("LANGUAGE " + currentProgram.getLanguageID());
        println("");

        Listing listing = currentProgram.getListing();
        for (Data data : listing.getDefinedData(true)) {
            String value = stringValue(data);
            if (value == null || value.isEmpty()) {
                continue;
            }
            for (String target : TARGETS) {
                if (value.contains(target)) {
                    reportString(target, data.getAddress(), value);
                }
            }
            if (monitor.isCancelled()) {
                return;
            }
        }
    }

    private String stringValue(Data data) {
        try {
            StringDataInstance sdi = StringDataInstance.getStringDataInstance(data);
            if (sdi != null) {
                return sdi.getStringValue();
            }
        }
        catch (Exception e) {
            // Fall through.
        }
        Object value = data.getValue();
        return value == null ? "" : value.toString();
    }

    private void reportString(String target, Address addr, String value) {
        println("STRING \"" + target + "\" @ " + addr + " value=\"" + value + "\"");
        ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(addr);
        int count = 0;
        while (refs.hasNext()) {
            Reference ref = refs.next();
            Address from = ref.getFromAddress();
            println("  XREF " + from + " op=" + ref.getOperandIndex() + " in " + functionFor(from));
            count++;
            if (count >= 40) {
                println("  ... xrefs truncated");
                break;
            }
        }
        if (count == 0) {
            println("  XREF <none>");
        }
        println("");
    }

    private String functionFor(Address addr) {
        Function f = getFunctionContaining(addr);
        if (f == null) {
            return "<no function>";
        }
        return f.getName() + " @ " + f.getEntryPoint();
    }
}
