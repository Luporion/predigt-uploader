# Entwicklungsbericht: LosslessCut-Start und Archivierung

## Ziel

Die lokale Version 1.6 weiter beruhigen: manuellen LosslessCut-Pfad vor dem Start merken, LosslessCut-Ausgaben vom Wizard-Terminal trennen, nach Prozessende weiterlaufen und Rohaufnahme-Archivierung standardmaessig auf Verschieben setzen.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/ui.py`
- `tests/test_cli.py`
- `tests/test_ui.py`
- `docs/config.md`
- `docs/manual-test-v1-5.md`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- `_open_losslesscut` gibt jetzt den gestarteten Prozess zurueck und leitet `stdin`, `stdout` und `stderr` nach `DEVNULL`, damit LosslessCut nicht in das Wizard-Terminal schreibt.
- Wenn der automatische LosslessCut-Start fehlschlaegt und ein manueller EXE-Pfad eingegeben wird, fragt der Wizard zuerst nach dem Merken in `%APPDATA%\PredigtUploader\config.toml` und startet LosslessCut erst danach.
- Der Export-Schritt wartet jetzt entweder auf Enter oder erkennt, wenn der gestartete LosslessCut-Prozess bereits beendet ist. Wenn Prozessbeobachtung nicht sinnvoll moeglich ist, bleibt Enter der robuste Fallback.
- Die Rohaufnahme-Archivierung schlaegt bei normalen Rohaufnahmen zuerst Verschieben vor. Bei geschnitten wirkenden Dateien bleibt Liegenlassen die sichere Vorauswahl.
- Der Text-Fallback fuer Menues nutzt Enter als Auswahl der ersten Option, passend zur sichtbaren Vorauswahl.
- Dokumentation und Status wurden fuer AppData-Config, `V:\vMixStorage` als Standardwert, Prozessbeobachtung und neuen Archivierungsstandard aktualisiert.

## Tests

- `python -m pytest` erfolgreich: 148 bestanden.
- PowerShell-Syntaxpruefung fuer `scripts/make-release-zip.ps1` erfolgreich.

## Offene Punkte / Risiken

- Die Prozessbeobachtung ist bewusst schlicht gehalten. Wenn das Terminal oder System sie nicht sicher erlaubt, bleibt Enter der Fallback.
- Keine Vimeo- oder WordPress-Automatisierung enthalten.
- Rohaufnahme-Verschieben bleibt durch eine zweite Sicherheitsabfrage abgesichert.

## Nächster sinnvoller Schritt

Den aktualisierten Ablauf auf dem Gemeinderechner testen: manuellen LosslessCut-Pfad waehlen, Merken bestaetigen, LosslessCut schließen statt Enter zu druecken und danach Rohaufnahme-Verschieben mit zweiter Bestaetigung pruefen.
