# Entwicklungsbericht: anklickbare Windows-Starter

## Ziel

Die lokale Phase 1.5 einfacher per Doppelklick startbar machen, ohne Vimeo- oder WordPress-Automatisierung und ohne GUI-Ausbau.

## Geänderte Dateien

- `PredigtUploader starten.cmd`
- `PredigtUploader einrichten.cmd`
- `PredigtUploader Systemcheck.cmd`
- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/install-v1-5.md`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- Drei `.cmd`-Startdateien im Projektstamm erstellt.
- Die Dateien wechseln automatisch in den Projektordner.
- PowerShell wird jeweils mit `-NoProfile` und `-ExecutionPolicy Bypass` gestartet.
- Einrichtung, Systemcheck und Wizard-Start rufen die vorhandenen PowerShell-Skripte auf.
- Das Fenster bleibt nach Ende oder Fehler offen und zeigt eine verständliche deutsche Meldung.
- Installationsdoku und README erklären jetzt die Doppelklick-Nutzung und mögliche Desktop-Verknüpfung.

## Tests

- `python -m pytest`
- Ergebnis: 104 bestanden

## Offene Punkte / Risiken

- Die `.cmd`-Dateien sind bewusst einfache Windows-Starter und ersetzen keine spätere GUI oder Paketierung.
- PowerShell-ExecutionPolicy wird nur für den einzelnen Start mit `Bypass` gesetzt.

## Nächster sinnvoller Schritt

Auf einem Zielrechner die drei Startdateien per Doppelklick testen: Einrichtung, Systemcheck, Wizard-Start.
