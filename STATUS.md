# Projektstatus

## Projektziel

PredigtUploader soll den lokalen Predigt-Workflow einer Gemeinde unter Windows vereinfachen. Das Tool richtet sich an überwiegend nicht-technische Nutzer und soll verständlich, zuverlässig und fehlertolerant sein.

## Aktueller Entwicklungsstand

### Produktive lokale Datenhaltung und Bedienbarkeit (31.08.2026)

Zusammenfassung und Workflow-State sind jetzt eindeutig an die finale MP4 gebunden: `<MP4-Stem> - Zusammenfassung.txt` und `<MP4-Stem>.predigt-workflow.json`. Mehrere Aufnahmen im selben Tagesordner bleiben getrennt. Ein alter generischer `predigt-workflow.json` wird nur übernommen, wenn sein gespeicherter `paths.final_mp4` exakt zur ausgewählten MP4 passt; fremde States werden nicht beansprucht oder überschrieben.

Vimeo-Credentials werden zentral aufgelöst. `PREDIGT_UPLOADER_VIMEO_TOKEN` behält Vorrang für Entwicklung und CI; im normalen Windows-Betrieb speichert `keyring` den Token im Windows Credential Manager. Textual besitzt nun editierbare Einstellungen für Pfade, Jahresformat, LosslessCut, Rohaufnahmeverhalten und nicht geheime Vimeo-Zielwerte sowie maskiertes Token-Einrichten, Entfernen und eine lesende Verbindungsprüfung. Tokens gelangen nicht in Config, Workflow-State oder Logs.

Das Textual-Hauptmenü enthält einen ausdrücklich sekundären Direkteinstieg zu Vimeo für bereits fertige MP4-Dateien. Er validiert die Datei, verwendet einen passenden vorhandenen (auch alten) State oder legt einen minimalen aufnahmespezifischen State an und öffnet denselben Schritt-8-Screen. Weder Auswahl noch Screen-Aufruf starten einen Upload. Die gemeinsame `VimeoPublishingService`-Logik bleibt die einzige Uploadimplementierung.

Erfolgreich lokal verwendete Prediger werden normalisiert und case-insensitiv dedupliziert unter `%APPDATA%\PredigtUploader\speakers.json` gespeichert. Schritt 5 zeigt während der Eingabe freie, tastaturbedienbare Vorschläge; Einstellungen erlauben Anzeigen, Hinzufügen und Entfernen. WordPress bleibt unverändert nicht implementiert.

### Phase 2: Vimeo-Publishing im Textual-Workflow (31.08.2026)

Auf Basis des unveränderten Tags `v0.2.0-local-workflow` ist eine UI-unabhängige Vimeo-Publishing-Schicht hinzugekommen. `publishing/vimeo.py` validiert Token, Team-Owner und eine explizite Folder-ID, überträgt große MP4-Dateien streamend per resumierbarem tus-Verfahren, ordnet das Video anschließend über die von Vimeo weiterhin „projects“ genannten Folder-Mitgliedschaftsendpunkte zu und verifiziert diese Zuordnung. Der normale Wizard bleibt rein lokal.

Der Workflow-State speichert ohne Secrets Video-ID/-URI/-URL, Player-/Embed-Daten, Zielordner, Team-Owner sowie tus-Link, Offset und Größe. Eine bekannte Video-ID wird remote geprüft und wiederverwendet; `complete` blockiert Doppeluploads und `in_progress` ohne ID stoppt sicher. Vimeo wird erst nach bestätigter Übertragung, Remote-Prüfung, verifizierter Teamordner-Zuordnung und verfügbarem Embed-Code auf `complete` gesetzt. Bekannte Remote-IDs bleiben bei Folgefehlern erhalten.

