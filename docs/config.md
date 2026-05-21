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
cut_mp4_folder = ""
mp3_base = "V:\\Predigten\\Predigten"
ffmpeg_path = "ffmpeg"
losslesscut_path = ""

[naming]
year_folder_template = "{year}"

[workflow]
copy_instead_of_move = true
open_target_folder = true
raw_archive_mode = "move"
```

`ffmpeg_path = "ffmpeg"` bedeutet: FFmpeg wird über PATH gefunden.

`losslesscut_path = ""` bedeutet: Der Wizard versucht LosslessCut über PATH oder den Windows-App-Alias `LosslessCut` zu starten. Wenn LosslessCut dort nicht gefunden wird, kann hier ein vollständiger Pfad eingetragen werden, zum Beispiel:

```toml
[paths]
losslesscut_path = "C:\\Tools\\LosslessCut\\LosslessCut.exe"
```

Wenn LosslessCut beim Wizard-Start nicht gefunden wird, kann der Pfad zur `LosslessCut.exe` auch direkt im Wizard eingegeben werden. Der Wizard fragt dann zuerst, ob dieser Pfad künftig gemerkt werden soll, und startet LosslessCut erst danach. Gespeichert wird auf Wunsch unter `%APPDATA%\PredigtUploader\config.toml`.

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

`vmix_storage` ist der Standardordner fuer Rohaufnahmen, zum Beispiel:

```toml
[paths]
vmix_storage = "V:\\vMixStorage"
```

`V:\vMixStorage` ist nur ein eingebauter Standardwert und ein typischer Beispielpfad aus dem Gemeinde-Workflow. Wenn dieser Ordner auf einem Rechner nicht existiert, ist das kein Fehler im Video selbst. Der Wert sollte dann dauerhaft in `config.toml` oder auf Wunsch im Wizard unter `%APPDATA%\PredigtUploader\config.toml` angepasst werden.

Auf dem Gemeinderechner ist ein UNC-Pfad oft robuster als ein gemapptes Laufwerk wie `V:`. Gemappte Laufwerke koennen je nach angemeldetem Windows-Benutzer oder Startart fehlen. Ein UNC-Pfad zeigt direkt auf die Netzwerkfreigabe:

```toml
[paths]
vmix_storage = "\\\\SERVER\\Freigabe\\vMixStorage"
```

In `config.example.toml` stehen nur Beispielpfade. Echte Gemeinde-Pfade gehoeren nur in die lokale `config.toml` auf dem Zielrechner.

Der LosslessCut-Assistent nutzt diesen Ordner, damit Nutzer nicht manuell suchen muessen. Wenn der Ordner vorhanden ist, schlaegt der Wizard zuerst die neueste plausible Rohaufnahme vor. Bereits geschnitten wirkende Dateien wie `_geschnitten` oder fertige `Predigt (...)_Redner.mp4`-Dateien werden dabei niedriger priorisiert und bei Auswahl mit einer Warnung bestaetigt.

Alternativ koennen die neuesten Aufnahmen angezeigt, Dateinamen gesucht/gefiltert oder ein anderer Datei-/Ordnerpfad eingegeben werden. Bei sehr vielen Dateien zeigt der Wizard nur eine begrenzte Liste und weist darauf hin. Die Suche nutzt nach Moeglichkeit eine Live-Auswahl ueber `questionary`; im Textmodus bleibt der Fallback mit Suchtext und Ergebnisliste erhalten.

Wenn `vmix_storage` fehlt oder nicht erreichbar ist, meldet der Wizard das verstaendlich und erlaubt eine manuelle Auswahl. Wird dabei ein Ordner eingegeben, verwendet der Wizard diesen Ordner nur fuer den aktuellen Lauf als temporaeren Rohaufnahme-Quellordner und zeigt danach wieder das normale Rohaufnahme-Menue mit neuester Aufnahme, neuesten Aufnahmen, Suche/Filter, manueller Eingabe und Abbruch.

Wenn der Rohaufnahme-Ordner im Wizard geaendert wird, kann der Wizard ihn unter `%APPDATA%\PredigtUploader\config.toml` merken. Diese Benutzer-Config liegt nicht im Repository und nicht zwingend in der Release-ZIP.

`cut_mp4_folder` ist der zuletzt gemerkte Ordner fuer bereits fertig geschnittene oder exportierte MP4-Dateien. Standard ist leer:

```toml
[paths]
cut_mp4_folder = ""
```

Wenn Nutzer im Wizard bei „Hast du bereits eine fertig geschnittene MP4-Datei?“ mit Ja antworten, nutzt der Wizard als vorgeschlagenen Ordner zuerst `cut_mp4_folder`, danach `vmix_storage`, danach `recordings_base`. Im vorgeschlagenen Ordner gibt es ein Menue zum Suchen/Auswaehlen, zum Verwenden der neuesten geschnittenen MP4, zur Auswahl aus den neuesten MP4-Dateien, zur manuellen Eingabe und fuer „Zurueck“.

Dateien mit `_geschnitten`, `geschnitten` oder einem fertigen Predigt-Dateinamen wie `Predigt (Titel_Bibelstelle)_Redner.mp4` werden bevorzugt angezeigt. Wenn keine eindeutig geschnittene Datei gefunden wird, zeigt der Wizard trotzdem MP4-Dateien an und weist darauf hin, dass bewusst die richtige Predigtdatei gewaehlt werden muss.

Wenn im Wizard ein anderer Ordner fuer geschnittene MP4-Dateien eingegeben wird, kann dieser Ordner unter `%APPDATA%\PredigtUploader\config.toml` gemerkt werden. Eine direkt eingegebene Datei wird weiterhin darauf geprueft, ob sie existiert, eine Datei ist und die Endung `.mp4` hat.

`recordings_base` ist der Ziel-Basisordner. Darunter legt der Wizard die Jahres- und Datumsordner an, zum Beispiel `2026\2026-05-24`.

Soll der Ziel-Basisordner dauerhaft geaendert werden, entweder `recordings_base` in `config.toml` setzen oder im Wizard beim abweichenden Ordner das Merken bestaetigen.

`year_folder_template` steuert den Namen des Jahresordners. Standard ist `{year}`. Auf dem Gemeinderechner kann zum Beispiel gesetzt werden:

```toml
[naming]
year_folder_template = "{year} Video+Audio"
```

Dann entsteht unter `recordings_base` zum Beispiel:

```text
2026 Video+Audio\2026-05-17
```

Wenn keine `config.toml` vorhanden ist, nutzt Version 1 automatisch den Desktop des aktuellen Windows-Benutzers:

```text
%USERPROFILE%\Desktop\Aufnahmen
```

Beim Start zeigt der Wizard diesen Ziel-Basisordner an. Enter verwendet den Vorschlag, ein eingegebener Pfad verwendet einen anderen Ordner fuer den aktuellen Lauf. Wenn dieser Ordner noch nicht existiert, fragt der Wizard, ob er erstellt werden soll. Soll dauerhaft ein anderer Ordner vorgeschlagen werden, `recordings_base` in `config.toml` anpassen oder im Wizard das Merken unter `%APPDATA%\PredigtUploader\config.toml` bestaetigen.

Die Zusammenfassung `predigt-zusammenfassung.txt` wird in Version 1 immer geschrieben. Es gibt dafür keine Config-Option.

`open_target_folder = true` bedeutet: Nach erfolgreicher Verarbeitung oeffnet der Wizard den Zielordner im Explorer. Wenn das auf einem Rechner stoert, kann der Wert auf `false` gesetzt werden.

`raw_archive_mode` steuert die Vorauswahl beim Aufraeumen der Rohaufnahme nach erfolgreichem Lauf:

```toml
[workflow]
raw_archive_mode = "move" # verschieben
```

Moegliche Werte sind `move`, `none` und `copy`. Fuer normale Rohaufnahmen ist `move` sinnvoll, damit `vMixStorage` frei bleibt. Wenn die Datei bereits geschnitten wirkt, bleibt der Wizard aus Sicherheitsgruenden trotzdem bei der sicheren Vorauswahl „liegen lassen“.

## Einstellungen im Startmenue

Normale Nutzer muessen `config.toml` nicht manuell bearbeiten. Im Hauptmenue gibt es „Einstellungen ändern“. Dort koennen Ziel-Basisordner, Rohaufnahme-Ordner, LosslessCut-Pfad, Jahresordner-Format und Rohaufnahme-Aufraeumen geaendert werden. Gespeichert wird unter:

```text
%APPDATA%\PredigtUploader\config.toml
```

Beim Jahresordner kann zwischen „nur Jahr“ und „Jahr mit Zusatz“ gewaehlt werden. Die Auswahl „2026 Video+Audio“ speichert intern:

```toml
[naming]
year_folder_template = "{year} Video+Audio"
```

Version 1 wertet nur die Optionen aus `config.example.toml` aus. Weitere Einstellungen sollten erst dokumentiert werden, wenn der Wizard sie tatsaechlich nutzt.

## Terminal-Auswahl

Der Wizard nutzt nach Möglichkeit `questionary` für Pfeiltasten-Auswahlen. Wenn das Terminal nicht geeignet ist oder `questionary` nicht verfügbar ist, nutzt der Wizard automatisch die Texteingabe.

Textmodus erzwingen:

```powershell
$env:PREDIGT_UPLOADER_TEXT_UI = "1"
```

Bei Dateipfad-Abfragen darf statt einer Datei auch ein Ordner eingegeben werden. Der Wizard zeigt dann passende Dateien direkt aus diesem Ordner an, zum Beispiel `.mp4` bei Video-Abfragen oder `.exe` bei `LosslessCut.exe`. Es wird bewusst nicht rekursiv in Unterordnern gesucht.

## Sicherheit

Keine Tokens/Passwörter in `config.example.toml`.
Spätere Vimeo-/WordPress-Tokens müssen sicher gespeichert werden und dürfen nicht ins Repo.
