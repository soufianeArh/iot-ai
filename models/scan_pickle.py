"""
Inspect a PyTorch .pt without executing it.

A .pt is a zip containing data.pkl. Unpickling runs code: every GLOBAL /
STACK_GLOBAL opcode imports a name, and REDUCE calls it. That is the whole
attack - a checkpoint that imports os.system and calls it during torch.load.

pickletools.genops only *parses* the opcode stream, so nothing is imported and
nothing is called. We list every global the pickle would reach for and compare
it against what a legitimate Ultralytics checkpoint needs.
"""
import pickletools
import sys
import zipfile

# Modules a real YOLO checkpoint touches. Anything outside this is worth a look;
# anything in DANGEROUS below is disqualifying on its own.
EXPECTED_PREFIXES = (
    "torch", "collections", "ultralytics", "numpy", "__builtin__",
    "builtins.set", "builtins.getattr", "pathlib", "argparse",
)
DANGEROUS = (
    "os", "posix", "nt", "subprocess", "sys", "shutil", "socket", "runpy",
    "importlib", "builtins.exec", "builtins.eval", "builtins.compile",
    "builtins.__import__", "builtins.open", "webbrowser", "urllib",
    "requests", "http", "ftplib", "pty", "commands", "popen2", "pickle",
    "base64", "codecs", "marshal", "types.FunctionType", "operator.attrgetter",
)


def globals_in(data: bytes):
    """Every (module, name) the pickle would import, plus the opcode counts."""
    found, counts = [], {}
    recent = []          # trailing string constants, for STACK_GLOBAL
    for op, arg, _pos in pickletools.genops(data):
        counts[op.name] = counts.get(op.name, 0) + 1

        if op.name == "GLOBAL":
            found.append(tuple(str(arg).split(" ", 1)))
        elif op.name == "STACK_GLOBAL":
            # The module and name were pushed as the two preceding strings.
            if len(recent) >= 2:
                found.append((recent[-2], recent[-1]))
            else:
                found.append(("<unresolved>", "<unresolved>"))

        if op.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE",
                       "SHORT_BINSTRING", "BINSTRING", "STRING"):
            recent.append(str(arg))
            recent = recent[-4:]
    return found, counts


def main(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        pkls = [n for n in names if n.endswith(".pkl")]
        print(f"zip entries: {len(names)}   pickles: {pkls}")
        print(f"non-tensor entries: "
              f"{[n for n in names if not n.endswith(('.pkl',)) and '/data/' not in n][:10]}")

        verdict_bad = []
        for name in pkls:
            data = z.read(name)
            found, counts = globals_in(data)
            uniq = sorted(set(found))

            print(f"\n--- {name} ({len(data)} bytes) ---")
            print(f"REDUCE={counts.get('REDUCE', 0)}  "
                  f"BUILD={counts.get('BUILD', 0)}  "
                  f"GLOBAL={counts.get('GLOBAL', 0) + counts.get('STACK_GLOBAL', 0)}")
            print(f"{len(uniq)} distinct globals:")
            for mod, fn in uniq:
                dotted = f"{mod}.{fn}"
                bad = any(dotted == d or dotted.startswith(d + ".") or mod == d
                          for d in DANGEROUS)
                ok = any(dotted.startswith(p) for p in EXPECTED_PREFIXES)
                mark = "!! DANGEROUS" if bad else ("   ok" if ok else "?  unexpected")
                if bad:
                    verdict_bad.append(dotted)
                print(f"  {mark}  {dotted}")

    print("\n" + "=" * 60)
    if verdict_bad:
        print("REJECT - pickle reaches for:", ", ".join(sorted(set(verdict_bad))))
        return 1
    print("No dangerous globals found. Safe to load in an isolated container.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