Die Kommandos `vimeo-diagnose` und `vimeo-check` führen keine Uploads aus. `vimeo-upload` braucht einen Workflow-State und zusätzlich `--confirm-vimeo-upload`. `vimeo-embed` kann Embed-Daten anhand einer gespeicherten Video-ID nachladen. Der echte isolierte Smoke-Test hat Authentifizierung, Team-Owner „Immanuelgemeinde Wolfsburg“, Zielordner „Predigten“ (ID `1320477`), `/me/videos`, tus-Upload, Uploadverifikation, Folder-Zuordnung, erneutes Laden, abgeschlossene Transkodierung und Embed-Abruf praktisch bestätigt. Gemeldet wurden `privacy.view=unlisted` und `privacy.embed=public`; externe Einbettung, Player-URL und vollständiger iframe-Code waren verfügbar. WordPress bleibt nicht implementiert.

Das Admin-Kommando `vimeo-smoke-test` bleibt als isolierter Regressionstest erhalten. Ohne `--confirm-vimeo-upload` lädt es weder Konfiguration/Token noch erzeugt es einen Clip oder Netzwerkzugriff. Mit Freigabe erzeugt es per FFmpeg einen viersekündigen 320×180-Testclip und verwendet dieselbe Publishing-Schicht. Lokale Testdaten werden immer entfernt; das Remote-Testvideo bleibt standardmäßig zur Kontrolle erhalten. `--delete-after-test` löscht nur nach erfolgreichem Lauf exakt die gespeicherte Video-ID.

Der reale Kontotest hat gezeigt, dass `metadata.connections.videos.options` bei `/me` und Team-Owner nur `GET` meldet, obwohl Vimeo einen authentifizierten `POST /me/videos` verarbeitet und den absichtlich ungültigen Ansatz korrekt mit 2204/2230 ablehnt. Dieser Metadatenwert ist daher kein harter Upload-Capability-Test mehr. `vimeo-check` validiert weiterhin Identität, Team-Owner und Teamfolder vollständig per GET und erklärt, dass die eigentliche Upload-Berechtigung erst beim ausdrücklich bestätigten Upload geprüft wird. Der tus-Platzhalter wird nun gemäß offizieller Vimeo-Dokumentation über `/me/videos` erstellt; Folder-Zuordnung und -Verifikation verwenden weiterhin den konfigurierten Team-Owner.

Workflow-State-Schema 4 speichert zusätzlich `transcode_status` und `folder_status`; Schema 3 ergänzte bereits `upload_status`, `uploaded_at` und die eindeutigen `target_folder_*`-Felder. Ältere Zustände und Schema-2-Foldernamen bleiben lesbar. Schon eine vorhandene Video-URI verhindert einen zweiten Platzhalter; nach bestätigtem Remote-Upload bleiben Status, URI, ID, URL und Zeitpunkt auch dann erhalten, wenn erst die Folder-Zuordnung oder der Embed-Abruf scheitert.

Textual besitzt nun einen achten Schritt „Vimeo veröffentlichen“. Er erscheint erst nach erfolgreicher lokaler Verarbeitung, zeigt MP4, Team/Foldersoll, Titel und State, startet beim Betreten aber keinerlei Vimeo-Zugriff. Erst der blaue Uploadbutton erzeugt den Service und startet Upload/Resume in einem Textual-Thread-Worker. Der tus-Dateistream meldet innerhalb der großen Uploadblöcke fortlaufend echte Bytes; Textual zeigt daraus einen determinierten Balken, Prozent, übertragene/Gesamtgröße, Sitzungsgeschwindigkeit und geschätzte Restzeit. Verbindung, Remote-Anlage, Uploadprüfung, Folder, Verarbeitung und Embed bleiben als markierte Stufen sichtbar. Vimeos Transkodierungsstatus wird ohne erfundenen Prozentwert dargestellt. Erfolg aktiviert Vimeo öffnen, Embed-Code kopieren und Abschluss; Überspringen oder Fehler lassen die lokalen Dateien unangetastet und markieren Vimeo im Abschluss als offen. Eine bereits gespeicherte ID wird durch den bestehenden Service wiederverwendet. Der manuelle Direkteinstieg über eine fertige MP4 nutzt exakt denselben Screen und Callback; offen bleibt nur eine automatische Übersicht aller unvollständigen States.

