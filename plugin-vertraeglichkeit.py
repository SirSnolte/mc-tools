"""Prueft, ob alle Methodenaufrufe eines Plugin-Jars in den Klassen des Proxys existieren.
Fuehrt nichts aus - liest nur Bytecode mit javap."""
import re, subprocess, sys, zipfile, os, collections

JAVAP = sys.argv[1]
PROXY_DIR = sys.argv[2]
PLUGIN_JAR = sys.argv[3]
PREFIXES = ("net/kyori/", "com/velocitypowered/")

ref = re.compile(r"//\s*(?:Interface)?Method\s+([\w/$]+)\.([\w<>$]+):(\([^)]*\)[\w/$;\[]+)")

def javap(args):
    r = subprocess.run([JAVAP] + args, capture_output=True, text=True)
    return r.stdout

# 1) welche Methoden bringt der Proxy mit?
have = collections.defaultdict(set)
decl = re.compile(r"^(?:[\w@. ]*?)(?:class|interface)\s+([\w.$]+)(?:<[^>]*>)?\s*(?:extends\s+([^{]*?))?\s*(?:implements\s+([^{]*?))?\s*\{", re.M)

def own_methods(cls):
    """Methodennamen, die die Klasse selbst deklariert, plus Elternklassen."""
    out = javap(["-p", "-cp", PROXY_DIR, cls.replace("/", ".")])
    if not out.strip():
        return None, []
    names = set()
    for line in out.splitlines():
        m = re.search(r"\b([\w$<>]+)\(", line)
        if m:
            names.add(m.group(1))
    parents = []
    m = decl.search(out)
    if m:
        for grp in (m.group(2), m.group(3)):
            if not grp:
                continue
            for raw in grp.split(","):
                name = re.sub(r"<[^>]*>", "", raw).strip()
                if name and name != "java.lang.Object":
                    parents.append(name.replace(".", "/"))
    return names, parents

def load_proxy(cls, seen=None):
    if cls in have: return
    seen = seen or set()
    if cls in seen: return
    seen.add(cls)
    names, parents = own_methods(cls)
    if names is None:
        have[cls] = set()          # Klasse fehlt ganz
        return
    names.add("__exists__")
    for p in parents:
        load_proxy(p, seen)
        names |= {n for n in have.get(p, set()) if n != "__exists__"}
    have[cls] = names

# 2) alle Aufrufe im Plugin sammeln
zf = zipfile.ZipFile(PLUGIN_JAR)
classes = [n for n in zf.namelist() if n.endswith(".class")]
tmp = PLUGIN_JAR + ".x"
zf.extractall(tmp, members=classes)

calls = set()
for n in classes:
    cls = n[:-6]
    out = javap(["-p", "-c", "-cp", tmp, cls.replace("/", ".")])
    for cname, mname, desc in ref.findall(out):
        if cname.startswith(PREFIXES):
            calls.add((cname, mname, desc))

print("Klassen im Plugin: %d | Aufrufe in Proxy-Bibliotheken: %d" % (len(classes), len(calls)))

fehlt_klasse, fehlt_methode = [], []
for cname, mname, desc in sorted(calls):
    load_proxy(cname)
    if "__exists__" not in have[cname]:
        fehlt_klasse.append(cname)
    elif mname not in have[cname] and mname != "<init>":
        fehlt_methode.append("%s.%s%s" % (cname, mname, desc))

print("\n== fehlende Klassen ==")
for c in sorted(set(fehlt_klasse)): print("  ", c)
if not fehlt_klasse: print("   keine")
print("\n== fehlende Methoden ==")
for m in sorted(set(fehlt_methode)): print("  ", m)
if not fehlt_methode: print("   keine")
