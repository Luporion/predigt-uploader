# Konfiguration

Die Standardkonfiguration liegt als Beispiel in `config.example.toml`.

Suchreihenfolge:

1. Pfad aus CLI-Argument `--config`
2. `config.toml` im Projekt-/Programmordner
3. `%APPDATA%\PredigtUploader\config.toml`
4. eingebaute Defaults

## Wichtige Werte

```toml
[paths]
vmix_storage = "V:\\vMixStorage"
recordings_base = "C:\\Users\\DEIN-NAME\\Desktop\\Aufnahmen"
mp3_base = "V:\\Predigten\\Predigten"
ffmpeg_path = "ffmpeg"
losslesscut_path = ""
```

`ffmpeg_path = "ffmpeg"` bedeutet: FFmpeg wird über PATH gefunden.

`losslesscut_path = ""` bedeutet: Der Wizard versucht LosslessCut über PATH oder den Windows-App-Alias `LosslessCut` zu starten. Wenn LosslessCut dort nicht gefunden wird, kann hier ein vollständiger Pfad eingetragen werden, zum Beispiel:

```toml
[paths]
losslesscut_path = "C:\\Tools\\LosslessCut\\LosslessCut.exe"
```

Wenn LosslessCut beim Wizard-Start nicht gefunden wird, kann der Pfad zur `LosslessCut.exe` auch direkt im Wizard eingegeben werden. Das gilt nur für diesen Lauf. Soll der Pfad dauerhaft gelten, `losslesscut_path` in `config.toml` setzen.

Bei einer portablen ZIP-Version liegt die Datei meist im entpackten Ordner, zum Beispiel:

```text
D:\Programme\LosslessCut\LosslessCut.exe
```

In `config.toml` muss der Pfad mit doppelten Backslashes geschrieben werden:

```toml
[paths]
losslesscut_path = "D:\\Programme\\LosslessCut\\LosslessCut.exe"
```

Bei einer einmaligen Eingabe im Wizard sind auch Anführungszeichen erlaubt, zum Beispiel `"D:\Programme\LosslessCut\LosslessCut.exe"`.

`vmix_storage` ist der Quellordner fuer Rohaufnahmen. Der LosslessCut-Assistent kann daraus die neueste MP4 als Rohaufnahme vorschlagen.

`recordings_base` ist der Ziel-Basisordner. Darunter legt der Wizard die Jahres- und Datumsordner an, zum Beispiel `2026\2026-05-24`.

Wenn keine `config.toml` vorhanden ist, nutzt Version 1 automatisch den Desktop des aktuellen Windows-Benutzers:

```text
%USERPROFILE%\Desktop\Aufnahmen
```

Beim Start zeigt der Wizard diesen Ziel-Basisordner an. Enter verwendet den Vorschlag, ein eingegebener Pfad verwendet einen anderen Ordner fuer den aktuellen Lauf. Wenn dieser Ordner noch nicht existiert, fragt der Wizard, ob er erstellt werden soll. Soll dauerhaft ein anderer Ordner vorgeschlagen werden, `recordings_base` in `config.toml` anpassen.

Die Zusammenfassung `predigt-zusammenfassung.txt` wird in Version 1 immer geschrieben. Es gibt dafür keine Config-Option.

Version 1 wertet nur die Optionen aus `config.example.toml` aus. Weitere Einstellungen sollten erst dokumentiert werden, wenn der Wizard sie tatsaechlich nutzt.

## Terminal-Auswahl

Der Wizard nutzt nach Möglichkeit `questionary` für Pfeiltasten-Auswahlen. Wenn das Terminal nicht geeignet ist oder `questionary` nicht verfügbar ist, nutzt der Wizard automatisch die Texteingabe.

Textmodus erzwingen:

```powershell
$env:PREDIGT_UPLOADER_TEXT_UI = "1"
```

## Sicherheit

Keine Tokens/Passwörter in `config.example.toml`.
Spätere Vimeo-/WordPress-Tokens müssen sicher gespeichert werden und dürfen nicht ins Repo.
