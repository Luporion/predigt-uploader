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

`recordings_base` ist der Ziel-Basisordner. Darunter legt der Wizard die Jahres- und Datumsordner an, zum Beispiel `2026\2026-05-24`.

Wenn keine `config.toml` vorhanden ist, nutzt Version 1 automatisch den Desktop des aktuellen Windows-Benutzers:

```text
%USERPROFILE%\Desktop\Aufnahmen
```

Beim Start zeigt der Wizard diesen Ziel-Basisordner an. Enter verwendet den Vorschlag, ein eingegebener Pfad verwendet einen anderen Ordner fuer den aktuellen Lauf. Wenn dieser Ordner noch nicht existiert, fragt der Wizard, ob er erstellt werden soll. Soll dauerhaft ein anderer Ordner vorgeschlagen werden, `recordings_base` in `config.toml` anpassen.

Die Zusammenfassung `predigt-zusammenfassung.txt` wird in Version 1 immer geschrieben. Es gibt dafür keine Config-Option.

Version 1 wertet nur die Optionen aus `config.example.toml` aus. Weitere Einstellungen sollten erst dokumentiert werden, wenn der Wizard sie tatsaechlich nutzt.

## Sicherheit

Keine Tokens/Passwörter in `config.example.toml`.
Spätere Vimeo-/WordPress-Tokens müssen sicher gespeichert werden und dürfen nicht ins Repo.
