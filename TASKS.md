# Entwicklungsaufgaben

## Phase 0: Repo-Start

- [x] Projektstruktur erstellen
- [x] Spezifikation dokumentieren
- [x] Codex-Anweisungen dokumentieren
- [x] minimale Python-Struktur anlegen
- [x] erste Tests für Dateiname/Ordnerlogik

## Phase 1: Lokaler CLI-Prototyp

- [x] Config-Laden finalisieren
- [x] Wizard im Terminal nutzerfreundlicher machen
- [x] Datei-Auswahl per Pfad robust validieren
- [x] Ordnerlogik interaktiv fertigstellen
- [x] MP4 kopieren/verschieben mit Sicherheitsabfrage
- [x] FFmpeg-Prüfung einbauen
- [x] MP3-Erzeugung implementieren und testen
- [x] Zusammenfassung als Textdatei im Zielordner speichern

- [x] Logdatei schreiben

## Phase 1.5: Lokaler LosslessCut-Schnitt-Assistent

- [x] vMix-/Quellordner per Config nutzen
- [x] LosslessCut-Pfad per Config oder PATH/App-Alias nutzen
- [x] neueste Rohaufnahme aus Quellordner vorschlagen
- [x] Rohaufnahme alternativ per Pfad abfragen
- [x] LosslessCut mit Rohaufnahme starten
- [x] bei fehlendem LosslessCut-Pfad manuelle EXE-Eingabe erlauben
- [x] Nutzerhinweise fuer manuellen Predigtschnitt anzeigen
- [x] neue exportierte MP4-Dateien seit Startzeit suchen
- [x] bei mehreren Exporten bewusste Auswahl erzwingen
- [x] Terminal-Auswahl mit questionary und Text-Fallback einfuehren
- [x] Textmodus per PREDIGT_UPLOADER_TEXT_UI=1 erzwingen
- [x] Dateipfad-Abfragen koennen passende Dateien aus einem angegebenen Ordner anbieten
- [x] Datumsauswahl mit Aufnahmedatum, heutigem Datum und manueller Eingabe anbieten
- [x] vorhandene Ziel-MP4 per Auswahl behandeln und Ueberschreiben doppelt bestaetigen
- [x] lokale Setup- und Systemcheck-Skripte fuer Zielrechner bereitstellen
- [x] Installationsanleitung fuer lokale Version 1.5 dokumentieren
- [x] anklickbare Windows-Startdateien fuer Einrichtung, Systemcheck und Wizard bereitstellen
- [x] Encoding der Windows-Startdateien und PowerShell-Ausgaben absichern
- [x] einfache Release-ZIP fuer lokale Auslieferung vorbereiten
- [x] FFmpeg-Pruefung im Setup mit winget-Angebot verbessern
- [x] Rohaufnahme-Auswahl fuer grosse vMixStorage-Ordner begrenzen und Suche ergaenzen
- [x] manuelle Exportauswahl fuer grosse Ordner begrenzen und geschnittene Dateien bevorzugen
- [x] Zielordner nach erfolgreichem Workflow optional automatisch oeffnen
- [x] Rohaufnahme nach erfolgreichem Workflow optional kopieren oder verschieben
- [x] Zurueck-Logik in Datei-Unterauswahlen reparieren
- [x] geschnitten wirkende Dateien bei Rohaufnahme-Vorschlaegen niedriger priorisieren und warnen
- [x] Live-Suche fuer Dateiauswahl mit robustem Text-Fallback ergaenzen
- [x] LosslessCut-Export-Erkennung per MP4-Snapshot robuster machen
- [x] Rohaufnahme-Archivierung gegen geschnitten wirkende Dateien absichern
- [x] Release-ZIP-Paketversion fuer nachgebesserte lokale Auslieferung aktualisieren
- [x] manuell eingegebenen Rohaufnahme-Ordner als temporaeren Quellordner mit normalem Menue nutzen
- [x] UNC-Pfade fuer Rohaufnahme-Ordner dokumentieren
- [x] bei fehlendem Export manuellen Pfad erlauben
- [x] danach bestehenden lokalen Workflow weiterverwenden

## Phase 2: Windows-Nutzerfreundlichkeit

- [ ] Logdateien in geeignetem Ordner speichern
- [ ] Fehlerbericht-ZIP erstellen
- [ ] einfache tkinter-GUI prüfen
- [ ] Drag-and-drop oder Datei-Auswahl-Dialog ergänzen
- [ ] PyInstaller-Build prüfen

## Phase 3: LosslessCut-Unterstützung

- [ ] LosslessCut-Pfad konfigurieren
- [ ] Aufnahme in LosslessCut öffnen
- [ ] Exportordner überwachen
- [ ] mehrere exportierte Clips erkennen
- [ ] Clipauswahl mit Dauer anzeigen

## Phase 4: Vimeo

- [ ] Vimeo API-Zugang dokumentieren
- [ ] API-Token sicher speichern
- [ ] Ordner „Predigten“ per API finden
- [ ] MP4 hochladen
- [ ] oEmbed-Code abrufen
- [ ] Embed-Code anzeigen/kopieren

## Phase 5: WordPress optional

- [ ] WordPress-Felder analysieren
- [ ] REST-API-Authentifizierung testen
- [ ] Predigt als Entwurf erstellen
- [ ] MP3 hochladen
