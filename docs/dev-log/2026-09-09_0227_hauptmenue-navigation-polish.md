# Entwicklungsbericht: Hauptmenü-Navigation-Polish

## Ziel

Die Aufnahmewege im Textual-Hauptmenü sollen logisch zusammenstehen und der Bereich für vollständige StreamingVideoProvider-Aufzeichnungen soll klarer benannt und optisch abgesetzt sein.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `docs/dev-log/2026-09-09_0227_hauptmenue-navigation-polish.md`

## Was wurde umgesetzt?

`Direkt zu Vimeo hochladen (Admin / Sonderfall)` steht jetzt unmittelbar unter `Neue Aufnahme vorbereiten`. Darunter folgt als eigener kompakter, seitlich markierter Bereich der in `Vollständige Stream-Aufzeichnungen` umbenannte StreamingVideoProvider-Einstieg. Seine erklärende Hilfszeile bleibt erhalten. `MP4-Dateien ansehen`, die bereits vorhandene Vimeo-Bibliothek, Einstellungen, Systemcheck-Hinweis und Beenden folgen darunter.

Alle bestehenden Button-IDs und Event-Routen bleiben unverändert. Vimeo-Upload, StreamingVideoProvider-Zugriff und sonstige Fachlogik wurden nicht verändert.

## Tests

Ein Textual-Pilot-Test prüft die wesentliche Reihenfolge, die neue Beschriftung, die unveränderte Hilfszeile und den eigenständigen StreamingVideoProvider-Layoutbereich. Zusätzlich wurde die vollständige Testsuite ausgeführt.

## Offene Punkte / Risiken

Die zusätzliche bestehende Funktion `Vimeo-Bibliothek` bleibt im Hauptmenü erhalten und steht nach `MP4-Dateien ansehen`. Bei außergewöhnlich kleinen Terminalhöhen kann weiterhin die allgemeine Terminalskalierung maßgeblich sein; die getestete normale Ansicht bleibt bedienbar.

## Nächster sinnvoller Schritt

Die neue Gruppierung einmal in der regulären Windows-Terminalgröße visuell prüfen; weitere UI-Änderungen sind für dieses kleine Arbeitspaket nicht vorgesehen.
