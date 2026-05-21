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
cut_mp4_folder = ""
losslesscut_path = ""

[naming]
year_folder_template = "{year}"
predigt_template = "Predigt ({title}_{bible_reference})_{speaker}{extension}"
bibelstunde_template = "Bibelstunde ({bible_reference})_{speaker}{extension}"
vortrag_template = "Vortrag ({title})_{speaker}{extension}"
lobpreis_template = "Lobpreis ({title}){speaker_suffix}{extension}"
sonstiges_template = "{service_type} ({title}){speaker_suffix}{extension}"

[workflow]
raw_archive_mode = "move"

[service_types]
additional = []
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

In Suchfeldern muss sichtbar sein:

```text
Tippe zum Suchen. Wähle 'Zurück', wenn du zum vorherigen Menü möchtest.
```

Im Textmodus muessen `zurück`, `z` und `back` ins vorherige Menue zurueckfuehren, nicht den ganzen Wizard abbrechen.

`recordings_base` ist der Ziel-Basisordner. Der Wizard fragt beim Start, ob ein abweichender Ziel-Basisordner künftig gemerkt werden soll. Gespeichert wird dann unter `%APPDATA%\PredigtUploader\config.toml`, nicht im Repository. Mit `year_folder_template = "{year} Video+Audio"` kann der Jahresordner zum Beispiel `2026 Video+Audio` heißen.

`cut_mp4_folder` ist optional und kann leer bleiben. Wenn bereits eine fertig geschnittene MP4-Datei vorhanden ist, zeigt der Wizard einen vorgeschlagenen Ordner an. Vorrang hat der zuletzt gemerkte Schnitt-/Exportordner, danach `vmix_storage`, danach `recordings_base`. Dateien mit `_geschnitten`, `geschnitten` oder fertigem Aufnahme-Dateinamen werden bevorzugt. Wenn keine eindeutig geschnittene Datei gefunden wird, muss bewusst die richtige MP4-Datei ausgewählt werden.

Im Startmenü können normale Nutzer Einstellungen ändern, ohne `config.toml` von Hand zu bearbeiten:

- Ziel-Basisordner
- Rohaufnahme-Ordner / vMixStorage
- LosslessCut-Pfad
- Jahresordner-Format
- Rohaufnahme nach Erfolg: verschieben, liegen lassen oder kopieren
- Dienstarten verwalten

Unter „Dienstarten verwalten“ koennen zusaetzliche Dienstarten hinzugefuegt werden. Standard-Dienstarten duerfen dabei nicht verschwinden oder kaputt geaendert werden. Gespeichert wird unter `%APPDATA%\PredigtUploader\config.toml`.

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

2. Im Hauptmenü „Neue Aufnahme vorbereiten“ wählen. Enter nimmt die erste Option.
3. Ziel-Basisordner bestätigen oder für den Testlauf ändern.
4. Variante A: Bei der Frage nach einer fertig geschnittenen MP4 mit `ja` antworten. Erwartet wird kein leerer Pfadprompt, sondern ein sichtbarer vorgeschlagener Ordner. Im Menü müssen verfügbar sein: „In diesem Ordner suchen/auswählen“, „Neueste geschnittene MP4 verwenden“, „In den neuesten MP4-Dateien auswählen“, „Anderen Ordner oder Datei eingeben“ und „Zurück“. „Zurück“ soll wieder zur Ja/Nein-Frage führen.
5. Für Variante A im vorgeschlagenen Ordner eine Datei mit `_geschnitten` oder `geschnitten` im Namen ablegen und prüfen, dass sie bevorzugt vorgeschlagen wird. Danach einen anderen Ordner eingeben und die Frage „Diesen Ordner künftig für geschnittene MP4-Dateien merken?“ mit Ja beantworten. Die Einstellung muss unter `%APPDATA%\PredigtUploader\config.toml` als `cut_mp4_folder` landen. Danach auch einmal eine direkte MP4-Datei eingeben; sie muss validiert und akzeptiert werden.
6. Variante B: Bei der Frage nach einer fertig geschnittenen MP4 mit `nein` antworten.
7. Vorgeschlagene neueste Rohaufnahme aus `vmix_storage` verwenden, aus den neuesten Aufnahmen auswählen, suchen/filtern oder einen MP4-Pfad manuell eingeben. Wenn nur ein Ordner eingegeben wird, zeigt der Wizard dieselbe begrenzte Auswahl- und Suchlogik wie bei konfigurierten Ordnern.
   Wenn `vmix_storage` nicht erreichbar ist und ein Ordner manuell eingegeben wird, soll danach trotzdem das normale Rohaufnahme-Menü erscheinen. Dort müssen „Neueste Aufnahme verwenden“, „In den neuesten Aufnahmen auswählen“, „Suchen/filtern“, „Datei/Ordner manuell eingeben“ und „Abbrechen“ verfügbar sein.
