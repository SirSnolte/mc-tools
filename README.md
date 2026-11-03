# mc-tools

Small tools for running a Minecraft network on a Velocity proxy.

## plugin-compat-check.py

Checks whether a plugin jar calls methods that the proxy does not provide, without running the
plugin. It catches `NoSuchMethodError` crashes before a restart instead of after it: for example
LibreLogin 0.24.0, which dies on Velocity 4.2 because `Title$Times.of` no longer exists in
Adventure 5.

It reads the plugin's bytecode with `javap`, collects every call into `net/kyori/` (Adventure)
and `com/velocitypowered/` (Velocity API), and looks each one up in the proxy's own classes,
including inherited methods.

### Requirements

- Python 3.8 or newer, no extra packages
- `javap` from a JDK (a JRE alone does not ship it)

### Usage

    # 1. Extract the proxy's classes: this is the real runtime the plugin will see
    unzip -q velocity-4.2.0-30.jar 'net/kyori/*' 'com/velocitypowered/*' -d proxy

    # 2. Check the plugin against them
    python3 plugin-compat-check.py /path/to/jdk/bin/javap proxy plugin.jar

The report lists missing classes and missing methods. The exit code is `0` when nothing is
missing and `1` otherwise, so the check can gate a deployment script.

### Limits

- It only checks that methods **exist**, not that they behave the same.
- Annotations, reflection and anything loaded at runtime are not seen. Check annotation
  fields such as `@Subscribe(priority=…)` separately with `javap -p` against the proxy.
- Methods inherited from `java.lang.Object` (`equals`, `hashCode`, `toString`) and some
  builder methods inherited through generic interfaces are reported as missing. These are
  known false positives.
- Missing classes for other platforms (BungeeCord in a multi-platform jar) are expected as
  long as the proxy never loads them.
