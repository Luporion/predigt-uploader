# Installation: lokale Version 1.5

Diese Anleitung richtet den PredigtUploader auf einem Windows-Zielrechner ein. Version 1.5 arbeitet nur lokal: Sie automatisiert keinen Vimeo-Upload und keine WordPress-Einträge.

## Voraussetzungen

- Windows 10 oder Windows 11
- Projektordner `predigt-uploader`
- Internetzugang für die erste Python-Installation der Abhängigkeiten
- Python 3.11 oder neuer
- FFmpeg für die MP3-Erzeugung
- LosslessCut für den manuellen Schnitt

## 1. Python installieren

Python 3.11 oder neuer von python.org installieren.

Wichtig: Beim Installieren die Option `Add Python to PATH` aktivieren.

Danach PowerShell öffnen und im Projektordner prüfen:

```powershell
py -3.11 --version
```

Wenn dieser Befehl nicht funktioniert, alternativ:

```powershell
python --version
```

## 2. PredigtUploader lokal einrichten

Normale Nutzer sollen im Projektordner diese Datei doppelklicken:

```text
PredigtUploader einrichten.cmd
```

Diese Startdatei öffnet PowerShell automatisch und führt `scripts/setup-local.ps1` aus. Am Ende bleibt das Fenster offen, damit die Meldung gelesen werden kann.
Die Startdateien stellen die Konsole auf UTF-8 um. Die wichtigsten Meldungen sind außerdem so formuliert, dass sie auch auf älteren Windows-Konsolen lesbar bleiben.

Alternativ in PowerShell:

```powershell
.\scripts\setup-local.ps1
```

Das Skript prüft Python, erstellt bei Bedarf `.venv` und installiert die benötigten Python-Abhängigkeiten.
Danach prüft es auch FFmpeg. FFmpeg ist nötig, damit der Wizard aus der MP4 eine MP3 erstellen kann.

Wenn FFmpeg fehlt und `winget` verfügbar ist, fragt das Setup ausdrücklich, ob FFmpeg automatisch installiert werden soll. Die Installation passiert nicht still. Wenn du zustimmst, kann Windows weitere Rückfragen anzeigen.

Wichtig: Nach einer FFmpeg-Installation muss oft ein neues PowerShell-Fenster geöffnet werden, damit Windows den neuen PATH kennt. Danach bitte den Systemcheck erneut starten.

Wenn `winget` nicht verfügbar ist oder die automatische Installation nicht klappt, zeigt das Setup eine manuelle Anleitung. Alternativ kann ein Admin später in `config.toml` einen festen Pfad setzen:

```toml
[paths]
ffmpeg_path = "C:\\Tools\\ffmpeg\\bin\\ffmpeg.exe"
```

Wenn PowerShell das Skript wegen Ausführungsrichtlinien blockiert, kann es für diesen Start so aufgerufen werden:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local.ps1
```

## 3. System prüfen

Nach der Einrichtung diese Datei doppelklicken:

```text
PredigtUploader Systemcheck.cmd
```

Diese Datei prüft, ob die lokale Umgebung startbereit ist.

Alternativ in PowerShell:

```powershell
.\scripts\check-system.ps1
```

Die Prüfung meldet verständlich, ob Python, `.venv`, der Wizard und FFmpeg verfügbar sind. Wenn FFmpeg direkt vorher installiert wurde und noch fehlt, ein neues PowerShell-Fenster öffnen und erneut prüfen. Wenn in `config.toml` ein `losslesscut_path` gesetzt ist, wird auch dieser Pfad geprüft.

## 4. FFmpeg installieren

FFmpeg muss verfügbar sein, damit aus der MP4 eine MP3 erzeugt werden kann.

Mögliche Wege:

- FFmpeg installieren und in PATH aufnehmen.
- Oder einen festen Pfad in `config.toml` setzen:

```toml
[paths]
ffmpeg_path = "C:\\Tools\\ffmpeg\\bin\\ffmpeg.exe"
```

Danach erneut ausführen:

```powershell
.\scripts\check-system.ps1
```

## 5. LosslessCut installieren oder portable ZIP nutzen

LosslessCut kann normal installiert oder als portable ZIP-Version genutzt werden.

Bei der ZIP-Version:

1. ZIP-Datei in einen festen Ordner entpacken, zum Beispiel `C:\Tools\LosslessCut`.
2. In diesem Ordner `LosslessCut.exe` suchen.
3. Den Pfad in `config.toml` setzen.

Beispiel:

```toml
[paths]
losslesscut_path = "C:\\Tools\\LosslessCut\\LosslessCut.exe"
```

Wenn kein `losslesscut_path` gesetzt ist, versucht der Wizard später LosslessCut über PATH oder Windows-App-Alias zu starten. Falls das nicht klappt, fragt er den Pfad im Wizard ab.

## 6. config.toml erstellen

Die Beispielkonfiguration kopieren:

```powershell
Copy-Item .\config.example.toml .\config.toml
```

Danach `config.toml` prüfen und bei Bedarf anpassen:

```toml
[paths]
vmix_storage = "V:\\vMixStorage"
recordings_base = "C:\\Users\\DEIN-NAME\\Desktop\\Aufnahmen"
cut_mp4_folder = ""
ffmpeg_path = "ffmpeg"
losslesscut_path = ""

[naming]
year_folder_template = "{year}"
predigt_template = "Predigt ({title}_{bible_reference})_{speaker}{extension}"
bibelstunde_template = "Bibelstunde ({bible_reference})_{speaker}{extension}"
vortrag_template = "Vortrag ({title})_{speaker}{extension}"
lobpreis_template = "Lobpreis ({title}){speaker_suffix}{extension}"
sonstiges_template = "{service_type} ({title}){speaker_suffix}{extension}"

