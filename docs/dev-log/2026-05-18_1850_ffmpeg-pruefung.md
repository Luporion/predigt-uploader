# Entwicklungsbericht: FFmpeg-Pruefung

## Ziel

Vor der MP3-Erzeugung im Phase-1-Wizard pruefen, ob FFmpeg verfuegbar ist, und fehlendes FFmpeg nutzerfreundlich erklaeren.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `tests/test_cli.py`
- `STATUS.md`
- `docs/dev-log/2026-05-18_1850_ffmpeg-pruefung.md`

## Was wurde umgesetzt?

- Der Wizard prueft nach erfolgreicher MP4-Uebernahme und vor der MP3-Erzeugung, ob FFmpeg verfuegbar ist.
- Wenn FFmpeg fehlt, wird die MP3-Erzeugung nicht gestartet.
- Die Meldung erklaert, was fehlt, warum FFmpeg gebraucht wird und dass die MP4 trotzdem vorbereitet wurde.
- Die Meldung nennt manuelle naechste Schritte inklusive erwartetem MP3-Dateinamen und Zielordner.
- Ein Admin-Hinweis nennt den konfigurierten `ffmpeg_path` und die technische Erwartung.
- Normale Nutzer bekommen keinen Traceback.
- Keine Vimeo- oder WordPress-Automatisierung ergaenzt.
- `STATUS.md` an den neuen Stand angepasst.

## Tests

- `python -m pytest`
- Ergebnis: `25 passed in 0.11s`

## Offene Punkte / Risiken

- Die eigentliche FFmpeg-Konvertierung sollte noch weiter abgesichert werden, zum Beispiel durch Pruefung, ob MP4 und MP3 nach dem Workflow wirklich vorhanden sind.

## Nächster sinnvoller Schritt

MP3-Erzeugung weiter absichern und das Ergebnis nach der Konvertierung pruefen.
