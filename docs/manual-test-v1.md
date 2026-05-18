# Manueller Test: Version 1

Diese Anleitung beschreibt die erste lokale Testversion von Phase 1. Sie richtet sich an Admins oder technisch begleitete Tests auf einem Windows-Rechner.

Version 1 arbeitet nur lokal. Sie lädt nichts zu Vimeo hoch und legt nichts in WordPress an.

## Voraussetzungen

- Windows 10 oder Windows 11
- Python 3.11 oder neuer
- PowerShell
- Eine kleine MP4-Testdatei
- FFmpeg, wenn auch die MP3-Erzeugung getestet werden soll

Die MP4-Testdatei sollte keine echten vertraulichen Inhalte enthalten. Für einen ersten Test reicht eine kurze Beispiel-MP4.

## Python und virtuelle Umgebung einrichten

Im Projektordner:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
python -m pytest
```

Wenn `py -3.11` nicht gefunden wird, ist Python wahrscheinlich nicht installiert oder nicht korrekt im PATH eingetragen.

## FFmpeg-Anforderung

Für die MP3-Erzeugung braucht Version 1 FFmpeg. Der einfachste Test ist:

```powershell
ffmpeg -version
```

Wenn dieser Befehl funktioniert, kann der Wizard FFmpeg normalerweise über `ffmpeg_path = "ffmpeg"` finden.

Wenn FFmpeg fehlt, bereitet der Wizard die MP4 trotzdem im Zielordner vor und erklärt, wie die MP3 manuell erstellt werden kann.

## Optionale config.toml

Ohne eigene Config nutzt der Wizard eingebaute Standardwerte.

Der Ziel-Basisordner wird dann aus dem aktuellen Windows-Benutzer abgeleitet:

```text
%USERPROFILE%\Desktop\Aufnahmen
```

Optional kann `config.example.toml` kopiert werden:

```powershell
Copy-Item config.example.toml config.toml
```

Danach können lokale Pfade in `config.toml` angepasst werden. Keine Zugangsdaten, Tokens, API-Keys oder privaten Passwörter in die Config schreiben.

Wichtige Werte:

- `recordings_base`: Basisordner für Zielordner
- `ffmpeg_path`: Pfad zu FFmpeg oder `ffmpeg`, wenn FFmpeg im PATH liegt
- `copy_instead_of_move`: `true` bedeutet, die MP4 wird standardmäßig kopiert

Beispiel:

```toml
[paths]
recordings_base = "D:\\Predigt-Test\\Aufnahmen"
```

Der Wizard zeigt den vorgeschlagenen Ziel-Basisordner beim Start an. Drücke Enter, um diesen Ordner zu verwenden, oder gib direkt einen anderen Ordner ein. Für einen einzelnen Testlauf kann so ein anderer Ordner genutzt werden, ohne die `config.toml` zu ändern.

Wenn der eingegebene Ordner noch nicht existiert, fragt der Wizard, ob er erstellt werden soll.

## Wizard starten

Empfohlen über das Startskript:

```powershell
.\scripts\run-wizard.ps1
```

Alternativ direkt aus aktivierter `.venv`:

```powershell
python -m predigt_uploader wizard
```

## Test mit kleiner MP4 durchführen

1. Wizard starten.
2. Vorgeschlagenen Ziel-Basisordner prüfen: Enter verwendet den Vorschlag, ein eingegebener Pfad verwendet einen anderen Ordner.
3. Pfad zur kleinen MP4-Testdatei einfügen.
4. Datum eingeben oder den Vorschlag bestätigen.
5. Titel, Hauptbibelstelle und Redner eingeben.
6. Entscheiden, ob eine Besonderheit im Ordnernamen stehen soll.
7. Zielordner und finalen Dateinamen prüfen.
8. Dateiaktion ausdrücklich bestätigen.
9. Warten, bis die MP3-Erzeugung abgeschlossen ist oder der Wizard eine verständliche Fehlermeldung zeigt.

## Erwartete Ergebnisse im Zielordner

Im Zielordner sollten nach einem erfolgreichen Lauf liegen:

- die finale MP4-Datei
- die gleichnamige MP3-Datei
- `predigt-zusammenfassung.txt`

Der Wizard zeigt am Ende den Zielordner sowie die finalen Pfade zur MP4 und MP3 an. Der Erfolgsfall wird nur gemeldet, wenn MP4 und MP3 existieren und nicht leer sind.

## Logs

Pro Wizard-Lauf wird eine Logdatei im Projektordner unter `logs/` geschrieben.

Die Logdatei ist für Admin-Fehlersuche gedacht. Sie soll keine Zugangsdaten, Tokens oder sensiblen Daten enthalten.

## Was bei Fehlern zu tun ist

- Nutzerhinweis im Wizard lesen und den vorgeschlagenen Schritt ausführen.
- Prüfen, ob die MP4-Datei noch existiert und nicht in einem anderen Programm geöffnet ist.
- Prüfen, ob der Ziel-Basisordner und der Zielordner beschreibbar sind.
- Bei MP3-Problemen prüfen, ob `ffmpeg -version` funktioniert.
- Admin-Hinweis und passende Logdatei unter `logs/` prüfen.

Wenn der Fehler unklar bleibt: kurze Beschreibung, Uhrzeit des Tests, verwendete Testdatei und die passende Logdatei sammeln. Keine Zugangsdaten oder privaten Tokens weitergeben.
