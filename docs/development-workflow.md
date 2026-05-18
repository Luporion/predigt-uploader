# Entwicklungsworkflow mit Codex

## Rollen

- Mensch/Admin: fachliche Entscheidungen, Tests am echten Rechner, Freigaben
- ChatGPT-Projektchat: Architektur, Anforderungen, Review, nächste Aufgaben
- Codex: Umsetzung im Repo, Tests, Dev-Logs

## Empfohlener Ablauf

1. Aufgabe aus `TASKS.md` auswählen.
2. Aufgabe für Codex konkret formulieren.
3. Codex ändert Code und Tests.
4. Codex führt Tests aus.
5. Codex erstellt Dev-Log unter `docs/dev-log/`.
6. Mensch prüft kurz in VS Code.
7. Bei Unsicherheit: Git-Diff oder ZIP an Projektchat übergeben.

## Was an den Projektchat übergeben werden sollte

Für kleine Änderungen reicht oft:

- Dev-Log-Datei
- Testausgabe
- kurze Beschreibung, was passiert ist

Für echte Prüfung besser:

- `git diff`
- geänderte Dateien
- oder ZIP des aktuellen Repos

Der Dev-Log ist eine Orientierung, ersetzt aber kein Code-Review.
