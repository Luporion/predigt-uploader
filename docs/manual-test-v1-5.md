# Manueller Test: Phase 1.5 LosslessCut-Schnitt-Assistent

Diese Anleitung beschreibt den lokalen Schnitt-Assistenten. Er automatisiert weder Vimeo noch WordPress und ersetzt keinen Video-Editor. LosslessCut bleibt das externe Schnittprogramm.

## Voraussetzungen

- eingerichtete Phase-1-Testversion
- eine kleine vMix-/Rohaufnahme als MP4
- LosslessCut installiert
- FFmpeg, wenn nach dem Schnitt auch die MP3-Erzeugung getestet werden soll

## Optionale config.toml

Der Assistent nutzt diese Werte:

```toml
[paths]
vmix_storage = "D:\\vMixStorage"
recordings_base = "C:\\Users\\DEIN-NAME\\Desktop\\Aufnahmen"
losslesscut_path = ""

[naming]
year_folder_template = "{year}"

[workflow]
raw_archive_mode = "move"
```

`vmix_storage` ist der Ordner mit Rohaufnahmen. Der Wizard schlägt daraus die neueste MP4 vor.
Wenn dort viele alte Dateien liegen, zeigt der Wizard nicht sofort alle MP4-Dateien an. Erwartet wird:

- neueste Aufnahme verwenden
- in den neuesten Aufnahmen auswählen
- suchen/filtern
- Datei/Ordner manuell eingeben
- abbrechen

Bei der Liste der neuesten Aufnahmen werden nur die neuesten Dateien angezeigt. Bereits geschnitten wirkende Dateien, zum Beispiel mit `_geschnitten` im Namen oder fertige `Predigt (...)_Redner.mp4`-Dateien, werden nicht als beste Rohaufnahme bevorzugt. Wenn nur so eine Datei gewählt wird, fragt der Wizard ausdrücklich nach, ob das wirklich die vollständige Rohaufnahme ist.

Bei der Suche nutzt der Wizard nach Möglichkeit eine Live-Suche: Suchtext tippen, Treffer werden enger, Auswahl per Pfeiltasten. Ein leeres Suchfeld zeigt die begrenzte vollständige Liste. Wenn das Terminal diese Suche nicht unterstützt oder der Textmodus aktiv ist, bleibt der robuste Fallback erhalten: Suchtext eingeben, Ergebnisliste anzeigen, Nummer auswählen. Bei sehr vielen Treffern erscheint ein Hinweis.

`recordings_base` ist der Ziel-Basisordner. Der Wizard fragt beim Start, ob ein abweichender Ziel-Basisordner künftig gemerkt werden soll. Gespeichert wird dann unter `%APPDATA%\PredigtUploader\config.toml`, nicht im Repository. Mit `year_folder_template = "{year} Video+Audio"` kann der Jahresordner zum Beispiel `2026 Video+Audio` heißen.

Im Startmenü können normale Nutzer Einstellungen ändern, ohne `config.toml` von Hand zu bearbeiten:

- Ziel-Basisordner
- Rohaufnahme-Ordner / vMixStorage
- LosslessCut-Pfad
- Jahresordner-Format
- Rohaufnahme nach Erfolg: verschieben, liegen lassen oder kopieren

`losslesscut_path = ""` bedeutet: LosslessCut wird über PATH oder Windows-App-Alias gestartet. Wenn das nicht klappt, kann ein vollständiger Pfad eingetragen werden.

Wenn LosslessCut als portable ZIP-Version genutzt wird:

1. ZIP-Datei in einen festen Ordner entpacken, z. B. `D:\Programme\LosslessCut`.
2. In diesem Ordner `LosslessCut.exe` suchen.
3. Optional den Pfad dauerhaft in `config.toml` eintragen:

```toml
[paths]
losslesscut_path = "D:\\Programme\\LosslessCut\\LosslessCut.exe"
```

Wenn `losslesscut_path` leer bleibt und der automatische Start fehlschlägt, fragt der Wizard den Pfad zur `LosslessCut.exe` direkt ab. Der Wizard fragt zuerst, ob der Pfad künftig unter `%APPDATA%\PredigtUploader\config.toml` gemerkt werden soll, und startet LosslessCut erst danach. So wird die Frage nicht von LosslessCut-Ausgaben überlagert.

Bei der direkten Eingabe im Wizard sind Anführungszeichen erlaubt, zum Beispiel:

```text
"D:\Programme\LosslessCut\LosslessCut.exe"
```

Wenn versehentlich nur der Ordner eingegeben wird, in dem `LosslessCut.exe` liegt, zeigt der Wizard passende `.exe`-Dateien aus diesem Ordner zur Auswahl an.

Keine Zugangsdaten, Tokens oder privaten Passwörter in die Config schreiben.

## Testablauf

1. PredigtUploader starten:

```powershell
.\scripts\run-wizard.ps1
```

2. Im Hauptmenü „Neue Predigt vorbereiten“ wählen. Enter nimmt die erste Option.
3. Ziel-Basisordner bestätigen oder für den Testlauf ändern.
4. Bei der Frage nach einer fertig geschnittenen MP4 mit `nein` antworten.
5. Vorgeschlagene neueste Rohaufnahme aus `vmix_storage` verwenden, aus den neuesten Aufnahmen auswählen, suchen/filtern oder einen MP4-Pfad manuell eingeben. Wenn nur ein Ordner eingegeben wird, zeigt der Wizard dieselbe begrenzte Auswahl- und Suchlogik wie bei konfigurierten Ordnern.
   Wenn `vmix_storage` nicht erreichbar ist und ein Ordner manuell eingegeben wird, soll danach trotzdem das normale Rohaufnahme-Menü erscheinen. Dort müssen „Neueste Aufnahme verwenden“, „In den neuesten Aufnahmen auswählen“, „Suchen/filtern“, „Datei/Ordner manuell eingeben“ und „Abbrechen“ verfügbar sein.
