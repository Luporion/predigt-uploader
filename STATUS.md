# Projektstatus

## Projektziel

PredigtUploader soll den lokalen Predigt-Workflow einer Gemeinde unter Windows vereinfachen. Das Tool richtet sich an überwiegend nicht-technische Nutzer und soll verständlich, zuverlässig und fehlertolerant sein.

## Aktueller Entwicklungsstand

Das Projekt ist ein lokaler CLI-Prototyp in Phase 1. Die Grundstruktur, Fachregeln für Dateinamen und Ordner sowie automatische Tests sind vorhanden. Der Terminal-Wizard wurde nutzerfreundlicher gemacht, prüft Eingaben robuster, behandelt Config-Fehler verständlich, sichert die lokale MP4-Übernahme besser ab, prüft die MP3-Erzeugung genauer, schreibt eine einfache Logdatei und meldet den lokalen Workflow-Endzustand klar. Die abschließende Gegenprüfung sieht keine blockierenden offenen Punkte für Phase 1 mehr.
Für die erste lokale Testversion gibt es eine manuelle Testanleitung und ein PowerShell-Startskript für den Wizard.

## Was Version 1 bereits kann

- Konfiguration mit Standardwerten und optionaler `config.toml` laden.
- Angegebene Config-Dateien kontrolliert prüfen und verständliche Fehler bei fehlender, unlesbarer oder ungültiger Config anzeigen.
- Predigtdaten im Terminal abfragen.
- Leere Pflichtangaben erneut abfragen.
- Pfad zu einer MP4-Datei prüfen.
- Ziel-Dateinamen nach dem Predigtstandard erzeugen.
- Jahres- und Datumsordner ermitteln.
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

## Bewusst noch nicht enthalten

- Vimeo-Upload.
- WordPress-Automatisierung.
- Login-, Token- oder API-Key-Verwaltung.
- Automatische Predigt-Erkennung per KI.
- Komfortable Windows-GUI oder Datei-Auswahldialog.
- LosslessCut-Automatisierung.

## Nächster geplanter Schritt

Phase 1 lokal mit einer kleinen MP4 nach `docs/manual-test-v1.md` testen. Danach den Übergang zu Phase 2 planen.

## Sicherheits-Hinweis

Keine Zugangsdaten, API-Keys, Tokens, Passwörter oder privaten Pfade ins Repository einbauen oder committen. Beispieldateien dürfen nur Platzhalter enthalten.
