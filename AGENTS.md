# AGENTS.md – Anweisungen für Codex und andere Coding-KIs

## Projektziel

Entwickle ein Windows-Tool für den Predigt-Workflow einer Gemeinde. Die Zielgruppe sind überwiegend nicht-technische Nutzer. Das Tool muss zuverlässig, verständlich und fehlertolerant sein.

## Arbeitsweise

- Arbeite in kleinen, testbaren Schritten.
- Ändere nicht unnötig viele Dateien auf einmal.
- Füge für neue Logik Tests hinzu.
- Nach jeder Aufgabe: `pytest` ausführen, falls möglich.
- `STATUS.md` nach relevanten Änderungen am Projektstand kurz aktualisieren.
- Keine API-Keys, Tokens, Passwörter oder privaten Pfade committen.
- Keine echten Gemeinde-Zugangsdaten in Beispieldateien verwenden.
- Standardbibliothek bevorzugen, externe Abhängigkeiten nur mit Begründung.
- Windows ist Hauptplattform. Pfade und Dateinamen müssen Windows-tauglich sein.

## Nutzerfreundlichkeit

Alle Nutzertexte müssen deutsch, konkret und laienverständlich sein.

Schlecht:

```text
ffmpeg exit code 1
```

Gut:

```text
Die MP3 konnte nicht erstellt werden.
Bitte prüfe, ob die Videodatei noch in einem anderen Programm geöffnet ist.
Admin-Hinweis: FFmpeg exit code 1. Details siehe Logdatei.
```

## Version-1-Grenzen

Nicht implementieren, solange nicht ausdrücklich beauftragt:

- WordPress-Automatisierung
- Vimeo-Upload
- Login-/Token-Verwaltung für Vimeo oder WordPress
- automatische Predigt-Erkennung per KI

Version 1 soll lokal funktionieren:

- Datei auswählen
- Dateiname erzeugen
- Ordner prüfen/erstellen
- MP4 verschieben/umbenennen
- MP3 erzeugen
- Zusammenfassung anzeigen

## Codex-Bericht nach jeder Aufgabe

Nach jeder umgesetzten Aufgabe muss eine neue Datei unter `docs/dev-log/` erstellt werden.

Dateiname:

```text
YYYY-MM-DD_HHMM_kurzer-task-name.md
```

Inhalt:

```markdown
# Entwicklungsbericht: kurzer Task-Name

## Ziel

## Geänderte Dateien

## Was wurde umgesetzt?

## Tests

## Offene Punkte / Risiken

## Nächster sinnvoller Schritt
```

Diese Datei ersetzt kein Review. Für tiefe Reviews müssen zusätzlich der Git-Diff oder die geänderten Dateien geprüft werden können.

## Code-Stil

- klare Funktionsnamen
- kleine Funktionen
- keine stillen Fehler
- keine kryptischen Rückgabewerte
- lieber `Result`/Dataclasses oder Exceptions mit verständlicher Behandlung
- Tests für Sonderfälle

## Technische Entscheidungen

Aktueller Stack:

- Python 3.11+
- Standardbibliothek bevorzugt
- CLI zuerst
- GUI später mit tkinter oder anderem bewusst gewähltem Framework
- FFmpeg wird extern aufgerufen, nicht selbst implementiert

## Wichtige Fachregeln

Dateiname Predigt:

```text
Predigt (Predigttitel_Hauptbibelstelle)_Redner Vorname Nachname.mp4
```

Ordner:

```text
YYYY\YYYY-MM-DD
YYYY\YYYY-MM-DD - Besonderheit
```

Bei mehreren exportierten Clips nie blind hochladen. Nutzer muss ausdrücklich die Predigt auswählen.