Fehlende nicht geheime Vimeo-Zielwerte in bestehenden `config.toml`-Dateien erhalten zur Laufzeit die bestätigten Projektdefaults für Team-Owner `59930802`, Folder `1320477` und Name `Predigten`, ohne die bestehende Datei umzuschreiben oder andere Einstellungen zu verändern. Der Token kommt aus der Umgebungsvariable oder dem Windows Credential Manager.

Die vollständige automatische Suite umfasst jetzt 386 bestandene Tests. Der Windows-Systemcheck ist einschließlich Wizard, Textual, Vimeo-HTTP-Abhängigkeit, Windows-Credential-Zugriff und FFmpeg grün. CLI-Hilfe und der bestätigungslose Smoke-Test-Vorschauweg wurden ebenfalls ohne Netzwerk-Upload geprüft.

### Stabile lokale Baseline (30.08.2026)

Die Baseline trägt die Projektversion `0.2.0`; `pyproject.toml` ist die einzige numerische Versionsquelle. Der Release-Kanal heißt `local-workflow`, sodass der automatische ZIP-Name ohne passenden HEAD-Tag `predigt-uploader-v0.2.0-local-workflow.zip` lautet. Ein Git-Tag wird nicht automatisch erzeugt.

Der lokale Textual-Workflow ist durchgängig funktionsfähig: Startcheck, Quell- oder Rohaufnahmeauswahl, LosslessCut-Aufruf, Exporterkennung und -bestätigung, Metadaten, Zielordnerentscheidung, sichere Dateikonfliktbehandlung, finale MP4/MP3/Zusammenfassung sowie Abschlussbildschirm. Der responsive Aufbau der Schritte 5 bis 7 und die Bottom-Actions bleiben erhalten. Der normale Terminal-Wizard bleibt parallel verfügbar und wird nicht entfernt oder zwangsweise durch Textual ersetzt.

Die damalige Baseline schrieb zusätzlich die generischen Dateien `predigt-workflow.json` und `predigt-zusammenfassung.txt` in den Zielordner. Dieser historische Stand bleibt lesekompatibel; der aktuelle Stand verwendet die oben beschriebenen aufnahmespezifischen Namen.

Zum Baseline-Zeitpunkt war Vimeo noch nicht angebunden. Aktuell ist Vimeo in Textual verfügbar; der normale Wizard bleibt lokal und WordPress-MP3-Upload sowie WordPress-Beitrag sind weiterhin nicht automatisiert.

