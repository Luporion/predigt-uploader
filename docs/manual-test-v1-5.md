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

Keine Zugangsdaten, Tokens oder privaten Passwörter in die Config schreiben.

## Testablauf

1. Wizard starten:

```powershell
.\scripts\run-wizard.ps1
```

2. Ziel-Basisordner bestätigen oder für den Testlauf ändern.
3. Bei der Frage nach einer fertig geschnittenen MP4 mit `nein` antworten.
4. Vorgeschlagene Rohaufnahme aus `vmix_storage` bestätigen oder einen MP4-Pfad manuell eingeben.
5. Der Wizard öffnet LosslessCut mit der Rohaufnahme.
6. In LosslessCut nur den Predigtbereich markieren.
7. Nur die Predigt als MP4 exportieren.
8. Chorlieder, Beiträge oder Ansagen nicht als Predigtdatei verwenden.
9. Nach dem Export zum Wizard zurückkehren und Enter drücken.
10. Wenn mehrere neue MP4-Dateien gefunden werden, bewusst die richtige Predigtdatei auswählen.
11. Wenn keine Datei gefunden wird, den exportierten MP4-Pfad manuell eingeben.
12. Danach läuft der bekannte lokale Workflow weiter: Metadaten, Zielordner, MP4 übernehmen, MP3 erzeugen, Zusammenfassung, Log.

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

Im Projektordner liegt zusätzlich eine Logdatei unter `logs/`.

## Fehlerhilfe

- Wenn LosslessCut nicht startet: Pfad zur `LosslessCut.exe` im Wizard eingeben, `losslesscut_path` in `config.toml` prüfen oder LosslessCut manuell öffnen.
- Wenn keine neue MP4 gefunden wird: exportierten Pfad manuell eingeben.
- Wenn mehrere MP4-Dateien gefunden werden: nur die Datei auswählen, die wirklich die Predigt enthält.
- Bei technischen Details den Admin-Hinweis und die Logdatei prüfen.
