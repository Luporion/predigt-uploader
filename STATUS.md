# Projektstatus

## Projektziel

PredigtUploader soll den lokalen Predigt-Workflow einer Gemeinde unter Windows vereinfachen. Das Tool richtet sich an überwiegend nicht-technische Nutzer und soll verständlich, zuverlässig und fehlertolerant sein.

## Aktueller Entwicklungsstand

Das Projekt ist ein lokaler CLI-Prototyp in Phase 1. Die Grundstruktur, Fachregeln für Dateinamen und Ordner sowie erste automatische Tests sind vorhanden. Der Terminal-Wizard wurde nutzerfreundlicher gemacht und prüft Eingaben robuster.

## Was Version 1 bereits kann

- Konfiguration mit Standardwerten und optionaler `config.toml` laden.
- Predigtdaten im Terminal abfragen.
- Leere Pflichtangaben erneut abfragen.
- Pfad zu einer MP4-Datei prüfen.
- Ziel-Dateinamen nach dem Predigtstandard erzeugen.
- Jahres- und Datumsordner ermitteln.
- Vorhandene Zielordner anzeigen und bewusst bestätigen lassen.
- Neue Ordnernamen mit optionaler Besonderheit verständlich anzeigen.
- MP4 kopieren oder verschieben.
- MP3-Erzeugung über externes FFmpeg anstoßen.
- Zusammenfassungsdateien im Zielordner schreiben.

## Bewusst noch nicht enthalten

- Vimeo-Upload.
- WordPress-Automatisierung.
- Login-, Token- oder API-Key-Verwaltung.
- Automatische Predigt-Erkennung per KI.
- Komfortable Windows-GUI oder Datei-Auswahldialog.
- LosslessCut-Automatisierung.

## Nächster geplanter Schritt

MP4 kopieren/verschieben mit einer ausdrücklichen Sicherheitsabfrage und noch besseren Fehlermeldungen absichern.

## Sicherheits-Hinweis

Keine Zugangsdaten, API-Keys, Tokens, Passwörter oder privaten Pfade ins Repository einbauen oder committen. Beispieldateien dürfen nur Platzhalter enthalten.