Die vollständige automatische Suite umfasst für diese Baseline 310 bestandene Tests. Systemcheck, Wizard-Startbarkeit, Textual-Import/App-Aufbau und das Release-ZIP `predigt-uploader-v0.2.0-local-workflow.zip` wurden ebenfalls erfolgreich geprüft.

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
Die Dienstart-Vorauswahl beruecksichtigt nun auch Freitag als Gebetsstunde. Fuer die Metadaten-Eingabe gibt es eine zentrale Dateiname-Vorschau mit sichtbaren Platzhaltern wie `[Titel]`, `[Bibelstelle]`, `[Redner]` und `[Leitung]`; der Terminal-Wizard zeigt diese Vorschau nach der Dienstartauswahl und nach fachlichen Eingaben kompakt an. Allgemeine Nutzertexte sprechen jetzt dort von Aufnahme oder Veranstaltung, wo nicht konkret die Dienstart Predigt gemeint ist. Zusaetzlich ist Textual als optionale Abhaengigkeit vorbereitet: `python -m predigt_uploader tui` startet einen experimentellen Prototyp mit Startmenue samt Statusbereich, echter Metadaten-Erfassung, Pflichtfeldpruefung, Zielordner-/Dateiname-Live-Vorschau, reiner MP4-Dateiuebersicht und reiner Einstellungen-Ansicht, wenn `.[tui]` installiert ist. Der normale Terminal-Wizard bleibt der Standard.
Der Textual-Prototyp hat nun einen gefuehrten Startablauf fuer neue Aufnahmen: Nutzer waehlen zwischen bereits geschnittener MP4 und Rohaufnahme, sehen eine filterbare Liste der neuesten MP4-Dateien aus dem passenden Ordner und landen danach in der Metadaten-Erfassung. Aus Quelle und Metadaten wird ein reines Preview-Uebergabeobjekt mit Zielordner, finaler MP4, finaler MP3 und Zusammenfassungspfad erstellt. Dateiuebernahme, LosslessCut, FFmpeg und Rohaufnahme-Aufraeumen bleiben weiterhin beim normalen Wizard.
Die Textual-Dateiauswahl nutzt nun fuer geschnittene MP4 und Rohaufnahme dieselbe Auswahl-Logik mit neuester Datei, Such-/Filterliste und manueller Datei- oder Ordner-Eingabe. MP4-Dateien werden als Tabelle mit Dateiname, Aenderungsdatum und Groesse angezeigt; Zurueck und Abbrechen bleiben getrennte Aktionen. Fehlende Metadaten-Pflichtfelder werden direkt an den Eingabefeldern markiert und die Vorschau zeigt einen klaren Bitte-ergaenzen-Hinweis.
Die Textual-Dateiauswahl zeigt die MP4-Ergebnisse nur noch in der Tabelle, nicht zusaetzlich als Textliste. Vor dem Textual-Startablauf fragt ein Sicherheitshinweis ab, ob Aufnahme und Stream in vMix beendet wurden. Im normalen Hauptmenue erscheint derselbe Hinweis vor dem produktiven Wizard-Start. Fuer Bibelstunden ist Titel/Themenreihe optional; wenn er eingetragen wird, erscheint er im gemeinsamen Dateinamen vor der Bibelstelle.
Der Textual-Startcheck ist nun eine eigene grosse Sicherheitsseite: "Nein, erst in vMix pruefen" steht links und erhaelt den Standardfokus, "Ja, Aufnahme und Stream sind beendet" fuehrt erst danach in die Dateiauswahl. Der Warnhinweis zu weiterlaufendem Stream und Datenvolumen/Kosten ist deutlich gerahmt.
Die Textual-Startcheck-Seite nutzt wieder eine breite, ruhige Sicherheitsdarstellung mit Titelrahmen, gemeinsamem Fragenpanel, Warnpanel und klar getrennten Buttons.
Für robuste Testläufe auf unterschiedlichen Windows-Rechnern gibt es `scripts/test.ps1` und die anklickbare Datei `Tests ausfuehren.cmd`. Das Script nutzt bevorzugt `%LOCALAPPDATA%\PredigtUploader\pytest` für temporäre Testdaten und Pytest-Cache, fällt bei Berechtigungsproblemen auf `%TEMP%\PredigtUploader-pytest` zurück und lässt `pyproject.toml` frei von rechnerabhängigen Temp-Pfaden.
Das Release-ZIP bleibt ein Nutzerpaket: Sichtbar im Paket sind die drei Gemeinde-Launcher fuer Einrichten, Systemcheck und Starten; der Test-Launcher wird nicht als Top-Level-Datei ausgeliefert.
Textual kann nach Datei-Auswahl und Metadaten nun einen zentralen Verarbeitungsplan anzeigen und daraus testbar Dateien vorbereiten: Zielordner erstellen, MP4 uebernehmen, MP3 per FFmpeg erzeugen, Zusammenfassung schreiben, Rohaufnahme je nach Plan behandeln und optional den Zielordner oeffnen. Der normale Wizard bleibt weiterhin produktiver Standard.
Die Textual-Ausfuehrung meldet nun direkt beim Klick sichtbar "Verarbeitung gestartet...", deaktiviert den Ausfuehren-Button, zeigt Statusschritte und endet bei Erfolg mit einer klaren Fertig-Zusammenfassung. Die Textzusammenfassung wird als UTF-8 mit BOM geschrieben, damit Umlaute in Windows Notepad und PowerShell zuverlaessiger erkannt werden.
Der Textual-Rohaufnahme-Zweig wurde fachlich korrigiert: Nach Auswahl einer vMix-Rohaufnahme folgt zuerst eine LosslessCut-/Schnitt-Seite und danach die Auswahl der geschnittenen MP4. Erst diese geschnittene MP4 wird als finale Quelle fuer MP4/MP3/Zusammenfassung verwendet; die Rohaufnahme bleibt separat fuer die optionale Aufraeum-Aktion.
Der Textual-Schnittschritt nutzt nun einen Snapshot-Ansatz: Beim LosslessCut-Schritt werden MP4-Dateien in plausiblen Exportordnern gemerkt, danach werden neue oder geaenderte MP4-Dateien vorgeschlagen und muessen bestaetigt werden. Die Dateitabelle zeigt bis zu 500 passende MP4-Dateien. Vor der finalen Verarbeitung waehlen Nutzer bewusst, ob die Rohaufnahme verschoben, kopiert oder liegen gelassen wird.
Die automatische Dienstart-Vorauswahl in Textual richtet sich nun nach dem wirksamen Aufnahmedatum: zuerst Rohaufnahme-Dateiname, dann geschnittene MP4, dann Dateidatum und erst zuletzt das heutige Datum. Solange Nutzer die Dienstart nicht manuell aendern, folgt sie weiteren Datumswechseln automatisch.
Textual prueft nach den Metadaten nun zuerst den Zielordner: fehlende, einzelne vorhandene und mehrere vorhandene Tagesordner werden sichtbar unterschieden. Die finale Pruefseite erkennt bestehende Ziel-MP4, Ziel-MP3 und Zusammenfassung und laesst die Verarbeitung erst nach bewusster Ersetzen-Entscheidung zu.
Die Textual-Konfliktentscheidung auf der finalen Pruefseite ist nun deutlicher: Bestehende Zieldateien werden kompakt als MP4, MP3 und Zusammenfassung angezeigt, rechts erscheint ein eigener Achtung-Bereich mit Zurueck-, Ersetzen- und Abbrechen-Aktion. Erst nach "Vorhandene Dateien ersetzen" wird der finale Ausfuehren-Button aktiviert.
Die finale Textual-Pruefseite erklaert nun auch ohne Konflikte direkt, dass der naechste Klick MP4, MP3 und Zusammenfassung erstellt und eine Rohaufnahme gemaess Auswahl behandelt. Bei Konflikten steht rechts ein STOPP-Hinweis mit vorhandenen Dateien und klaren Optionen; nach Erfolg weist der Status auf die manuelle Weiterbearbeitung in Vimeo/WordPress hin.
Der Textual-Ersetzen-Button ist im Konfliktfall nun als breiter, kontrastreicher Button beschriftet. Nach bestaetigtem Ersetzen verschwindet der STOPP-Text aus dem rechten Bereich, nach erfolgreicher Verarbeitung wird der finale Button deaktiviert und der Status nennt Zielordner-Kontrolle sowie manuelle Vimeo-/WordPress-Weiterarbeit.
Textual hat nun einen eigenen Doppelklick-Starter `PredigtUploader Textual starten.cmd` und das PowerShell-Skript `scripts/run-tui.ps1`. Das Release-ZIP enthaelt den normalen Wizard-Starter weiterhin unveraendert, zusaetzlich den Textual-Starter und keine Windows-`.lnk`-Verknuepfungen. Der Textual-Abschlussstatus zeigt Zielordner, finale MP4/MP3, Zusammenfassung, Kontrollliste und die manuellen naechsten Schritte fuer Vimeo und WordPress.
Die lokale Einrichtung installiert nun standardmaessig auch die optionale Textual-Abhaengigkeit (`.[tui]`, im Dev-Fall `.[dev,tui]`). Der Systemcheck prueft `import textual` und `run-tui.ps1` meldet bei fehlendem Textual konkret, dass `PredigtUploader einrichten.cmd` erneut gestartet werden soll.
Der Release-ZIP-Prozess ist nun tag-basiert und nicht mehr an hart codierte Preview-Suffixe gebunden: `make-release-zip.ps1` akzeptiert `-ReleaseTag` oder `-ReleaseName`, liest sonst einen passenden Git-Tag auf `HEAD` und faellt ohne Tag auf einen lokalen Namen aus `pyproject.toml` zurueck. `scripts/release.ps1` fuehrt erst die Tests aus und baut nur bei Erfolg das ZIP.
Der Textual-Verarbeitungsabschluss ist nun klarer: Beim Start der finalen Verarbeitung zeigt der Status, dass Dateien erstellt, kopiert oder verschoben werden, waehrend gefaehrliche Aktionen gesperrt sind. Nach Erfolg zeigt die rechte Seite Zielpfade, Rohaufnahme-Aktion und nummerierte naechste Schritte; Fehler nennen verstaendlich, dass nichts still ueberschrieben wurde.
Nach dem Blindtest verwendet Textual fuer die normale Veranstaltung den sichtbaren Begriff `Gottesdienst`, behaelt intern aber den kompatiblen Wert `Predigt` und damit das bestehende Predigt-Dateinamenschema. Die inzwischen acht Workflow-Schritte sind nummeriert, Zurueck-Hilfe und Zurueck-Buttons sind vereinheitlicht, konkrete Aktionsnamen ersetzen Ja/Nein- und allgemeine Weiter-Texte. Rohaufnahmen bleiben in Textual standardmaessig sicher am Quellort; Verschieben muss bewusst ausgewaehlt werden. Eine automatische Gottesdienst-Ordnerkennung wie `-1` existiert nicht und wird nicht erfunden; kuenftige Markerregeln sind zentral in `folders.py` vorgesehen.
Die Textual-Schritte 5 bis 7 sind nun fuer kleinere Terminalgroessen stabiler: lange Inhalte liegen in scrollbaren Bereichen, waehrend Aktionsleisten ausserhalb sichtbar bleiben. Schritt 6 zeigt je nach Ordnerstatus genau eine empfohlene Primaeraktion und blendet das Zusatzfeld erst bei Bedarf ein. Schritt 7 ist als kompakte Checkliste aufgebaut; nach Erfolg erscheint ein eigener `CompletionScreen` mit Zielpfaden, naechsten Schritten und den Aktionen Zielordner oeffnen, neue Aufnahme oder beenden.
Die aktuelle UI-Politur fuer die Textual-Oberflaeche hebt Fortschritt, Navigation und Status bunter und klarer hervor, verwendet neutrale Info-Panels statt Warnfarben fuer normale Infobloecke und laeuft auch im Textual-Startcheck wieder sauber an. Schritt 5 zeigt eine feste Validierungszeile, einen kleinen lokalen Scroll-Hinweis im Formularbereich und eine klarere Aufteilung zwischen Eingaben und Vorschau; Schritt 6 fuehrt die Zusatz-Ordnerwahl eindeutiger und Schritt 7 endet mit einem eigenen gruenen Abschlussbanner.
Der linke Formularbereich in Textual-Schritt 5 ist wieder ein eigener, hoehenbegrenzter Scrollcontainer mit sichtbarer Scrollbar bei Ueberlauf. Fokusnavigation scrollt verdeckte Felder in den sichtbaren Bereich; der lokale Pflichtfeld-Hinweis unterscheidet fehlende Felder oberhalb und unterhalb des Viewports. Pilot-Tests decken 100x32 und 120x50 Terminalzellen ab.
Textual-Schritt 6 behandelt den Zusatzordner nun als eigenen Entscheidungszustand: Status, vollstaendiger Live-Zielpfad und grosser Primaerbutton wechseln gemeinsam auf den neuen Ordner. Ein leerer Zusatz bleibt gesperrt, bestehende Zusatzordner werden sichtbar als vorhandene Ziele gemeldet und der Rueckwechsel zum normalen Tagesordner bleibt als Sekundaeraktion moeglich. Der scrollbare Inhalt und die feste Bottom-Navigation sind bei 100x32 Terminalzellen per Pilot geprueft.
Textual-Schritt 7 zeigt Dateikonflikte nun als kompakte Datei-/Zustand-/Aktionsuebersicht fuer MP4, MP3 und Zusammenfassung. Nutzer koennen vorhandene Dateien nach bewusster Bestaetigung ersetzen, fuer neue Dateien automatisch vorgeschlagene oder eigene Windows-gueltige Namen verwenden oder vorhandene Dateien vorab auf konkret angezeigte `__alt`-Namen umbenennen lassen. Alle neuen Namen werden vor Freigabe erneut auf Kollision geprueft; bis zum finalen Ausfuehren werden keine Dateien veraendert. Konfliktentscheidungen liegen im scrollbaren rechten Bereich, waehrend Ausfuehren und Navigation bei 100x32 sichtbar bleiben.

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
- Eine kurze aufnahmespezifische `<MP4-Stem> - Zusammenfassung.txt` im Zielordner schreiben.
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
- Experimentellen Textual-Prototyp optional ueber `python -m predigt_uploader tui` starten, inklusive Statusbereich, Metadaten-Erfassung mit Pflichtfeldpruefung, Zielordner-/Dateiname-Vorschau, MP4-Dateiuebersicht und Einstellungen-Anzeige.
- In Textual Quelle und Metadaten als Preview-Uebergabeobjekt vorbereiten, ohne den normalen Wizard als produktiven Workflow zu ersetzen.
- In Textual MP4-Dateien tabellarisch auswaehlen, suchen/filtern, die neueste Datei verwenden oder Datei/Ordner manuell eingeben.
- In Textual fehlende Metadaten-Pflichtfelder direkt am Eingabefeld markieren und rechts gesammelt als Bitte-ergaenzen-Hinweis anzeigen.
- In Textual nach der Metadatenpruefung eine finale Seite "Vorbereitung pruefen" mit Quelle, Zielordner, finalen Dateinamen, Zusammenfassung, Rohaufnahme-Aktion, Warnungen und Ausfuehren-Button anzeigen.
- Aus einem zentralen `PreparedRecordingPlan` heraus kleine Testdateien ueber die gemeinsame Verarbeitungsfunktion vorbereiten, inklusive Statusmeldungen fuer Zielordner, MP4, MP3, Zusammenfassung, Rohaufnahme und Fertig.
- In Textual beim Start der Datei-Vorbereitung sofort sichtbares Feedback anzeigen und nach Erfolg Zielordner, finale MP4, finale MP3, Zusammenfassung und Rohaufnahme-Aktion im Statusbereich nennen.
- In Textual Rohaufnahmen nicht mehr direkt als finale Predigt-MP4 verarbeiten, sondern zuerst LosslessCut/Schnitt und danach eine separate Auswahl der geschnittenen MP4 erzwingen.
- In Textual nach LosslessCut neue oder geaenderte MP4-Exporte per Dateisystem-Snapshot vorschlagen und vor Uebernahme bestaetigen lassen.
- In Textual vor der finalen Verarbeitung die Rohaufnahme-Aktion explizit waehlen lassen; Verschieben bleibt je nach Config die Vorauswahl, geschieht aber nicht mehr stillschweigend.
- In Textual die Dienstart anhand des wirksamen Aufnahmedatums statt pauschal anhand des heutigen Datums vorauswaehlen.
- In Textual vor der finalen Verarbeitung Zielordner-Konflikte und vorhandene Zieldateien getrennt pruefen.
- In Textual vorhandene Zieldateien mit einem gut sichtbaren Entscheidungsbereich statt nur einem deaktivierten Button behandeln.
- In Textual die finale Pruefseite mit klaren Naechster-Schritt-Hinweisen, STOPP-Konflikttexten und dynamischen MP4-Aktionstexten nachschaerfen.
- In Textual den Ersetzen-Button im Konfliktfall lesbar hervorheben und Konflikttexte nach Erfolg ausblenden.
- Eigenen Textual-Starter fuer Tests bereitstellen und den Abschlussstatus als klare Kontroll- und Weiterarbeitsseite anzeigen.
- Lokale Einrichtung und Systemcheck so erweitern, dass die Textual-Oberflaeche nach `PredigtUploader einrichten.cmd` startbar ist.
- Release-ZIP-Namen dynamisch aus Parameter, Git-Tag oder lokalem Fallback ableiten und optionalen Release-Ablauf mit Tests bereitstellen.
- Textual-Verarbeitung mit klarer Laufmeldung, Abschlussstatus, Folgeaktionen und verstaendlichem Fehlerstatus nachschaerfen.
- Textual-Begriffe, nummerierte Nutzerfuehrung, Zurueck-Navigation und sichere Rohaufnahme-Standards anhand des Blindtests verbessern.
- Textual-Schritte 5 bis 7 scrollfest gestalten, Zielordnerentscheidung vereinfachen und eigenen Abschlussscreen einfuehren. Der offene Scroll-Hinweis fuer Schritt 5 ist als kleine lokale Badge im Formularbereich umgesetzt.
- Textual-Standardweg auf Rohaufnahme ausrichten, alle Schritte mit einer kompakten Fortschrittsanzeige versehen und Aktionsleisten fuer kleine Terminalfenster fest sichtbar halten.
- Textual-Zieldateikonflikte wahlweise durch eindeutige neue Dateinamen, Sicherung vorhandener Dateien oder bewusst bestaetigtes Ersetzen aufloesen.
- Textual-Statusbereiche mit einheitlichen Info-, Warn-, Fehler- und Erfolgsmeldungen hervorheben; Vimeo wird im achten Schritt ausschließlich nach bewusster Nutzeraktion gestartet.
- Vor neuen Aufnahmen in Textual und im normalen Hauptmenue bewusst bestaetigen lassen, dass vMix-Aufnahme und Stream beendet sind.
- Den Textual-Startcheck als prominente Sicherheitsseite mit Standardfokus auf "Nein" anzeigen.
- Die Textual-Startcheck-Fragen als getrennte grosse Warnbloecke darstellen.
- Bibelstunden optional mit Titel/Themenreihe im Dateinamen bilden, ohne Titel weiterhin nur mit Bibelstelle.
- Tests ueber `scripts/test.ps1` oder `Tests ausfuehren.cmd` mit lokalen, beschreibbaren Temp- und Cache-Ordnern ausfuehren.