[workflow]
open_target_folder = true
raw_archive_mode = "move"

[service_types]
additional = []
```

`vmix_storage` ist der Standardordner für Rohaufnahmen. Der Wizard nutzt diesen Ordner, damit Nutzer nicht selbst durch alte Aufnahmen suchen müssen. Bereits geschnitten wirkende Dateien werden nicht als beste Rohaufnahme bevorzugt und müssen bei Auswahl extra bestätigt werden. Wenn der Ordner fehlt, erklärt der Wizard das und erlaubt eine manuelle Datei- oder Ordnerauswahl.

`cut_mp4_folder` kann leer bleiben. Wenn Nutzer bereits eine fertig geschnittene MP4-Datei haben, schlägt der Wizard zuerst den zuletzt gemerkten Schnitt-/Exportordner vor, sonst `vmix_storage`, sonst `recordings_base`. In diesem Ordner können sie suchen, die neueste geschnittene MP4 verwenden, aus den neuesten MP4-Dateien wählen oder einen anderen Ordner beziehungsweise eine Datei eingeben.

Wenn Nutzer im Wizard einen anderen Ziel-Basisordner, Rohaufnahme-Ordner, Schnitt-/Exportordner oder einen funktionierenden LosslessCut-Pfad angeben, kann der Wizard diese Werte künftig unter `%APPDATA%\PredigtUploader\config.toml` merken. Diese Benutzer-Config liegt außerhalb des Projektordners und gehört nicht in die Release-ZIP.

Für Netzwerkordner ist ein UNC-Pfad meist robuster als ein gemapptes Laufwerk wie `V:`, weil gemappte Laufwerke je nach Windows-Benutzer fehlen können. Beispiel:

```toml
[paths]
vmix_storage = "\\\\SERVER\\Freigabe\\vMixStorage"
```

`open_target_folder = true` öffnet nach erfolgreicher Verarbeitung den Zielordner automatisch im Explorer. Bei Bedarf kann der Wert auf `false` gesetzt werden.

`year_folder_template` steuert den Namen des Jahresordners unterhalb von `recordings_base`. Standard ist `{year}`. Für Gemeinderechner mit Ordnern wie `2026 Video+Audio` kann gesetzt werden:

```toml
[naming]
year_folder_template = "{year} Video+Audio"
```

Keine Zugangsdaten, Tokens, Passwörter oder privaten Schlüssel in `config.toml` eintragen.

Normale Nutzer können diese Werte später auch im Startmenü unter „Einstellungen ändern“ setzen. Der Wizard speichert sie dann in `%APPDATA%\PredigtUploader\config.toml`.

Im Einstellungsmenü können zusätzlich Dienstarten verwaltet werden. Standardmäßig gibt es Predigt, Bibelstunde, Vortrag, Lobpreis, Gebetsstunde, Zeugnis, Seminar und Sonstiges. Zusätzliche Dienstarten werden nur in der Benutzer-Config unter `%APPDATA%\PredigtUploader\config.toml` gespeichert.

## 7. Wizard starten

Für normale Nutzer:

```text
PredigtUploader starten.cmd
```

Diese Datei startet per Doppelklick ein einfaches Hauptmenü. Dort kann man eine neue Predigt vorbereiten, Einstellungen ändern, den Systemcheck-Hinweis anzeigen oder Logs öffnen. Sie setzt automatisch den Projektordner als Arbeitsverzeichnis und lässt das Fenster nach Ende oder Fehler offen.

Wichtig: `Strg+C` bricht den laufenden Vorgang ab. Zum Zurückgehen im Wizard bitte die Option „Zurück“ verwenden. Beim Start per `.cmd` kann Windows nach `Strg+C` zusätzlich „Batchvorgang abbrechen (J/N)?“ anzeigen.

Alternativ in PowerShell:

```powershell
.\scripts\run-wizard.ps1
```

Der Wizard führt durch den lokalen Ablauf:

1. Ziel-Basisordner prüfen
2. fertige MP4 über den vorgeschlagenen Schnitt-/Exportordner wählen oder LosslessCut-Schnitt-Assistent starten
3. Datum, Dienstart und passende Metadaten abfragen
4. MP4 in den Zielordner übernehmen
5. MP3 per FFmpeg erzeugen
6. Zusammenfassung und Logdatei schreiben
7. optional die Rohaufnahme in den Zielordner verschieben oder kopieren
8. Zielordner automatisch öffnen

Erfahrene Nutzer können den langen Workflow direkt starten:

```powershell
.\scripts\run-wizard.ps1 wizard
```

Später kann auf dem Desktop eine Verknüpfung zu `PredigtUploader starten.cmd` erstellt werden. Die Datei selbst sollte im Projektordner bleiben, damit sie die Skripte zuverlässig findet.

## 8. Testdurchlauf

Für den ersten Test eine kleine MP4-Datei verwenden.

Erwartetes Ergebnis im Zielordner:

- finale MP4
- gleichnamige MP3
- `predigt-zusammenfassung.txt`

Zusätzlich liegt im Projektordner eine Logdatei unter `logs/`.

## Fehlerhilfe

- Wenn Python fehlt: Python 3.11 oder neuer installieren und `setup-local.ps1` erneut starten.
- Wenn `.venv` fehlt: `.\scripts\setup-local.ps1` ausführen.
- Wenn FFmpeg fehlt: FFmpeg installieren oder `ffmpeg_path` in `config.toml` setzen.
- Wenn LosslessCut nicht startet: `losslesscut_path` in `config.toml` setzen oder den Pfad im Wizard eingeben.
- Bei technischen Details die Logdatei unter `logs/` prüfen.
