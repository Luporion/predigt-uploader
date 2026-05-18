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

Alternativ in PowerShell:

```powershell
.\scripts\setup-local.ps1
```

Das Skript prüft Python, erstellt bei Bedarf `.venv` und installiert die benötigten Python-Abhängigkeiten.

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

Die Prüfung meldet verständlich, ob Python, `.venv`, der Wizard und FFmpeg verfügbar sind. Wenn in `config.toml` ein `losslesscut_path` gesetzt ist, wird auch dieser Pfad geprüft.

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
vmix_storage = "D:\\vMixStorage"
recordings_base = "C:\\Users\\DEIN-NAME\\Desktop\\Aufnahmen"
ffmpeg_path = "ffmpeg"
losslesscut_path = ""
```

Keine Zugangsdaten, Tokens, Passwörter oder privaten Schlüssel in `config.toml` eintragen.

## 7. Wizard starten

Für normale Nutzer:

```text
PredigtUploader starten.cmd
```

Diese Datei startet den Wizard per Doppelklick. Sie setzt automatisch den Projektordner als Arbeitsverzeichnis und lässt das Fenster nach Ende oder Fehler offen.

Alternativ in PowerShell:

```powershell
.\scripts\run-wizard.ps1
```

Der Wizard führt durch den lokalen Ablauf:

1. Ziel-Basisordner prüfen
2. fertige MP4 wählen oder LosslessCut-Schnitt-Assistent starten
3. Predigtdaten abfragen
4. MP4 in den Zielordner übernehmen
5. MP3 per FFmpeg erzeugen
6. Zusammenfassung und Logdatei schreiben

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
