from ghidra.program.model.data import StringDataInstance
from ghidra.util.task import ConsoleTaskMonitor


TARGETS = [
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
    "SavePassword",
]


def string_value(data):
    try:
        sdi = StringDataInstance.getStringDataInstance(data)
        if sdi is not None:
            return sdi.getStringValue()
    except Exception:
        pass
    try:
        value = data.getValue()
        if value is not None:
            return str(value)
    except Exception:
        pass
    return ""


def function_for(addr):
    func = getFunctionContaining(addr)
    if func is None:
        return "<no function>"
    return "%s @ %s" % (func.getName(), func.getEntryPoint())


def main():
    monitor = ConsoleTaskMonitor()
    listing = currentProgram.getListing()
    refs = currentProgram.getReferenceManager()

    print("PROGRAM %s" % currentProgram.getName())
    print("IMAGE_BASE %s" % currentProgram.getImageBase())
    print("LANGUAGE %s" % currentProgram.getLanguageID())
    print("")

    found = []
    data_iter = listing.getDefinedData(True)
    while data_iter.hasNext() and not monitor.isCancelled():
        data = data_iter.next()
        value = string_value(data)
        if not value:
            continue
        for target in TARGETS:
            if target in value:
                found.append((target, data.getAddress(), value))

    for target, addr, value in found:
        print("STRING %r @ %s value=%r" % (target, addr, value))
        ref_iter = refs.getReferencesTo(addr)
        count = 0
        for ref in ref_iter:
            count += 1
            from_addr = ref.getFromAddress()
            print("  XREF %s op=%d in %s" % (from_addr, ref.getOperandIndex(), function_for(from_addr)))
            if count >= 40:
                print("  ... xrefs truncated")
                break
        if count == 0:
            print("  XREF <none>")
        print("")


main()
