# Ziel-Workflow Version 1

Version 1 ersetzt nicht LosslessCut und automatisiert nicht WordPress/Vimeo. Sie reduziert zuerst die lokalen Fehlerquellen.

## Nutzer-Ablauf

1. PredigtUploader starten.
2. Geschnittene MP4 auswählen.
3. Predigtdaten eingeben:
   - Datum
   - Titel
   - Hauptbibelstelle
   - Redner
   - Besonderheit für Ordnername, falls vorhanden
4. Tool zeigt Zielordner und Dateinamen.
5. Nutzer bestätigt.
6. Tool erstellt/verwendet Ordner.
7. Tool benennt MP4 korrekt.
8. Tool erzeugt MP3 automatisch per FFmpeg.
9. Tool zeigt Zusammenfassung für Vimeo/WordPress.

## Nicht-Ziele in Version 1

- kein Vimeo-Upload
- keine WordPress-Automatisierung
- kein automatisches Schneiden
- kein Erkennen des Predigt-Inhalts per KI

## Erfolgszustand

Im Zielordner liegen:

```text
Predigt (Titel_Bibelstelle)_Redner.mp4
Predigt (Titel_Bibelstelle)_Redner.mp3
predigt-zusammenfassung.txt
```

Version 1 schreibt bewusst keine zusätzliche `predigt-info.json`. Die Textzusammenfassung ist das vorgesehene lokale Übergabedokument.
