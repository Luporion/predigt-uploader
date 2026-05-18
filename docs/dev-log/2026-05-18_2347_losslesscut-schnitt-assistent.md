# Entwicklungsbericht: losslesscut-schnitt-assistent

## Ziel

Eine kleine Phase 1.5 umsetzen: LosslessCut als externes Schnittprogramm in den lokalen Workflow einbinden, ohne Vimeo, WordPress oder einen eigenen Video-Editor zu implementieren.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `tests/test_cli.py`
- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/config.md`
- `docs/manual-test-v1.md`
- `docs/manual-test-v1-5.md`

## Was wurde umgesetzt?

- Der Wizard fragt, ob bereits eine fertig geschnittene MP4 vorhanden ist.
- Wenn nicht, startet der LosslessCut-Schnitt-Assistent.
- Der Assistent kann die neueste MP4 aus dem konfigurierten `vmix_storage` vorschlagen.
- Alternativ kann die Rohaufnahme manuell per Pfad eingegeben werden.
- LosslessCut wird mit der Rohaufnahme gestartet.
- `losslesscut_path` kann konfiguriert werden; ohne Pfad versucht der Wizard `LosslessCut` über PATH/App-Alias.
- Nutzer bekommen klare Hinweise, nur den Predigtbereich zu exportieren und Chorlieder/Beiträge nicht als Predigtdatei zu verwenden.
- Nach dem Export sucht der Wizard in sinnvollen lokalen Ordnern nach neuen MP4-Dateien seit Start des Assistenten.
- Bei mehreren neuen MP4-Dateien muss die richtige Predigtdatei bewusst ausgewählt werden.
- Wenn keine Datei gefunden oder die gefundene Datei abgelehnt wird, kann der Exportpfad manuell eingegeben werden.
- Danach läuft der bestehende lokale Workflow weiter: Zielbasisordner, Metadaten, MP4 übernehmen, MP3 erzeugen, Zusammenfassung und Log.

## Tests

- `python -m pytest`
- Ergebnis: 75 Tests bestanden.

## Offene Punkte / Risiken

- Der Assistent steuert LosslessCut bewusst nicht fern; der Schnitt und Export bleiben manuell.
- Die automatische Exportsuche ist bewusst einfach und sucht nicht rekursiv in grossen Ordnerbaeumen.
- Der Ablauf sollte mit einer echten Rohaufnahme und installiertem LosslessCut manuell getestet werden.

## Nächster sinnvoller Schritt

Phase 1.5 nach `docs/manual-test-v1-5.md` lokal testen und die Exportsuche im echten LosslessCut-Ablauf beobachten.
