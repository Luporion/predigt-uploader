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
- [x] Nutzerhinweise fuer manuellen Aufnahmeschnitt anzeigen
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
- [x] Ziel-Basisordner, Rohaufnahme-Ordner und LosslessCut-Pfad optional in Benutzer-Config unter APPDATA merken
- [x] Jahresordner per year_folder_template konfigurierbar machen
- [x] Bitte-warten-Hinweise fuer laengere Dateiaktionen anzeigen
- [x] LosslessCut-Export-Kandidaten auch anhand des Rohdateinamens bevorzugen
- [x] manuellen LosslessCut-Pfad vor dem Start optional merken
- [x] LosslessCut-Ausgaben vom Wizard-Terminal trennen
- [x] nach LosslessCut-Export per Enter oder Prozessende weiterlaufen
- [x] Rohaufnahme-Archivierung fuer normale Rohaufnahmen standardmaessig auf Verschieben setzen
- [x] einfaches Hauptmenue fuer normale Nutzer ergaenzen
- [x] Einstellungen im Menue in APPDATA-config.toml speichern
- [x] Jahresordner-Format im Menue zwischen Jahr und Jahr Video+Audio waehlen
- [x] nutzerfreundlichere Startueberschrift anzeigen
- [x] Auswahl bereits geschnittener MP4-Dateien mit vorgeschlagenem Ordner, Suche und AppData-Merker verbessern
- [x] Metadaten-Hilfetexte, Suchfeld-Zurueck und Strg+C-Abbruchhinweis ergaenzen
- [x] Dienstarten mit passenden Pflichtfeldern und Dateinamen einfuehren
- [x] zusaetzliche Dienstarten im Einstellungsmenue in APPDATA-config.toml speichern
- [x] Freitag als Gebetsstunde vorauswaehlen
- [x] zentrale Dateiname-Vorschau mit Platzhaltern ergaenzen
- [x] optionale experimentelle Textual-Oberflaeche vorbereiten
- [x] allgemeine Texte nach Dienstart-Einfuehrung auf Aufnahme/Veranstaltung bereinigen
- [x] Textual-Prototyp mit MP4-/MP3-Vorschau, Zielordner und Einstellungen-Anzeige erweitern
- [x] Textual-Prototyp lesbarer beschriften und Start-/Hinweisbereiche verbessern
- [x] Textual-Prototyp um reine MP4-Dateiuebersicht fuer Schnitt- und Rohaufnahmeordner erweitern
- [x] Textual-Metadaten-Erfassung mit Dienstart-Defaults, Pflichtfeldpruefung und Ordner-Besonderheit ausbauen
- [x] Textual-Startablauf mit Quelle-Auswahl, MP4-Filterliste und Preview-Uebergabeobjekt vorbereiten
- [x] Textual-Dateiauswahl als wiederverwendbare MP4-Tabelle fuer geschnittene Dateien und Rohaufnahmen verbessern
- [x] Textual-Metadatenvalidierung direkt an den Eingabefeldern sichtbar machen
- [x] Doppelte Textausgabe unter der Textual-MP4-Tabelle entfernen
- [x] Start-Hinweis fuer beendete vMix-Aufnahme und beendeten Stream ergaenzen
- [x] Textual-Start-Hinweis als prominente Sicherheitsseite mit Nein-Standardfokus darstellen
- [x] Textual-Startcheck-Fragen als grosse getrennte Warnbloecke hervorheben
- [x] Textual-Startcheck als kompakten ASCII-/Checklisten-Banner nachschaerfen
- [x] Textual-Startcheck wieder auf breite ruhige Warnseite ohne ASCII-Checkliste zurueckstellen
- [x] Bibelstunde mit optionaler Themenreihe im gemeinsamen Dateinamen unterstuetzen
- [x] danach bestehenden lokalen Workflow weiterverwenden
- [x] Textual-Rohaufnahme-Workflow mit LosslessCut-Export-Erkennung und bewusster Rohaufnahme-Aktionsauswahl absichern
- [x] Textual-Dienstart-Vorauswahl am wirksamen Aufnahmedatum aus Rohaufnahme oder Schnittdatei ausrichten
- [x] Textual-Zielordnerpruefung und Zieldatei-Konfliktschutz vor finaler Verarbeitung ergaenzen
- [x] Textual-Konfliktentscheidung fuer vorhandene Zieldateien prominent und bedienbar anzeigen
- [x] Textual-Vorbereitung-pruefen-Seite fuer naechste Nutzeraktion verstaendlicher machen
- [x] Textual-Ersetzen-Button und Erfolgsstatus bei vorhandenen Zieldateien nachschaerfen
- [x] Textual-Doppelklick-Starter und klare Abschlussseite mit manuellen naechsten Schritten ergaenzen
- [x] Setup und Systemcheck um Textual-Installation und Textual-Pruefung erweitern

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
