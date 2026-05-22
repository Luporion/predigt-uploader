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
Eine zweite Nachbesserung behebt Bedien- und Erkennungsprobleme aus dem Praxistest: `Zurück` aus Unterauswahlen führt direkt ins vorherige Menü, Rohaufnahme-Vorschläge vermeiden geschnitten wirkende Dateien, die Suche nutzt nach Möglichkeit Live-Filter per `questionary`, die Export-Erkennung vergleicht einen MP4-Snapshot vor/nach LosslessCut und die Rohaufnahme-Archivierung warnt bei geschnitten wirkenden Dateien.
Eine weitere Zielrechner-Korrektur behandelt fehlende `vmix_storage`-Ordner besser: Wenn Nutzer manuell einen Ordner eingeben, wird er für diesen Wizard-Lauf als temporärer Rohaufnahme-Quellordner verwendet und das normale Rohaufnahme-Menü inklusive Suche/Filter angezeigt. UNC-Pfade werden als normale Pfade akzeptiert und in der Config-Doku als robuster empfohlen.
Die aktuelle Stabilisierung ergänzt eine eindeutigere Zurück-Logik ohne doppelte Fallback-Listen, besser lesbare `questionary`-Auswahlen, AppData-Benutzer-Config für gemerkte Ordner und LosslessCut-Pfad, ein konfigurierbares Jahresordner-Template sowie kurze Bitte-warten-Hinweise bei längeren Dateiaktionen. LosslessCut-Exporte werden zusätzlich anhand plausibler Dateinamen mit Bezug zur Rohaufnahme bevorzugt vorgeschlagen, aber weiterhin nicht blind übernommen.
Die LosslessCut-Bedienung wurde weiter beruhigt: Ein manuell gewählter LosslessCut-Pfad wird vor dem Programmstart optional gemerkt, LosslessCut-Ausgaben werden vom Wizard-Terminal getrennt und der Wizard kann nach dem Export entweder durch Enter oder durch Schließen des gestarteten LosslessCut-Prozesses weiterlaufen. Bei der Rohaufnahme-Archivierung ist Verschieben für normale Rohaufnahmen die Vorauswahl; bei geschnitten wirkenden Dateien bleibt Liegenlassen die sichere Vorauswahl.
Für normale Gemeindemitarbeiter gibt es jetzt ein einfaches Terminal-Hauptmenü. Darüber kann eine neue Aufnahme vorbereitet, Einstellungen geändert, ein Systemcheck-Hinweis angezeigt oder die letzte Logdatei geöffnet werden. Die Überschrift wurde auf „PredigtUploader“ mit kurzer Nutzerbeschreibung vereinfacht.
Der Workflow fuer bereits fertig geschnittene MP4-Dateien wurde komfortabler: Statt eines leeren Pfadprompts zeigt der Wizard nun einen vorgeschlagenen Schnitt-/Exportordner an. Vorrang haben ein gemerkter `cut_mp4_folder`, danach `vmix_storage` und danach `recordings_base`. In vorhandenen Ordnern koennen Nutzer suchen, die neueste geschnittene MP4 verwenden, aus den neuesten MP4-Dateien auswaehlen, einen anderen Ordner oder eine Datei eingeben oder zur vorherigen Frage zurueckgehen. Geschnitten wirkende Dateien werden bevorzugt, und ein abweichender Schnittordner kann unter `%APPDATA%\PredigtUploader\config.toml` gemerkt werden.
Die aktuelle Nachbesserung erweitert die fachliche Metadatenlogik: Nach dem Datum wird eine Dienstart wie Predigt, Bibelstunde, Vortrag, Lobpreis oder Sonstiges abgefragt. Je nach Dienstart werden nur die passenden Pflichtfelder abgefragt und die Dateinamen entsprechend gebildet. Metadaten-Hilfetexte nennen laienverstaendlich typische Quellen fuer Titel, Bibelstelle und Redner. Suchfelder zeigen eine sichtbare Zurueck-Hilfe und akzeptieren im Textmodus `zurück`, `z` und `back`. Der Starttext weist darauf hin, dass `Strg+C` abbricht und nicht als Zurueck-Funktion gedacht ist. Zusaetzliche Dienstarten koennen im Einstellungsmenue angelegt und unter `%APPDATA%\PredigtUploader\config.toml` gespeichert werden.
Die Dienstart-Vorauswahl beruecksichtigt nun auch Freitag als Gebetsstunde. Fuer die Metadaten-Eingabe gibt es eine zentrale Dateiname-Vorschau mit sichtbaren Platzhaltern wie `[Titel]`, `[Bibelstelle]`, `[Redner]` und `[Leitung]`; der Terminal-Wizard zeigt diese Vorschau nach der Dienstartauswahl und nach fachlichen Eingaben kompakt an. Allgemeine Nutzertexte sprechen jetzt dort von Aufnahme oder Veranstaltung, wo nicht konkret die Dienstart Predigt gemeint ist. Zusaetzlich ist Textual als optionale Abhaengigkeit vorbereitet: `python -m predigt_uploader tui` startet einen experimentellen Prototyp mit Startmenue samt Statusbereich, besser beschrifteter Metadaten-/Dateiname-Vorschau, Zielordner-Vorschau, reiner MP4-Dateiuebersicht und reiner Einstellungen-Ansicht, wenn `.[tui]` installiert ist. Der normale Terminal-Wizard bleibt der Standard.

## Was Version 1 bereits kann

