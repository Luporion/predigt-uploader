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
losslesscut_path = ""
```

`vmix_storage` ist der Ordner mit Rohaufnahmen. Der Wizard schlägt daraus die neueste MP4 vor.
Wenn dort viele alte Dateien liegen, zeigt der Wizard nicht sofort alle MP4-Dateien an. Erwartet wird:

- neueste Aufnahme verwenden
- in den neuesten Aufnahmen auswählen
- suchen/filtern
- Datei/Ordner manuell eingeben
- abbrechen

Bei der Liste der neuesten Aufnahmen werden nur die neuesten Dateien angezeigt. Bei der Suche werden nur passende Dateinamen angezeigt. Bei sehr vielen Treffern erscheint ein Hinweis.

`losslesscut_path = ""` bedeutet: LosslessCut wird über PATH oder Windows-App-Alias gestartet. Wenn das nicht klappt, kann ein vollständiger Pfad eingetragen werden.

Wenn LosslessCut als portable ZIP-Version genutzt wird:

1. ZIP-Datei in einen festen Ordner entpacken, z. B. `D:\Programme\LosslessCut`.
2. In diesem Ordner `LosslessCut.exe` suchen.
3. Optional den Pfad dauerhaft in `config.toml` eintragen:

```toml
[paths]
losslesscut_path = "D:\\Programme\\LosslessCut\\LosslessCut.exe"
```

Wenn `losslesscut_path` leer bleibt und der automatische Start fehlschlägt, fragt der Wizard den Pfad zur `LosslessCut.exe` direkt ab. Diese Eingabe gilt nur für den aktuellen Lauf.

Bei der direkten Eingabe im Wizard sind Anführungszeichen erlaubt, zum Beispiel:

```text
"D:\Programme\LosslessCut\LosslessCut.exe"
```

Wenn versehentlich nur der Ordner eingegeben wird, in dem `LosslessCut.exe` liegt, zeigt der Wizard passende `.exe`-Dateien aus diesem Ordner zur Auswahl an.

Keine Zugangsdaten, Tokens oder privaten Passwörter in die Config schreiben.

## Testablauf

1. Wizard starten:

```powershell
.\scripts\run-wizard.ps1
```

2. Ziel-Basisordner bestätigen oder für den Testlauf ändern.
3. Bei der Frage nach einer fertig geschnittenen MP4 mit `nein` antworten.
4. Vorgeschlagene neueste Rohaufnahme aus `vmix_storage` verwenden, aus den neuesten Aufnahmen auswählen, suchen/filtern oder einen MP4-Pfad manuell eingeben. Wenn nur ein Ordner eingegeben wird, zeigt der Wizard nur eine begrenzte Auswahl der neuesten `.mp4`-Dateien aus diesem Ordner.
5. Der Wizard öffnet LosslessCut mit der Rohaufnahme.
6. In LosslessCut nur den Predigtbereich markieren.
7. Nur die Predigt als MP4 exportieren.
8. Chorlieder, Beiträge oder Ansagen nicht als Predigtdatei verwenden.
9. Nach dem Export zum Wizard zurückkehren und Enter drücken.
10. Wenn mehrere neue MP4-Dateien gefunden werden, bewusst die richtige Predigtdatei auswählen.
11. Wenn keine Datei gefunden wird, den exportierten MP4-Pfad manuell eingeben. Wenn ein Ordner wie `V:\vMixStorage` eingegeben wird, soll der Wizard zuerst neue Dateien seit Start des Assistenten zeigen. Sonst werden neueste/geschnittene Dateien bevorzugt angezeigt; Dateien mit `_geschnitten` im Namen sollen oben stehen.
12. Danach läuft der bekannte lokale Workflow weiter: Datum, Metadaten, Zielordner, MP4 übernehmen, MP3 erzeugen, Zusammenfassung, Log.
13. Nach erfolgreichem Lauf fragt der Wizard optional, ob die Rohaufnahme im Zielordner archiviert werden soll. Standard ist Nein. Verschieben warnt vorher deutlich, weil die Datei aus `vmix_storage` entfernt wird.
14. Am Ende soll sich der Zielordner im Explorer öffnen. Wenn das nicht klappt, bleibt der Workflow trotzdem erfolgreich und es erscheint nur ein verständlicher Hinweis.

Bei der Datumsauswahl bietet der Wizard nach Möglichkeit das Aufnahmedatum aus typischen vMix-Dateinamen an, zum Beispiel aus `Gottesdienst - 10 Mai 2026 - 09-55-08.mp4`. Falls kein Datum im Dateinamen erkannt wird, kann das Dateidatum der MP4 angeboten werden. Alternativ können immer das heutige Datum oder ein anderes Datum per Hand gewählt werden.

Wenn die finale MP4-Datei im Zielordner bereits existiert, überschreibt der Wizard sie nicht automatisch. Es gibt eine bewusste Auswahl:

- vorhandene Datei behalten und ohne Kopieren/Verschieben weiterarbeiten
- neuen Dateinamen verwenden
- abbrechen
- überschreiben

Überschreiben ersetzt die vorhandene Datei und muss deshalb zusätzlich bestätigt werden.

Bei Ja/Nein-Fragen und mehreren gefundenen MP4-Dateien nutzt der Wizard nach Möglichkeit eine stabile Pfeiltasten-Auswahl über `questionary`. Falls das Terminal dies nicht unterstützt, funktioniert weiterhin die Texteingabe mit `ja`/`nein` oder nummerierter Auswahl.

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
- Wenn mehrere MP4-Dateien gefunden werden: nur die Datei auswählen, die wirklich die Predigt enthält.
- Bei technischen Details den Admin-Hinweis und die Logdatei prüfen.
