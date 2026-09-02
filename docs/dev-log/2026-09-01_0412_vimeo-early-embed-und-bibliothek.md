# Entwicklungsbericht: Vimeo Early-Embed und Bibliothek

## Ziel

Vimeo-Link und Embed-Code sollen nach Anlage des Vimeo-Videoobjekts möglichst früh nutzbar sein, ohne den bewährten tus-/Resume-Pfad zu verändern. Zusätzlich soll Textual echte Videos aus dem konfigurierten Team-Bibliotheksordner anzeigen.

## Geänderte Dateien

- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_vimeo.py`
- `tests/test_tui.py`
- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`
- dieser Entwicklungsbericht

## Was wurde umgesetzt?

### Früher Vimeo-Link und Embed-Code

Der vorhandene `VimeoPublishingService` speichert direkt nach `POST /me/videos` weiterhin Video-URI und -ID und übernimmt nun auch Link, Player-URL und direkt gelieferte Embed-Daten. Noch vor dem ersten tus-PATCH wird über die vorhandene Video-/oEmbed-/Player-Kette ein verwendbarer Embed-Code versucht. Erfolg wird atomar im aufnahmespezifischen Workflow-State gespeichert und als Fortschrittsereignis an Textual gemeldet.

Der frühe Abruf ist bewusst opportunistisch. Liefert Vimeo den Embed-Code noch nicht oder tritt ein vorübergehender API-Fehler auf, läuft der Datei-Upload weiter. Nach bestätigter Übertragung wird erneut versucht; der abschließende Pflichtabruf und damit die bisherigen Erfolgskriterien bleiben erhalten. URI/ID und vorhandene Remote-Daten werden bei Folgefehlern nicht vergessen.

Schritt 8 zeigt Link und Embed als eigene Stufen. `Vimeo öffnen` beziehungsweise `Embed-Code kopieren` werden unmittelbar aktiviert, sobald die jeweilige Information im State steht – unabhängig davon, ob der tus-Upload oder Vimeos Verarbeitung noch läuft. Nach 100 Prozent unterscheidet der Screen zwischen vollständig übertragener Datei und noch laufender Vimeo-Transkodierung.

### Vimeo-Bibliothek

`VimeoPublishingService.list_target_folder_videos()` verwendet die bestehende Vorprüfung und lädt `GET /users/{team_owner_user_id}/projects/{target_folder_id}/videos` vollständig über `paging.next`. API-Antworten werden in UI-unabhängige Bibliotheksmodelle für Video- und Downloadmetadaten normalisiert.

Im Textual-Hauptmenü öffnet `Vimeo-Bibliothek` einen rein lesenden Screen. Das Laden läuft in einem Textual-Thread-Worker und blockiert die Oberfläche nicht. Loading-, Leer- und Fehlerzustände, eine lokale Titelsuche, Tabelle, Videoauswahl sowie Öffnen/Kopieren/Details sind vorhanden. Die Bottom-Actions bleiben auch bei 100×32 Terminalzellen erreichbar.

Downloadfähigkeit wird nicht geraten. Nur explizite HTTPS-Links aus Vimeos API-Feld `download` gelten als verfügbare Varianten. Die erste Version zeigt Qualität, Auflösung, Größe und Typ an, startet aber noch keinen Download. `files`, Player-URL und Embed-Code werden nicht als Downloadrecht interpretiert.

## Tests

Ergänzt wurden Backend-Tests für sofort verfügbaren Embed-Code, zunächst fehlenden und später verfügbaren Embed-Code, einen nicht fatalen frühen API-Fehler, frühe Link-/State-Persistenz, Pagination, mehrere beziehungsweise keine Bibliotheksvideos, API-/Konfigurationsfehler sowie vorhandene und fehlende Download-Capability.

Textual-Pilot-Tests prüfen die frühe Buttonfreigabe während eines laufenden Uploads, Bibliotheksladung, Auswahl, Titelfilter, Details, capabilityabhängige Buttons, leeren Ordner, Fehlerzustand und die feste Aktionsleiste bei 100×32.

Die gezielte Vimeo-/TUI-Suite ist grün. `scripts/test.ps1` schließt die vollständige Suite mit **407 bestandenen Tests** ab. Es wurden keine echten Vimeo-Netzwerkzugriffe oder Uploads ausgeführt.

## Manuelle Prüfung

1. Textual starten und `Vimeo-Bibliothek` öffnen.
2. Team und Ordner `Predigten` sowie mehrere reale Videos kontrollieren.
3. Nach Titel filtern, ein fertiges und ein noch verarbeitetes Video auswählen.
4. Vimeo-Link und Embed-Code kopieren und die Detailanzeige prüfen.
5. Kontrollieren, ob Vimeo für einzelne Videos Downloadvarianten liefert; es darf dabei kein Download starten.
6. Eine bewusst gewählte größere MP4 über Schritt 8 oder `Direkt zu Vimeo` starten.
7. Direkt nach der Remote-Anlage beobachten, ob Link-/Embed-Stufen grün und die beiden Buttons schon während des laufenden Balkens aktiv werden.
8. Bei 100 Prozent kontrollieren, dass eine noch laufende Transkodierung ausdrücklich als Vimeo-Verarbeitung und nicht als erfundener Prozentwert erscheint.

## Offene Punkte / Risiken

- Vimeo kann Embed-Daten je nach Privacy und Verarbeitungszustand erst später liefern; der bestehende Retry und `vimeo-embed` bleiben dafür maßgeblich.
- Downloadfelder sind token-, konto-, privacy- und videospezifisch und können zeitlich begrenzte Links enthalten. Ein tatsächlicher Download mit Zielauswahl und Ablaufprüfung ist bewusst noch nicht implementiert.
- Die Suche arbeitet in dieser ersten Version lokal über die vollständig geladenen Ordnervideos. Serverseitige Suche und mehrere Ordner bleiben mögliche spätere Erweiterungen.
- Es wurde kein echter Vimeo-Netzwerkzugriff automatisch ausgeführt.

## Nächster sinnvoller Schritt

Early-Embed und Bibliothek mit dem realen Teamkonto manuell prüfen. Danach kann entweder ein sicherer Download ausgewählter, explizit angebotener Vimeo-Dateien ergänzt oder die WordPress-Publishing-Phase begonnen werden.