## Bewusst noch nicht enthalten

- automatischer Vimeo-Upload ohne ausdrücklichen Nutzerklick oder eine Vimeo-Anbindung des normalen Wizards.
- Wiederaufnahme eines unvollständigen produktiven Vimeo-States direkt aus dem Textual-Startmenü.
- WordPress-Automatisierung.
- Login-, Token- oder API-Key-Verwaltung.
- Automatische Predigt-Erkennung per KI.
- Komfortable Windows-GUI oder Datei-Auswahldialog.
- Vollständige LosslessCut-Automatisierung oder eigener Video-Editor.

## Nächster geplanter Schritt

Als Nächstes den neuen achten Textual-Schritt manuell mit einer kleinen, bewusst gewählten lokalen Aufnahme prüfen: zunächst Vimeo überspringen und den offenen Abschluss kontrollieren, danach in einem separaten Lauf den Upload bewusst starten, Fortschritt, Vimeo-URL, Embed-Kopieren und erfolgreichen Abschluss prüfen. Anschließend ist der WordPress-MP3-/Beitragsworkflow der nächste große fachliche Schritt; eine Startmenü-Wiederaufnahme für unvollständige Vimeo-States kann davor als kleine eigene UX-Aufgabe ergänzt werden.

## Sicherheits-Hinweis

Keine Zugangsdaten, API-Keys, Tokens, Passwörter oder privaten Pfade ins Repository einbauen oder committen. Beispieldateien dürfen nur Platzhalter enthalten.