6. Der Wizard öffnet LosslessCut mit der Rohaufnahme. Ausgaben von LosslessCut sollen nicht in das Wizard-Terminal schreiben.
7. In LosslessCut nur den Predigtbereich markieren.
8. Nur die Predigt als MP4 exportieren.
9. Chorlieder, Beiträge oder Ansagen nicht als Predigtdatei verwenden.
10. Nach dem Export LosslessCut schließen oder zum Wizard zurückkehren und Enter drücken. Wenn der Wizard den gestarteten LosslessCut-Prozess beobachten kann, läuft er nach dem Schließen automatisch weiter.
11. Wenn mehrere neue MP4-Dateien gefunden werden, bewusst die richtige Predigtdatei auswählen. Der Wizard vergleicht dafür einen MP4-Snapshot vor dem Export mit dem Zustand danach und priorisiert zusätzlich plausible LosslessCut-Dateinamen mit Bezug zur Rohaufnahme, zum Beispiel `_geschnitten_<Rohdateiname>...mp4`.
12. Wenn keine Datei gefunden wird, den exportierten MP4-Pfad manuell eingeben. Wenn ein Ordner wie `V:\vMixStorage` eingegeben wird, soll der Wizard zuerst neue Dateien seit Start des Assistenten zeigen. Sonst werden neueste/geschnittene Dateien bevorzugt angezeigt; Dateien mit `_geschnitten` oder typischem LosslessCut-Zeitbereich im Namen sollen oben stehen.
13. Danach läuft der bekannte lokale Workflow weiter: Datum, Metadaten, Zielordner, MP4 übernehmen, MP3 erzeugen, Zusammenfassung, Log. Bei längeren Dateiaktionen zeigt der Wizard eine kurze Bitte-warten-Meldung.
14. Nach erfolgreichem Lauf fragt der Wizard optional, ob die Rohaufnahme im Zielordner archiviert werden soll. Bei normal wirkenden Rohaufnahmen ist „Ja, Rohaufnahme in Zielordner verschieben“ vorausgewählt. Verschieben warnt vorher deutlich und erfordert eine zweite Bestätigung, weil die Datei aus `vmix_storage` entfernt wird. Wenn die bekannte Rohaufnahme bereits geschnitten wirkt, warnt der Wizard zusätzlich; dann bleibt „liegen lassen“ die sichere Vorauswahl.
15. Am Ende soll sich der Zielordner im Explorer öffnen. Wenn das nicht klappt, bleibt der Workflow trotzdem erfolgreich und es erscheint nur ein verständlicher Hinweis.

Bei der Datumsauswahl bietet der Wizard nach Möglichkeit das Aufnahmedatum aus typischen vMix-Dateinamen an, zum Beispiel aus `Gottesdienst - 10 Mai 2026 - 09-55-08.mp4`. Falls kein Datum im Dateinamen erkannt wird, kann das Dateidatum der MP4 angeboten werden. Alternativ können immer das heutige Datum oder ein anderes Datum per Hand gewählt werden.

Wenn die finale MP4-Datei im Zielordner bereits existiert, überschreibt der Wizard sie nicht automatisch. Es gibt eine bewusste Auswahl:

- vorhandene Datei behalten und ohne Kopieren/Verschieben weiterarbeiten
- neuen Dateinamen verwenden
- abbrechen
- überschreiben

Überschreiben ersetzt die vorhandene Datei und muss deshalb zusätzlich bestätigt werden.

Bei Ja/Nein-Fragen und mehreren gefundenen MP4-Dateien nutzt der Wizard nach Möglichkeit eine stabile Pfeiltasten-Auswahl über `questionary`. Die Auswahl ist bewusst kontrastreich gestaltet. Falls das Terminal dies nicht unterstützt, funktioniert weiterhin die Texteingabe mit `ja`/`nein` oder nummerierter Auswahl.

Falls die Pfeiltasten-Auswahl im Terminal Probleme macht, kann der Textmodus vor dem Start erzwungen werden:

```powershell
$env:PREDIGT_UPLOADER_TEXT_UI = "1"
.\scripts\run-wizard.ps1
```

## Erwartetes Ergebnis

Im Zielordner liegen nach erfolgreichem Lauf:

- finale MP4
- gleichnamige MP3
- `predigt-zusammenfassung.txt`
- optional die Rohaufnahme, wenn Kopieren oder Verschieben ausgewählt wurde

Im Projektordner liegt zusätzlich eine Logdatei unter `logs/`.

## Fehlerhilfe

- Wenn LosslessCut nicht startet: Pfad zur `LosslessCut.exe` im Wizard eingeben, `losslesscut_path` in `config.toml` prüfen oder LosslessCut manuell öffnen.
- Wenn keine neue MP4 gefunden wird: exportierten Pfad manuell eingeben.
- Wenn versehentlich ein Ordner statt einer Datei eingegeben wurde: passende Datei aus der angezeigten Liste auswählen oder einen anderen Pfad eingeben.
- Wenn gespeicherte Ordner falsch sind: `%APPDATA%\PredigtUploader\config.toml` prüfen oder im Wizard einen anderen Ordner wählen und erneut merken lassen.
- Wenn mehrere MP4-Dateien gefunden werden: nur die Datei auswählen, die wirklich die Predigt enthält.
- Bei technischen Details den Admin-Hinweis und die Logdatei prüfen.
