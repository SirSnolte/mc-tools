"""Check that every method a plugin jar calls on the proxy actually exists there.

Nothing is executed: the plugin and the proxy classes are only read as bytecode
through javap.
"""
import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile
import zipfile

PREFIXES = ("net/kyori/", "com/velocitypowered/")
# javap processes are started per batch of plugin classes instead of per class.
BATCH_SIZE = 200

REF = re.compile(r"//\s*(?:Interface)?Method\s+([\w/$]+)\.([\w<>$]+):(\([^)]*\)[\w/$;\[]+)")
DECL = re.compile(
    r"^(?:[\w@. ]*?)(?:class|interface)\s+([\w.$]+)(?:<[^>]*>)?\s*"
    r"(?:extends\s+([^{]*?))?\s*(?:implements\s+([^{]*?))?\s*\{",
    re.M,
)
METHOD_NAME = re.compile(r"\b([\w$<>]+)\(")
EXISTS = "__exists__"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Find method calls in a plugin jar that the proxy does not provide."
    )
    parser.add_argument("javap", help="path to the javap binary of a JDK")
    parser.add_argument("proxy_dir", help="directory with the extracted proxy classes")
    parser.add_argument("plugin_jar", help="plugin jar to check")
    args = parser.parse_args()

    if not (os.path.isfile(args.javap) and os.access(args.javap, os.X_OK)):
        parser.error("javap is not an executable file: %s" % args.javap)
    if not os.path.isdir(args.proxy_dir):
        parser.error("proxy_dir is not a directory: %s" % args.proxy_dir)
    if not zipfile.is_zipfile(args.plugin_jar):
        parser.error("plugin_jar is not a jar file: %s" % args.plugin_jar)
    return args


class Proxy:
    """Lazily collects the method names each proxy class declares or inherits."""

    def __init__(self, javap, classpath):
        self.javap = javap
        self.classpath = classpath
        self.methods = collections.defaultdict(set)

    def own_methods(self, cls):
        out = run_javap(self.javap, ["-p", "-cp", self.classpath, cls.replace("/", ".")])
        if not out.strip():
            return None, []
        names = set()
        for line in out.splitlines():
            m = METHOD_NAME.search(line)
            if m:
                names.add(m.group(1))
        parents = []
        m = DECL.search(out)
        if m:
            for group in (m.group(2), m.group(3)):
                if not group:
                    continue
                for raw in group.split(","):
                    name = re.sub(r"<[^>]*>", "", raw).strip()
                    if name and name != "java.lang.Object":
                        parents.append(name.replace(".", "/"))
        return names, parents

    def load(self, cls, seen=None):
        if cls in self.methods:
            return
        seen = seen or set()
        if cls in seen:
            return
        seen.add(cls)
        names, parents = self.own_methods(cls)
        if names is None:
            self.methods[cls] = set()  # class is missing entirely
            return
        names.add(EXISTS)
        for parent in parents:
            self.load(parent, seen)
            names |= {n for n in self.methods.get(parent, set()) if n != EXISTS}
        self.methods[cls] = names


def run_javap(javap, args):
    return subprocess.run([javap] + args, capture_output=True, text=True).stdout


def plugin_calls(javap, plugin_jar):
    """Return the jar's class count and its calls into the proxy libraries."""
    with zipfile.ZipFile(plugin_jar) as jar, tempfile.TemporaryDirectory() as tmp:
        classes = [n for n in jar.namelist() if n.endswith(".class")]
        jar.extractall(tmp, members=classes)
        names = [n[:-6].replace("/", ".") for n in classes]
        calls = set()
        for i in range(0, len(names), BATCH_SIZE):
            out = run_javap(javap, ["-p", "-c", "-cp", tmp] + names[i:i + BATCH_SIZE])
            for cname, mname, desc in REF.findall(out):
                if cname.startswith(PREFIXES):
                    calls.add((cname, mname, desc))
    return len(classes), calls


def print_section(title, items):
    print("\n== %s ==" % title)
    for item in sorted(set(items)):
        print("  ", item)
    if not items:
        print("   none")


def main():
    args = parse_args()
    class_count, calls = plugin_calls(args.javap, args.plugin_jar)
    print("Classes in plugin: %d | calls into proxy libraries: %d" % (class_count, len(calls)))

    proxy = Proxy(args.javap, args.proxy_dir)
    missing_classes, missing_methods = [], []
    for cname, mname, desc in sorted(calls):
        proxy.load(cname)
        if EXISTS not in proxy.methods[cname]:
            missing_classes.append(cname)
        elif mname not in proxy.methods[cname] and mname != "<init>":
            missing_methods.append("%s.%s%s" % (cname, mname, desc))

    print_section("missing classes", missing_classes)
    print_section("missing methods", missing_methods)
    return 1 if missing_classes or missing_methods else 0


if __name__ == "__main__":
    sys.exit(main())
