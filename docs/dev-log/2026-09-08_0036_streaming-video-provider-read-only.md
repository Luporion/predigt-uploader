# Entwicklungsbericht: StreamingVideoProvider read-only

## Ziel

Sichere API-Grundlage, Diagnose und eine echte lesende Textual-Bibliothek für vollständige Stream-Aufzeichnungen ergänzen, ohne Vimeo oder den lokalen Workflow umzubauen.

## Geänderte Dateien

- `src/predigt_uploader/credentials.py`
- `src/predigt_uploader/publishing/streaming_video_provider.py`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_credentials.py`, `tests/test_streaming_video_provider.py`, `tests/test_cli.py`, `tests/test_tui.py`
- `README.md`, `STATUS.md`, `TASKS.md`
- `docs/streaming-video-provider.md`

## Was wurde umgesetzt?

Ein eigener read-only Provider verwendet die offiziellen XML-Dienste für Auth, Videoliste, Live-Recordings, Properties und Player-Code. API-Key/API-Code liegen gemeinsam in Keyring; der 48-Stunden-Token bleibt nur im Speicher und wird bei eindeutigem Authfehler einmal erneuert. Die CLI-Diagnose untersucht Videos, Live-Aufzeichnungen und Properties ohne rohe Credential-Antworten auszugeben.

Textual erhielt den Hauptmenüpunkt `Stream-Aufzeichnungen`, asynchrones Laden, Suche, Sortierung, Details und offizielle Zuschauer-Link-Aktionen. Die Einstellungen verwalten den Zugang maskiert und prüfen ihn mit einem reinen Leseaufruf.

Die Downloadfreigabe bleibt offen: Es wird weder ein Parameter geraten noch HTML gescrapt oder eine Property geschrieben. Ebenso bleiben Ablaufdatum und Passwortschutz späteren Aufgaben vorbehalten.

## Tests

Parser-, Token-Renewal-, Credential-, CLI- und Textual-Pilot-Tests wurden ergänzt. Es finden keine echten Netzwerkzugriffe statt. Die vollständige Suite besteht mit **473 Tests**. Der neue asynchrone Bibliotheksstart wird nach dem ersten Layout-Refresh terminiert; der zugehörige Pilot-Test bestand zusätzlich fünfmal hintereinander.

## Offene Punkte / Risiken

- Der echte Account muss zeigen, ob abgeschlossene Aufzeichnungen zugleich in `svp_list_videos` und `svp_list_recordings` erscheinen.
- Die reale Form des mit `player_link` gelieferten Codes wird beim manuellen Test verifiziert; der Parser unterstützt direkte und in HTML enthaltene offizielle HTTP(S)-Links.
- Eine dokumentierte Download-Property ist noch nicht bestätigt.

## Nächster sinnvoller Schritt

Read-only Diagnose am echten Konto ausführen und danach anhand der Antwort entscheiden, welche Datenquelle die produktive Aufzeichnungsliste priorisieren soll.
