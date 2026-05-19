# Entwicklungsbericht: Temporaerer Rohaufnahme-Ordner

## Ziel

Die Rohaufnahme-Auswahl reparieren, wenn der konfigurierte `vmix_storage`-Ordner auf dem Zielrechner nicht gefunden wird und der Nutzer stattdessen manuell einen Ordner eingibt.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `tests/test_cli.py`
- `config.example.toml`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Manuell eingegebene Rohaufnahme-Ordner werden fuer den aktuellen Wizard-Lauf als temporaerer Rohaufnahme-Quellordner verwendet.
- Nach Eingabe eines solchen Ordners erscheint wieder das normale Rohaufnahme-Menue mit neuester Aufnahme, neuesten Aufnahmen, Suche/Filter, manueller Eingabe und Abbruch.
- Suche/Filter nutzt auch den temporaeren Ordner.
- `Zurueck` aus Unterauswahlen fuehrt direkt ins Rohaufnahme-Hauptmenue zurueck und erzeugt keine zweite blinde Dateiliste.
- UNC-Pfade werden als normale Nutzereingabe akzeptiert.
- `docs/config.md` erklaert, dass UNC-Pfade auf Zielrechnern oft robuster sind als gemappte Laufwerke.
- `config.example.toml` enthaelt nur Beispielpfade und einen UNC-Beispielkommentar.

## Tests

- `python -m pytest` erfolgreich: 129 Tests.

## Offene Punkte / Risiken

- UNC-Zugriff wurde als Pfadverarbeitung getestet. Der echte Netzwerkzugriff sollte auf dem Gemeinderechner mit der realen lokalen `config.toml` geprueft werden.

## Nächster sinnvoller Schritt

Auf dem Zielrechner `vmix_storage` testweise auf einen fehlenden Pfad setzen, dann einen UNC-Ordner manuell eingeben und Rohaufnahme-Menue, Suche/Filter und `Zurueck` praktisch pruefen.
