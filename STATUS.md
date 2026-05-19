# Projektstatus

## Projektziel

PredigtUploader soll den lokalen Predigt-Workflow einer Gemeinde unter Windows vereinfachen. Das Tool richtet sich an überwiegend nicht-technische Nutzer und soll verständlich, zuverlässig und fehlertolerant sein.

## Aktueller Entwicklungsstand

Das Projekt ist ein lokaler CLI-Prototyp in Phase 1. Die Grundstruktur, Fachregeln für Dateinamen und Ordner sowie automatische Tests sind vorhanden. Der Terminal-Wizard wurde nutzerfreundlicher gemacht, prüft Eingaben robuster, behandelt Config-Fehler verständlich, sichert die lokale MP4-Übernahme besser ab, prüft die MP3-Erzeugung genauer, schreibt eine einfache Logdatei und meldet den lokalen Workflow-Endzustand klar. Die abschließende Gegenprüfung sieht keine blockierenden offenen Punkte für Phase 1 mehr.
Für die erste lokale Testversion gibt es eine manuelle Testanleitung und ein PowerShell-Startskript für den Wizard. Der Ziel-Basisordner wird ohne eigene Config aus dem aktuellen Windows-Benutzer abgeleitet und kann im Wizard für den aktuellen Lauf direkt per Pfadeingabe überschrieben werden.
Phase 1.5 ergänzt einen einfachen LosslessCut-Schnitt-Assistenten: Rohaufnahme wählen, LosslessCut extern öffnen, Predigt manuell schneiden/exportieren und die exportierte MP4 danach in den bestehenden lokalen Workflow übernehmen.
Die Terminal-Bedienung nutzt nach Möglichkeit `questionary` für Pfeiltasten-Auswahlen und fällt sonst auf robuste Texteingabe zurück. Der Textmodus kann mit `PREDIGT_UPLOADER_TEXT_UI=1` erzwungen werden. Wenn LosslessCut nicht automatisch gefunden wird, kann der Pfad zur `LosslessCut.exe` direkt im Wizard angegeben werden.
Bei Dateipfad-Abfragen kann auch ein Ordner eingegeben werden; der Wizard zeigt dann passende Dateien im Ordner zur Auswahl an.
Die Datumsauswahl ist nun geführter: Der Wizard kann ein Aufnahmedatum aus typischen vMix-Dateinamen erkennen, alternativ das Dateidatum, das heutige Datum oder eine manuelle Eingabe verwenden.
Wenn eine finale MP4 im Zielordner bereits existiert, bietet der Wizard eine bewusste Auswahl an. Überschreiben ist nicht Standard und erfordert eine zweite Bestätigung.
Für die Vorbereitung eines Zielrechners gibt es jetzt `scripts/setup-local.ps1`, `scripts/check-system.ps1` und die Installationsanleitung `docs/install-v1-5.md`.
Für Gemeindemitarbeiter gibt es zusätzlich anklickbare `.cmd`-Startdateien im Projektstamm für Einrichtung, Systemcheck und Wizard-Start.
Die Windows-Starter und PowerShell-Skripte initialisieren UTF-8 und verwenden bei kritischen Konsolentexten ASCII-sichere deutsche Schreibweisen wie `verfuegbar`.
Für die Weitergabe an den Gemeinderechner gibt es eine einfache Release-ZIP-Anleitung und `scripts/make-release-zip.ps1`.
Nach dem Gemeinderechner-Praxistest wurde der lokale Zielrechner-Workflow verbessert: `setup-local.ps1` prüft FFmpeg und bietet bei verfügbarem `winget` eine bestätigte Installation an, große vMixStorage-Ordner werden nicht mehr ungefiltert angezeigt, Rohaufnahmen können gesucht oder aus einer begrenzten neuesten Liste gewählt werden, exportierte Dateien mit `_geschnitten` werden bevorzugt angezeigt, der Zielordner kann nach Erfolg automatisch geöffnet werden und die bekannte Rohaufnahme kann optional kopiert oder nach Warnung verschoben werden.

## Was Version 1 bereits kann

