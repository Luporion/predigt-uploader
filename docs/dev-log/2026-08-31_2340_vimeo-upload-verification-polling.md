# Entwicklungsbericht: Vimeo-Upload-Verifikations-Polling mit Backoff

## Ziel
Behebung des Timing-Problems bei der Vimeo-Upload-Verifikation: Nach abgeschlossenem TUS-Dateitransfer zeigt Vimeo kurzzeitig `upload.status=in_progress`, bevor es zu `complete` wechselt. Dieses sollte als normaler Zwischenzustand toleriert werden, nicht als sofortiger Fehler.

## Problem (Ursache)
1. Nach vollständigem TUS-Upload (~2 GB Test) war Vimeo noch kurz im Zustand `upload.status=in_progress`
2. Die alte Verifikation versuchte nur 6 × mit 2-Sekunden-Intervallen (max ~12 Sekunden)
3. Nach Timeout wurde sofort ein nicht-recoverable Error geworfen
4. Beim Retry funktionierte es, da Vimeo zwischenzeitlich zu `complete` gewechselt hatte

## Geänderte Dateien

### 1. `src/predigt_uploader/publishing/vimeo.py`
- **`_verify_remote_video()`**: Erweitert von 6 Versuchen auf exponential Backoff mit bis zu 15 Versuchen
  - Backoff-Schema: 1s, 2s, 4s, 8s, 16s, 30s, 30s, ... (total ~150 Sekunden)
  - `in_progress` wird als normaler Zwischenzustand toleriert
  - Nur `error` oder `canceled` führt zu sofortigem Fehler
  - Parameter `total_bytes` für korrekte Progress-Anzeige hinzugefügt
  - Error-Meldung ist jetzt recoverable: enthält bekannte Video-ID zur Wiederverwendung

- **`publish()`**: Parameter `total_bytes=state.vimeo.upload_size` an `_verify_remote_video()` übergeben

### 2. `src/predigt_uploader/tui_app.py`
- **`TUI_VIMEO_STAGE_LABELS`**: Labels präzisiert zur semantischen Klarheit
  - `"upload"`: "Video wird hochgeladen" → **"Datei zu Vimeo übertragen"**
  - `"verify_upload"`: "Upload wird geprüft" → **"Vimeo bestätigt den Upload"**

### 3. `tests/test_vimeo.py` (5 neue Tests)
- **`test_upload_verification_tolerates_in_progress_with_exponential_backoff`**: Zeigt, dass mehrere `in_progress`-Antworten toleriert werden
- **`test_upload_verification_timeout_is_recoverable_with_same_video_id`**: Dauerhafte `in_progress`-Antworten führen zu recoverable Error mit gesicherter Video-ID
- **`test_upload_verification_preserves_total_bytes_in_progress_display`**: Final-Bytes werden über Verifikation beibehalten (Fehler "0 B / 0 B" behoben)
- **`test_retry_with_known_upload_status_skips_remote_video_creation`**: Retry nutzt bestehende Video-ID, erstellt keinen Doppel-Platzhalter
- **`test_upload_and_transcode_status_are_independent`**: `upload.status=complete` mit `transcode.status=in_progress` ist OK und blockiert nicht

### 4. `tests/test_tui.py`
- Labels aktualisiert in Tests `test_tui_vimeo_progress_and_success_text_are_clear` und `test_tui_vimeo_error_keeps_local_files_and_allows_later_completion`

## Was wurde umgesetzt?

### 1. Polling mit Backoff ✓
```python
backoff_schedule = [1, 2, 4, 8, 16] + [30] * 10  # ~150s max
```
- Exponential Backoff statt konstant 2s
- Längerer Timeout (~120 Sekunden) für echte Fälle
- Keine Endlosschleife

### 2. Progress-Tracking ✓
- `_verify_remote_video(total_bytes=...)` Parameter für korrekte Anzeige
- Progress während Polling: `VimeoProgress("verifying_upload", total_bytes, total_bytes)`
- Bytes gehen nicht verloren beim Wechsel zu Folder-Zuweisung

### 3. UI-Updates während Polling ✓
- Checklisten-Label geändert für semantische Klarheit
- `verifying_upload` Phase zeigt "Vimeo bestätigt den Upload"
- Fortschritt nach Upload: `1,97 GB / 1,97 GB` statt `0 B / 0 B`

