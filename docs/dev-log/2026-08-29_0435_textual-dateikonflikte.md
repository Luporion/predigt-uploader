# Entwicklungsbericht: textual-dateikonflikte

## Ziel

Dateikonflikte in Textual-Schritt 7 vollstaendig, verstaendlich und ohne stilles Ueberschreiben behandeln. Die gemeinsame Processing-Logik soll alle sicherheitsrelevanten Dateinamen- und Umbenennungsentscheidungen tragen.

## Geänderte Dateien

- `src/predigt_uploader/processing.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_processing.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Der zentrale `PreparedRecordingPlan` kann konkrete Umbenennungen vorhandener Ausgabedateien enthalten.
- Die gemeinsame Processing-Logik validiert Windows-Dateinamen, erhaelt die geforderte Dateiendung und weist ungueltige Zeichen, reservierte Namen, falsche Endungen sowie bereits vorhandene Ziele zurueck.
- Automatische Vorschlaege verwenden `(2)`, `(3)` und weitere freie Nummern.
- Eigene Namen fuer MP4, MP3 und Zusammenfassung werden gemeinsam geprueft. Dadurch kann eine kompakte Strategie fuer alle Konflikte verwendet werden, ohne mehrere Bestaetigungsseiten zu erzeugen.
- Vorhandene Dateien koennen als alternative Strategie auf vorab berechnete `__alt`-Namen umbenannt werden. Schritt 7 zeigt jede Abbildung `ALT -> NEU` vor dem Schreiben an.
- Der Umbenennungsschritt prueft vorab alle Quellen und Ziele. Scheitert eine Umbenennung innerhalb dieses Schritts, werden bereits ausgefuehrte Umbenennungen rueckgaengig gemacht.
- Ersetzen bleibt eine rote, explizite Entscheidung. Erst der separate finale Ausfuehren-Button schreibt oder ersetzt Dateien.
- Die Schritt-7-Uebersicht zeigt fuer MP4, MP3 und Zusammenfassung jeweils Datei, Zustand und geplante Aktion mit den tatsaechlichen Dateinamen.
- Konfliktstrategien liegen rechts im scrollbaren Entscheidungsbereich. Unten bleiben der finale Ausfuehren-Button und die Navigation sichtbar.
- Der Zurueck-Button lautet bei Konflikten weiterhin `Zurueck und anderen Ordner waehlen` und fuehrt zu Schritt 6.

Die bestehende gemeinsame Strategie gilt fuer alle erkannten Konflikte. Einzelne Zieldateinamen koennen dennoch getrennt bearbeitet werden. Unterschiedliche destruktive Strategien pro Datei wurden bewusst nicht eingefuehrt, weil drei separate Ersetzen-/Sichern-Bestaetigungen die letzte Pruefseite fuer normale Nutzer unverhaeltnismaessig kompliziert machen wuerden.

## Tests

- Keine Konflikte sowie einzelne MP4-, MP3- und Zusammenfassungs-Konflikte.
- Mehrere gleichzeitige Konflikte.
- Explizites Ersetzen.
- Automatische eindeutige `(2)`-/`(3)`-Namen.
- Benutzerdefinierte neue Namen und erhaltene Endungen.
- Erneute Kollision eines eingegebenen Namens.
- Ungueltige und reservierte Windows-Dateinamen.
- Konkrete Umbenennungen vorhandener Dateien und keine Veraenderung vor finaler Ausfuehrung.
- Ausfuehrung der bestaetigten vorhandenen-Datei-Umbenennung.
- Rueckkehr von Schritt 7 zu Schritt 6.
- Pilot bei `100x32`: auffaellige Konfliktmeldung, Dateiuebersicht, erreichbare Namensfelder, Validierungszustand, Scrollbereich und sichtbare Bottom-Actions.
- Processing- und TUI-Tests gemeinsam: 113 Tests bestanden.
- Komplette Testsuite: 303 Tests bestanden.

## Offene Punkte / Risiken

- Wenn nach erfolgreich umbenannten Altdateien erst eine spaetere Aktion wie FFmpeg fehlschlaegt, bleibt der nachvollziehbare Zwischenstand aus Alt-Sicherungen und bereits erstellten Dateien bestehen. Eine vollstaendige Transaktion ueber MP4-Kopie, externes FFmpeg, Zusammenfassung und optionale Rohaufnahme-Aktion waere erheblich komplexer und ist nicht Teil dieser Aenderung.
- Sehr lange Dateinamen oder UNC-Pfade sollten auf dem Zielrechner visuell geprueft werden; der Bereich ist scrollbar und Dateinamen werden umgebrochen.

## Nächster sinnvoller Schritt

Schritt 7 auf dem Zielrechner mit einem einzelnen und drei gleichzeitigen Konflikten durchklicken und die drei Strategien ohne finalen Klick sowie mit kleinen Testdateien kontrollieren.