- Konfiguration mit Standardwerten und optionaler `config.toml` laden.
- Angegebene Config-Dateien kontrolliert prüfen und verständliche Fehler bei fehlender, unlesbarer oder ungültiger Config anzeigen.
- Aufnahmedaten und Dienstart im Terminal abfragen.
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
- Optional eine Rohaufnahme aus `vmix_storage` vorschlagen, in LosslessCut öffnen und nach dem manuellen Export die neue MP4 übernehmen.
- Große Rohaufnahme-Ordner über neueste Aufnahme, begrenzte neueste Liste, Suche/Filter oder manuelle Eingabe bedienen.
- Bei Rohaufnahme-Vorschlägen echte vMix-Rohaufnahmen gegenüber geschnitten wirkenden Dateien bevorzugen und verdächtige Rohaufnahmen bestätigen lassen.
- Bei fehlendem `vmix_storage` einen manuell eingegebenen Ordner als temporären Rohaufnahme-Quellordner mit vollständigem Rohaufnahme-Menü verwenden.
- Bei Datei-Suchen nach Möglichkeit Live-Filter mit Pfeiltasten-Auswahl nutzen und im Textmodus robust auf Suchtext plus Ergebnisliste zurückfallen.
- Bei Export-Erkennung neue oder veränderte MP4-Dateien über Snapshot, Erstellzeit und typische LosslessCut-Namen finden, ohne automatisch eine falsche Datei zu wählen.
- Nach erfolgreichem Lauf den Zielordner im Explorer öffnen, falls `open_target_folder = true` gesetzt ist.
- Eine bekannte Rohaufnahme nach erfolgreichem Lauf optional liegen lassen, kopieren oder nach Warnung verschieben; geschnitten wirkende Dateien werden zusätzlich gewarnt.
- Bei fehlendem LosslessCut-Start einen manuellen Pfad zur `LosslessCut.exe` abfragen und erneut versuchen.
- Ja/Nein- und Mehrfachauswahlen im Terminal über `questionary` nutzerfreundlicher anzeigen, mit Texteingabe-Fallback.
- Bei Datei-Abfragen passende Dateien aus einem eingegebenen Ordner anzeigen und auswählen lassen.
- Das Aufnahmedatum über eine Auswahl bestimmen und vMix-Dateinamen mit deutschen Monatsnamen auswerten.
- Bei vorhandener Ziel-MP4 behalten, neuen Namen wählen, abbrechen oder nach zweiter Bestätigung überschreiben.
- Abweichende Ziel-Basisordner, Rohaufnahme-Ordner und funktionierende LosslessCut-Pfade auf Wunsch unter `%APPDATA%\PredigtUploader\config.toml` merken.
- Jahresordner über `year_folder_template` benennen, zum Beispiel `2026 Video+Audio`.
- Bei längeren Dateiaktionen einfache Bitte-warten-Hinweise anzeigen.
- LosslessCut ohne störende Konsolenausgaben starten und nach dem manuellen Export Enter oder das Prozessende als Weiter-Signal nutzen.
- Normale Rohaufnahmen standardmäßig zum Verschieben in den Zielordner vorschlagen, weiterhin mit zweiter Sicherheitsbestätigung.
- Beim Doppelklick-Start ein einfaches Hauptmenü anzeigen.
- Einstellungen ohne manuelles Bearbeiten von `config.toml` in der Benutzer-Config speichern.
- Jahresordner-Format im Menü zwischen `2026` und `2026 Video+Audio` umstellen.
- Bei bereits fertig geschnittener MP4 einen vorgeschlagenen Schnitt-/Exportordner anzeigen, geschnitten wirkende Dateien bevorzugen und abweichende Ordner als `cut_mp4_folder` in der Benutzer-Config merken.
- Dienstarten wie Predigt, Bibelstunde, Vortrag, Lobpreis und Sonstiges abfragen und passende Metadatenfelder sowie Dateinamen verwenden.
- Zusätzliche Dienstarten im Einstellungsmenü anlegen und in der Benutzer-Config speichern.
- In Suchfeldern sichtbar zurück zum vorherigen Menü gehen, ohne den ganzen Wizard abzubrechen.
- `Strg+C` als Abbruch erklären.
- Freitag automatisch als Gebetsstunde vorschlagen.
- Zentrale Dateiname-Vorschau mit Platzhaltern fuer Terminal-Wizard und kuenftige Oberflaechen bereitstellen.
- Experimentellen Textual-Prototyp optional ueber `python -m predigt_uploader tui` starten, inklusive Statusbereich, beschrifteter Metadaten-Vorschau, Zielordner-Vorschau, MP4-Dateiuebersicht und Einstellungen-Anzeige.

## Bewusst noch nicht enthalten

- Vimeo-Upload.
- WordPress-Automatisierung.
- Login-, Token- oder API-Key-Verwaltung.
- Automatische Predigt-Erkennung per KI.
- Komfortable Windows-GUI oder Datei-Auswahldialog.
- Vollständige LosslessCut-Automatisierung oder eigener Video-Editor.

## Nächster geplanter Schritt

Release-ZIP `predigt-uploader-v0.1.6-local.zip` nach `docs/release-v1-5.md` neu erstellen, auf dem Gemeinderechner entpacken und den verbesserten Zielrechner-Workflow mit Dienstarten inklusive Freitag-Gebetsstunde, Dateiname-Vorschau, allgemeineren Aufnahmetexten, Metadaten-Hilfetexten, Suchfeld-Zurueck, Auswahl einer bereits geschnittenen MP4, Rohaufnahme-Auswahl, Live-Suche, Export-Snapshot-Erkennung und optionaler Rohaufnahme-Archivierung testen. Den experimentellen Textual-Prototyp nur als Zusatztest mit Startmenue, Metadaten-Vorschau, MP4-Dateiuebersicht und Einstellungen pruefen.

## Sicherheits-Hinweis

Keine Zugangsdaten, API-Keys, Tokens, Passwörter oder privaten Pfade ins Repository einbauen oder committen. Beispieldateien dürfen nur Platzhalter enthalten.
