# Fehlerbehandlung

## Grundprinzip

Jede Fehlermeldung muss für normale Nutzer verständlich sein und gleichzeitig genug technische Infos für den Admin liefern.

## Format

```text
Überschrift: Was ist schiefgelaufen?

Für Nutzer:
- Was bedeutet das?
- Was soll ich jetzt tun?
- Gibt es eine manuelle Alternative?

Für Admin:
- technischer Fehler
- betroffene Datei
- Config-Wert
- Logdatei
```

## Beispiele

### FFmpeg fehlt

```text
Die MP3 konnte nicht erstellt werden.

Das Programm findet den MP3-Konverter FFmpeg nicht.
Bitte John Bescheid sagen oder die MP3 vorübergehend manuell mit File Converter erstellen.

Admin-Hinweis:
ffmpeg_path ist ungültig oder FFmpeg ist nicht im PATH.
```

### Zielordner nicht erreichbar

```text
Der Aufnahmeordner ist nicht erreichbar.

Bitte prüfe, ob das Laufwerk verbunden ist.
Du kannst alternativ einen anderen Zielordner auswählen.

Admin-Hinweis:
recordings_base existiert nicht oder ist nicht lesbar.
```

### Mehrere Datumsordner

```text
Es gibt mehrere Ordner für dieses Datum.

Bitte wähle aus, welcher Ordner verwendet werden soll.
Das Programm entscheidet hier nicht automatisch, damit keine Dateien falsch abgelegt werden.
```
