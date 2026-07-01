# Entwicklungsbericht: textual-rohaufnahme-schnittschritt

## Ziel

Der Textual-Rohaufnahme-Zweig darf eine komplette vMix-Rohaufnahme nicht direkt als finale Predigt-MP4 verarbeiten. Nach Rohaufnahme-Auswahl muss zuerst ein bewusster LosslessCut-/Schnitt-Schritt kommen.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `src/predigt_uploader/processing.py`
- `tests/test_tui.py`
- `tests/test_processing.py`
- `STATUS.md`

## Was wurde umgesetzt?

- Der Rohaufnahme-Zweig fuehrt nach der MP4-Auswahl nicht mehr direkt zur Metadatenmaske, sondern zur neuen LosslessCut-/Schnitt-Seite.
- Die LosslessCut-Seite erklaert den manuellen Schnitt, kann LosslessCut mit der Rohaufnahme starten und erlaubt danach die Auswahl der geschnittenen MP4.
- Die Auswahl der geschnittenen MP4 nach Rohaufnahme bevorzugt `cut_mp4_folder`, danach den Ordner der Rohaufnahme und danach `vmix_storage`.
- Metadaten und Verarbeitungsplan erhalten nun zwei getrennte Pfade: `source_mp4` fuer die geschnittene finale MP4 und `raw_recording` fuer die komplette vMix-Rohaufnahme.
- Der finale Prueftext nennt explizit, welche Datei als finale Predigt verwendet wird und welche Rohaufnahme danach verschoben/kopiert/liegen gelassen wird.
- Wenn `source_mp4` und `raw_recording` im Rohaufnahme-Zweig identisch sind, wird eine deutliche Warnung in den Plan aufgenommen.

## Tests

- `.\scripts\test.ps1` mit 227 passed.

## Offene Punkte / Risiken

- Die LosslessCut-Schliessen-Erkennung ist noch nicht umgesetzt. Nutzer koennen nach dem Schnitt bewusst auf `Weiter: geschnittene MP4 auswaehlen` klicken.
- Der LosslessCut-Start in Textual nutzt zunaechst nur einen gesetzten `losslesscut_path`; bei fehlendem Pfad wird ein manueller Schnitt mit anschliessender MP4-Auswahl angeboten.

## Nächster sinnvoller Schritt

Den korrigierten Textual-Rohaufnahme-Flow am Zielrechner testen: Rohaufnahme waehlen, LosslessCut starten oder manuell schneiden, geschnittene MP4 auswaehlen, Metadaten erfassen und finale Verarbeitung pruefen.