- Konfiguration mit Standardwerten und optionaler `config.toml` laden.
- Angegebene Config-Dateien kontrolliert prüfen und verständliche Fehler bei fehlender, unlesbarer oder ungültiger Config anzeigen.
- Predigtdaten im Terminal abfragen.
- Leere Pflichtangaben erneut abfragen.
- Pfad zu einer MP4-Datei prüfen.
- Ziel-Dateinamen nach dem Predigtstandard erzeugen.
- Jahres- und Datumsordner ermitteln.
- Ziel-Basisordner anzeigen, prüfen, bei Bedarf erstellen und im Wizard überschreiben lassen.
- Vorhandene Zielordner anzeigen und bewusst bestätigen lassen.
- Neue Ordnernamen mit optionaler Besonderheit verständlich anzeigen.
- Vor der MP4-Übernahme Quelle, Zielordner, finalen Dateinamen und Kopier-/Verschiebe-Aktion anzeigen.
- MP4 standardmäßig kopieren und vor der Dateiaktion ausdrücklich bestätigen lassen.
- Bestehende MP4-Zieldateien erkennen, ohne sie still zu überschreiben.
- Vor der MP3-Erzeugung prüfen, ob FFmpeg verfügbar ist.
- Bei fehlendem FFmpeg erklären, dass die MP4 trotzdem vorbereitet wurde und wie man manuell eine MP3 erstellt.
- MP3-Erzeugung über externes FFmpeg anstoßen, wenn FFmpeg verfügbar ist.
- Nach der MP3-Erzeugung prüfen, ob die MP3 existiert und größer als 0 Bytes ist.
- Bei Fehlern in der MP3-Erzeugung verständlich erklären, wo die vorbereitete MP4 liegt und wie man manuell weitermacht.
- MP4 und MP3 vor der Erfolgsmeldung nochmal auf Existenz und Dateigröße prüfen.
- Den erfolgreichen lokalen Abschluss mit Zielordner, finaler MP4 und finaler MP3 anzeigen.
- Eine kurze `predigt-zusammenfassung.txt` im Zielordner schreiben.
- Keine zusätzliche `predigt-info.json` schreiben.
- Schreibfehler beim Erstellen der Zusammenfassung nutzerfreundlich melden.
- Pro Wizard-Lauf eine einfache Logdatei unter `logs/` schreiben.
- Über `scripts/run-wizard.ps1` lokal gestartet werden, wenn `.venv` eingerichtet ist.
- Über `scripts/setup-local.ps1` lokal eingerichtet und über `scripts/check-system.ps1` vor dem ersten Lauf geprüft werden.
- Über anklickbare `.cmd`-Dateien im Projektstamm ohne direkte PowerShell-Eingabe eingerichtet, geprüft und gestartet werden.
- Als einfache lokale ZIP-Auslieferung unter `dist/` vorbereitet werden.
- Optional eine Rohaufnahme aus `vmix_storage` vorschlagen, in LosslessCut öffnen und nach dem manuellen Export die neue Predigt-MP4 übernehmen.
- Große Rohaufnahme-Ordner über neueste Aufnahme, begrenzte neueste Liste, Suche/Filter oder manuelle Eingabe bedienen.
- Bei manueller Exportauswahl neue Dateien seit Assistentenstart und geschnittene Dateien bevorzugen, ohne automatisch eine falsche Datei zu wählen.
- Nach erfolgreichem Lauf den Zielordner im Explorer öffnen, falls `open_target_folder = true` gesetzt ist.
- Eine bekannte Rohaufnahme nach erfolgreichem Lauf optional liegen lassen, kopieren oder nach Warnung verschieben.
- Bei fehlendem LosslessCut-Start einen manuellen Pfad zur `LosslessCut.exe` abfragen und erneut versuchen.
- Ja/Nein- und Mehrfachauswahlen im Terminal über `questionary` nutzerfreundlicher anzeigen, mit Texteingabe-Fallback.
- Bei Datei-Abfragen passende Dateien aus einem eingegebenen Ordner anzeigen und auswählen lassen.
- Das Predigtdatum über eine Auswahl bestimmen und vMix-Dateinamen mit deutschen Monatsnamen auswerten.
- Bei vorhandener Ziel-MP4 behalten, neuen Namen wählen, abbrechen oder nach zweiter Bestätigung überschreiben.

## Bewusst noch nicht enthalten

- Vimeo-Upload.
- WordPress-Automatisierung.
- Login-, Token- oder API-Key-Verwaltung.
- Automatische Predigt-Erkennung per KI.
- Komfortable Windows-GUI oder Datei-Auswahldialog.
- Vollständige LosslessCut-Automatisierung oder eigener Video-Editor.

## Nächster geplanter Schritt

Release-ZIP nach `docs/release-v1-5.md` neu erstellen, auf dem Gemeinderechner entpacken und den verbesserten Zielrechner-Workflow mit FFmpeg-Check, Rohaufnahme-Suche, Exportauswahl, Zielordner-Öffnen und optionaler Rohaufnahme-Archivierung testen.

## Sicherheits-Hinweis

Keine Zugangsdaten, API-Keys, Tokens, Passwörter oder privaten Pfade ins Repository einbauen oder committen. Beispieldateien dürfen nur Platzhalter enthalten.