### 4. Upload vs. Transkodierung ✓
- Klare Unterscheidung in Checkliste und Code
- `transcode_status=IN_PROGRESS` nach vollständigem `upload.status=COMPLETE` ist OK
- Publishing kann local erfolgreich sein, während Vimeo noch transkodiert

### 5. Resume-Sicherheit ✓
- Bekannte Video-ID wird in der Error-Nachricht und im State (`.error`) gespeichert
- `VimeoUploadError` ist auf recoverable Error klassiliert (nicht mehr "Fehler, abbrechen")
- Retry-Versuch verwendet `.video_id` und `.upload_uri` wieder

## Tests

Alle 399 Tests bestehen:
- 5 neue Tests für Upload-Verifikations-Polling
- Bestehende Tests regressionslos
- Nur Fake-Transporte in der Testsuite (kein echter Vimeo-Zugriff)

```bash
cd v:\predigt-uploader-repo\predigt-uploader
python -m pytest tests/ -q
# 399 passed
```

## Polling-/Timeout-Semantik

```
TUS-Upload abgeschlossen
  ↓ (Byte-Bestätigung von Vimeo)
  ↓ 
Verifikation (Polling mit Backoff):
  Versuch 1: upload.status=in_progress  → warte 1s
  Versuch 2: upload.status=in_progress  → warte 2s
  Versuch 3: upload.status=complete     → erfolg!
  
ODER:
  Alle 15 Versuche: upload.status=in_progress (bis ~150s)
  → Recoverable Error mit gesicherter Video-ID
  → Retry startet von vorne mit gleicher ID
```

## Fehler-Fortschrittsanzeige (Fix)

**Alt (Fehler):**
```
0 B / 0 B
100 %
```

**Neu (Korrekt):**
```
1,97 GB / 1,97 GB
100 %
```

Bytes werden im State (`upload_size`, `upload_offset`) gespeichert und nutzen den finalen Wert bei Verifikation.

## Retry-Sicherheit

Getestete Szenarien:
1. Erstes Upload mit Timeout → recoverable Error
2. Retry mit gleichem State:
   - `.video_id` wird wiederverwendet ✓
   - `.upload_uri` wird wiederverwendet ✓
   - Kein POST `/me/videos` für Doppel-Video ✓
   - Neuer Verifikations-Polling mit frischen Versuchen ✓

## Manueller Testanleitung

Nach dieser Änderung:

1. **Normales Szenario** (schnelle Verifikation):
   ```
   Upload: 100 %
   Vimeo bestätigt den Upload  ← sofort oder nach 1-2s
   Ordner wird zugeordnet
   Embed-Code wird abgerufen
   ✓ Erfolg
   ```

2. **Langsames Szenario** (Vimeo-Verzögerung):
   ```
   Upload: 100 %
   Vimeo bestätigt den Upload  ← Status: in_progress (1s)
                               ← Status: in_progress (2s)
                               ← Status: in_progress (4s)
                               ← Status: complete (OK!)
   Ordner wird zugeordnet
   ✓ Erfolg
   ```

3. **Timeout-Szenario** (Fehler nach Polling):
   ```
   Upload: 100 %
   Vimeo bestätigt den Upload  ← Status: in_progress (1s, 2s, 4s, ..., 30s)
                               ← Timeout nach ~120s
   ✗ Fehler: "Vimeo-Veröffentlichung noch nicht abgeschlossen"
   
   → Retry-Button funktioniert:
     Benutzer klickt Retry
     → Polling startet mit gleicher Video-ID
     → (Vimeo ist zwischenzeitlich zu complete gewechselt)
     ✓ Erfolg
   ```

4. **Unabhängige Transkodierung**:
   ```
   Upload bestätigt: complete
   Transkodierung: IN_PROGRESS
   → Publishing lokal erfolgreich
   → Vimeo verarbeitet das Video
   ```

## Offene Punkte
- Keine (alle Anforderungen erfüllt)

## Nächster sinnvoller Schritt
- Feldertest mit realen 2+ GB Predigtsaufnahmen
- Evtl. weitere Backoff-Optimierung basierend auf echtem Vimeo-Verhalten
- Dokumentation zur Upload-Resume-Architektur vervollständigen