8. Der Wizard öffnet LosslessCut mit der Rohaufnahme. Ausgaben von LosslessCut sollen nicht in das Wizard-Terminal schreiben.
9. In LosslessCut nur den gewünschten Aufnahmebereich markieren.
10. Nur diesen Abschnitt als MP4 exportieren.
11. Chorlieder, Beiträge oder Ansagen nicht versehentlich als Aufnahmedatei verwenden, wenn sie nicht dazugehören.
12. Nach dem Export LosslessCut schließen oder zum Wizard zurückkehren und Enter drücken. Wenn der Wizard den gestarteten LosslessCut-Prozess beobachten kann, läuft er nach dem Schließen automatisch weiter.
13. Wenn mehrere neue MP4-Dateien gefunden werden, bewusst die richtige MP4-Datei auswählen. Der Wizard vergleicht dafür einen MP4-Snapshot vor dem Export mit dem Zustand danach und priorisiert zusätzlich plausible LosslessCut-Dateinamen mit Bezug zur Rohaufnahme, zum Beispiel `_geschnitten_<Rohdateiname>...mp4`.
14. Wenn keine Datei gefunden wird, den exportierten MP4-Pfad manuell eingeben. Wenn ein Ordner wie `V:\vMixStorage` eingegeben wird, soll der Wizard zuerst neue Dateien seit Start des Assistenten zeigen. Sonst werden neueste/geschnittene Dateien bevorzugt angezeigt; Dateien mit `_geschnitten` oder typischem LosslessCut-Zeitbereich im Namen sollen oben stehen.
15. Danach läuft der bekannte lokale Workflow weiter: Datum, Metadaten, Zielordner, MP4 übernehmen, MP3 erzeugen, Zusammenfassung, Log. Bei längeren Dateiaktionen zeigt der Wizard eine kurze Bitte-warten-Meldung.
16. Nach erfolgreichem Lauf fragt der Wizard optional, ob die Rohaufnahme im Zielordner archiviert werden soll. Bei normal wirkenden Rohaufnahmen ist „Ja, Rohaufnahme in Zielordner verschieben“ vorausgewählt. Verschieben warnt vorher deutlich und erfordert eine zweite Bestätigung, weil die Datei aus `vmix_storage` entfernt wird. Wenn die bekannte Rohaufnahme bereits geschnitten wirkt, warnt der Wizard zusätzlich; dann bleibt „liegen lassen“ die sichere Vorauswahl.
17. Am Ende soll sich der Zielordner im Explorer öffnen. Wenn das nicht klappt, bleibt der Workflow trotzdem erfolgreich und es erscheint nur ein verständlicher Hinweis.

Bei der Datumsauswahl bietet der Wizard nach Möglichkeit das Aufnahmedatum aus typischen vMix-Dateinamen an, zum Beispiel aus `Gottesdienst - 10 Mai 2026 - 09-55-08.mp4`. Falls kein Datum im Dateinamen erkannt wird, kann das Dateidatum der MP4 angeboten werden. Alternativ können immer das heutige Datum oder ein anderes Datum per Hand gewählt werden.

Direkt nach der Datumsauswahl fragt der Wizard:

```text
Welche Art von Aufnahme ist das?
```

Erwartete Standardauswahl:

- Sonntag: Predigt
- Mittwoch: Bibelstunde
- Freitag: Gebetsstunde
- sonst: Predigt

Vor den Eingaben zu Titel, Bibelstelle und Redner muss ein Hinweis erscheinen, wo diese Angaben zu finden sind: Broadcast/Ablaufplan, Beamertechnik bzw. Präsentation, ChurchTools oder Prediger.

Nach der Dienstartauswahl und nach jeder fachlichen Eingabe muss eine kurze Dateiname-Vorschau erscheinen, zum Beispiel:

```text
Aktueller Dateiname: Predigt (Lehre statt Leere_[Bibelstelle])_[Redner].mp4
```

### Predigt-Test

Auswahl „Predigt“:

- Titel eingeben
- Hauptbibelstelle eingeben
- Redner eingeben

Erwarteter Dateiname:

```text
Predigt (Titel_Hauptbibelstelle)_Redner.mp4
```

### Bibelstunde-Test

Auswahl „Bibelstunde“:

- kein Titel als Pflichtfeld
- Hauptbibelstelle eingeben
- Redner eingeben

Erwarteter Dateiname:

```text
Bibelstunde (Hauptbibelstelle)_Redner.mp4
```

### Vortrag/Lobpreis/Sonstiges-Test

Vortrag:

```text
Vortrag (Titel)_Redner.mp4
```

Lobpreis ohne Leitung:

```text
Lobpreis (Titel).mp4
```

Lobpreis mit Leitung:

```text
Lobpreis (Titel)_Leitung.mp4
```

Sonstiges:

```text
Sonstiges (Titel).mp4
Sonstiges (Titel)_Name.mp4
```

Die MP3-Datei muss jeweils denselben Namen wie die MP4 bekommen, nur mit `.mp3`.

### Strg+C-Test

`Strg+C` bricht den Vorgang ab und ist nicht die Zurueck-Funktion. Beim Doppelklick-Start ueber `.cmd` kann Windows danach „Batchvorgang abbrechen (J/N)?“ anzeigen. Zum Zurueckgehen im Wizard immer „Zurück“ verwenden.

### Experimentelle Textual-Oberfläche

Der normale Wizard bleibt Standard. Für Entwicklungstests kann optional installiert werden:

```powershell
pip install -e .[tui]
python -m predigt_uploader tui
```

Erwartet wird ein erster Prototyp mit Startmenü, Metadaten-Vorschau, MP4-/MP3-Dateiname, Zielordner-Vorschau und einer reinen Einstellungen-Ansicht. Er muss den produktiven Wizard nicht vollständig ersetzen.

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
- Wenn mehrere MP4-Dateien gefunden werden: nur die Datei auswählen, die wirklich die gewünschte Aufnahme enthält.
- Bei technischen Details den Admin-Hinweis und die Logdatei prüfen.
