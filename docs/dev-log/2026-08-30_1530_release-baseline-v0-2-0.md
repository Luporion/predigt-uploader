# Entwicklungsbericht: Release-Baseline v0.2.0

## Ziel

Den abgeschlossenen lokalen Workflow versions- und release-seitig als `v0.2.0-local-workflow` absichern, ohne Anwendung, UI oder Konfliktlogik zu verändern.

## Geänderte Dateien

- `pyproject.toml`: Projektversion von `0.1.0` auf `0.2.0` angehoben
- `src/predigt_uploader/__init__.py`: doppelte hartcodierte Version entfernt; Paketmetadaten werden über `importlib.metadata` gelesen
- `scripts/make-release-zip.ps1`: klarer Versions-Fallback, Tag-Validierung und minimale Nutzerpaket-Liste
- `README.md`, `STATUS.md`, `docs/release-v1-5.md`: Versionsquelle, Tag- und ZIP-Strategie dokumentiert
- `tests/test_manual_test_assets.py`: Versionsquelle, Release-Namen, Tag-Schutz und Paketinhalt abgesichert

## Was wurde umgesetzt?

Die alte ZIP-Bezeichnung stammte aus `version = "0.1.0"` in `pyproject.toml`. Derselbe Wert war zusätzlich in `src/predigt_uploader/__init__.py` hartcodiert. Ohne Tag auf `HEAD` ergänzte das Release-Skript bisher `-local`, wodurch `predigt-uploader-v0.1.0-local.zip` entstand.

`pyproject.toml` ist jetzt die einzige Quelle der numerischen Version `0.2.0`. `__version__` wird aus den installierten Paketmetadaten gelesen. Das Release-Skript verwendet ohne passenden HEAD-Tag den dokumentierten Kanal `local-workflow`; daraus entsteht automatisch `predigt-uploader-v0.2.0-local-workflow.zip`.

Nur Tags, deren numerischer Teil zur Version aus `pyproject.toml` passt, werden auf `HEAD` automatisch verwendet. Ein explizit übergebener abweichender `-ReleaseTag` wird mit einer klaren Fehlermeldung abgelehnt. `-ReleaseName` bleibt als bewusster manueller Paketname verfügbar.

Das Nutzer-ZIP kopiert nicht mehr pauschal den gesamten Ordner `scripts/`. Enthalten sind nur Setup, Systemcheck sowie Wizard- und Textual-Starter. Test- und Release-Werkzeuge werden nicht ausgeliefert.

## Tests

- vollständige Suite: **310 bestanden** in 10,10 Sekunden
- gezielter Negativtest: `v0.1.0-old` wird als unpassender Release-Tag abgelehnt
- PowerShell-Syntaxprüfung des Release-Skripts: erfolgreich
- `predigt-uploader-v0.2.0-local-workflow.zip` ohne Namensparameter erfolgreich erzeugt
- ZIP-Inhalt geprüft: 28 Einträge; `workflow_state.py`, Publishing-Dokumentation, Version `0.2.0` und benötigte Laufzeitskripte vorhanden
- nicht enthalten: `.git`, `.venv`, Tests, Test-/Release-Skripte, lokale Config, Secrets, Logs, Cache-, Build- oder Python-Artefakte

## Offene Punkte / Risiken

- Vor einem späteren echten Release müssen Commit und Tag weiterhin bewusst durch einen Menschen erstellt werden.
- Die vorhandenen älteren Tags bleiben als Historie erhalten; sie bestimmen den automatischen Namen nur dann, wenn ihre numerische Version zu `pyproject.toml` passt.
- Es wurde kein Git-Tag und kein Commit erzeugt.

## Nächster sinnvoller Schritt

Den aktuellen Gesamtstand reviewen und committen, anschließend bewusst den annotierten Tag `v0.2.0-local-workflow` setzen. Erst danach mit der separat beauftragten Vimeo-Integration beginnen.
