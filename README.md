# mc-werkzeuge

## plugin-vertraeglichkeit.py

Prüft, ob ein Plugin-Jar Methoden aufruft, die der Proxy gar nicht mitbringt —
ohne das Plugin auszuführen. Fängt genau die Fehlerklasse, an der LibreLogin
0.24.0 auf Velocity 4.2 stirbt (`NoSuchMethodError` auf `Title$Times.of`),
und zwar vor dem Neustart statt danach.

Aufruf:

    # 1. Klassen des Proxys auspacken (das ist die echte Laufzeitumgebung)
    unzip -q velocity-4.2.0-30.jar 'net/kyori/*' 'com/velocitypowered/*' -d proxy

    # 2. Plugin dagegen prüfen
    python3 -I plugin-vertraeglichkeit.py /pfad/zu/javap proxy plugin.jar

Braucht `javap` aus einem JDK. Auf diesem Rechner ist `/usr/lib/jvm/java-25-openjdk`
nur eine JRE; das JDK von PrismLauncher funktioniert.

### Grenzen

- Prüft nur, ob Methoden **existieren** — nicht, ob sie sich verhalten wie erwartet.
- Annotationen, Reflection und Dinge, die erst zur Laufzeit nachgeladen werden,
  sieht es nicht. Annotationsfelder (z. B. `@Subscribe(priority=…)`) muss man
  gesondert mit `javap -p` am Proxy nachsehen.
- `toString()` und andere von `java.lang.Object` geerbte Methoden werden als
  fehlend gemeldet — Fehlalarm, bewusst so.
- Fehlende Klassen für andere Plattformen (BungeeCord in einem Multiplattform-Jar)
  sind normal, solange sie auf dem Proxy nie geladen werden.
