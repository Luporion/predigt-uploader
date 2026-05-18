# Konfiguration

Die Standardkonfiguration liegt als Beispiel in `config.example.toml`.

Später mögliche Suchreihenfolge:

1. Pfad aus CLI-Argument `--config`
2. `config.toml` im Projekt-/Programmordner
3. `%APPDATA%\PredigtUploader\config.toml`
4. eingebaute Defaults

## Wichtige Werte

```toml
[paths]
vmix_storage = "V:\\vMixStorage"
recordings_base = "C:\\Users\\micro\\Desktop\\Aufnahmen"
mp3_base = "V:\\Predigten\\Predigten"
ffmpeg_path = "ffmpeg"
losslesscut_path = ""
```

`ffmpeg_path = "ffmpeg"` bedeutet: FFmpeg wird über PATH gefunden.

Die Zusammenfassung `predigt-zusammenfassung.txt` wird in Version 1 immer geschrieben. Es gibt dafür keine Config-Option.

## Sicherheit

Keine Tokens/Passwörter in `config.example.toml`.
Spätere Vimeo-/WordPress-Tokens müssen sicher gespeichert werden und dürfen nicht ins Repo.
