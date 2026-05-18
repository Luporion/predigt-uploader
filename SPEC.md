# Spezifikation: PredigtUploader

## Problem

Der aktuelle Predigt-Workflow ist für normale Nutzer zu kompliziert:

- vMix-Aufnahme finden
- in LosslessCut schneiden
- Datei korrekt benennen
- Ordner erstellen
- Datei verschieben
- MP3 per VLC erzeugen
- MP4 zu Vimeo hochladen
- Embed-Code aus Vimeo kopieren
- Predigt in WordPress anlegen

Besonders fehleranfällig sind Dateinamen, Ordner, VLC-Konvertierung, Vimeo-UI und mehrere parallel genutzte Websites/Programme.

## Dateinamenstandard

Für Sonntagsgottesdienst:

```text
Predigt (Predigttitel_Hauptbibelstelle)_Redner Vorname Nachname.mp4
Predigt (Predigttitel_Hauptbibelstelle)_Redner Vorname Nachname.mp3
```

Beispiel:

```text
Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4
Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp3
```

Für Bibelstunde später optional:

```text
Bibelstunde (Hauptbibelstelle)_Redner Vorname Nachname.mp4
```

## Ordnerstandard

Standardordner lokal:

```text
%USERPROFILE%\Desktop\Aufnahmen\YYYY\YYYY-MM-DD
```

Optional mit Besonderheit:

```text
%USERPROFILE%\Desktop\Aufnahmen\YYYY\YYYY-MM-DD - Besonderheit
```

Beispiele:

```text
2026-05-24
2026-06-07 - Pfingsten
2026-10-04 - Erntedank
2026-09-13 - Gastredner Eduard Rahn
```

## Besonderheit im Ordnernamen

Das Programm fragt bei jedem Workflow:

> Gibt es etwas Besonderes, das im Ordnernamen stehen soll?

Optionen:

- Nein
- Ja: Freitext

Beispiele, die im UI angezeigt werden sollen:

- Feiertag
- Themenreihe
- Gastredner
- Besuch
- Taufe
- Gemeindefreizeit

Windows-ungültige Zeichen müssen automatisch ersetzt werden:

```text
\ / : * ? " < > |
```

## Version 1: Muss-Funktionen

- Konfiguration laden
- MP4-Datei auswählen oder Pfad per CLI übergeben
- Predigtdaten abfragen:
  - Datum
  - Typ: Predigt / Bibelstunde, erstmal Standard: Predigt
  - Titel
  - Hauptbibelstelle
  - Redner
  - Besonderheit für Ordnername: optional
- Dateiname erzeugen
- Zielordner bestimmen:
  - Jahresordner prüfen/erstellen
  - Datumsordner prüfen
  - wenn kein Datumsordner existiert: erstellen
  - wenn genau einer existiert: verwenden oder optional umbenennen
  - wenn mehrere existieren: Auswahl erzwingen
- MP4 kopieren/verschieben und korrekt umbenennen
- MP3 aus MP4 per FFmpeg erzeugen
- prüfen, dass MP4 und MP3 existieren
- `predigt-zusammenfassung.txt` für die manuelle Weiterarbeit schreiben und anzeigen
- Logdatei schreiben

Version 1 schreibt keine zusätzliche `predigt-info.json`. Strukturierte Übergabedaten können in einer späteren Phase bewusst neu entschieden werden.

## Version 1: Noch nicht enthalten

- WordPress-Automatisierung
- Vimeo-Upload
- automatische Schnitt-Erkennung in LosslessCut
- vollautomatisches Erkennen von Predigt-Anfang und Predigt-Ende

## Version 2: Mögliche Erweiterung

- LosslessCut komfortabel öffnen
- nach Export automatisch neue MP4-Dateien erkennen
- mehrere Clips erkennen
- Nutzer warnen, wenn mehrere Clips exportiert wurden
- längsten Clip als „wahrscheinlich Predigt“ vorschlagen, aber Auswahl bestätigen lassen

## Version 3: Mögliche Erweiterung

- Vimeo API Upload in Ordner „Predigten“
- Vimeo-Metadaten setzen
- Vimeo-oEmbed-Code automatisch abrufen
- Embed-Code anzeigen/kopieren

## Version 4: Mögliche Erweiterung

- WordPress-Predigt als Entwurf erstellen
- MP3 in WordPress-Mediathek hochladen
- Sermon-Manager-Felder automatisch setzen

## Fehlermeldungsstandard

Jeder Fehler soll enthalten:

1. Kurzbeschreibung für Nutzer
2. konkrete Handlungsempfehlung
3. technischer Admin-Hinweis
4. Pfad zur Logdatei
5. wenn möglich: manuelle Alternative

Beispiel:

```text
Die MP3 konnte nicht erstellt werden.

Bitte prüfe, ob die MP4-Datei geschlossen ist und versuche es erneut.
Wenn es wieder nicht klappt: John Bescheid sagen.

Admin-Hinweis:
FFmpeg wurde nicht gefunden. Erwartet im PATH oder in config.toml unter ffmpeg_path.
```
