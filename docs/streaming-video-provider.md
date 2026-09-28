# StreamingVideoProvider: read-only Integration

## Umfang

Diese erste Integration liest Stream-Aufzeichnungen und erzeugt offizielle Zuschauer-Links. Sie verändert keine Videos. Downloadfreigabe, Verfügbarkeit/Ablaufdatum und Passwortschutz sind noch nicht implementiert.

Die Textual-Bibliothek kombiniert normale On-Demand-Einträge mit den deduplizierten Recording-Ergebnissen aller in der Videoliste erkannten Live-Broadcasts. Damit funktioniert die erste Version sowohl dann, wenn Aufzeichnungen bereits in `svp_list_videos` auftauchen, als auch bei einer zusätzlichen Zuordnung über `svp_list_recordings`.

## Offizielle API

Basis ist ausschließlich die [offizielle StreamingVideoProvider-API-Dokumentation](https://docs.streamingvideoprovider.com/). Der Provider verwendet diese GET-Dienste:

| Dienst | Verwendung |
|---|---|
| `svp_auth_get_token` | temporären Auth-Token aus API-Key und API-Code beziehen |
| `svp_list_videos` | Videos und Live-Broadcasts des Kontos auflisten |
| `svp_list_recordings` | Aufzeichnungen zu einem Live-Broadcast lesen |
| `svp_get_video_properties` | sichtbare/editierbare Eigenschaften diagnostizieren, nicht ändern |
| `svp_get_player_code` | mit `embed_type=player_link` den offiziellen Zuschauer-Link erzeugen |

Die API liefert XML. Der Player-Code liegt Base64-kodiert in `embed_code_html`; der Client dekodiert daraus eine von SVP gelieferte HTTP(S)-Adresse. Eine URL wird nie aus `clip_key` geraten.

## Zugangsdaten

Normale Nutzer richten API-Key und API-Code maskiert unter `Einstellungen > StreamingVideoProvider` ein. Beide Werte liegen gemeinsam im Windows Credential Manager unter `PredigtUploader / StreamingVideoProvider`. Sie stehen nicht in `config.toml`, Workflow-State, Logs oder Diagnoseausgaben. Nach der Einrichtung zeigt die Oberfläche nur den Status.

Für Entwicklung und CI können beide Prozessvariablen gemeinsam gesetzt werden:

```powershell
$env:PREDIGT_UPLOADER_SVP_API_KEY = "..."
$env:PREDIGT_UPLOADER_SVP_API_CODE = "..."
```

Die Umgebungsvariablen haben Vorrang. Der daraus erzeugte API-Token wird nur im Prozess gespeichert. Laut offizieller Dokumentation ist er 48 Stunden gültig. Meldet ein lesender Dienst eindeutig einen Auth-/Tokenfehler, authentifiziert sich der Client einmal neu und wiederholt genau den Leseaufruf.

## Diagnose

`python -m predigt_uploader svp-check` authentifiziert sich und meldet die Anzahl aus `svp_list_videos`.

`python -m predigt_uploader svp-diagnose` zeigt Anzahl und neueste Videos, erkannte Live-Broadcasts, deren Ergebnisse aus `svp_list_recordings`, Überschneidungen der Recording-IDs mit der normalen Videoliste und Property-Namen einer kleinen Stichprobe. Die Diagnose gibt keine kompletten XML-Antworten und keine Secrets aus. Sie verändert nichts.

## Downloadfreigabe und spätere Funktionen

Die öffentliche Dokumentation bestätigt derzeit keinen eindeutigen Video-Property-Parameter für einen Zuschauer-Downloadbutton. Die Diagnose sucht deshalb nur nach sichtbar gelieferten Property-Namen mit `download`; sie ändert keinen Wert. Bis ein dokumentierter Parameter am echten Konto bestätigt ist, gilt: **Downloadfreigabe über dokumentierte API derzeit noch nicht bestätigt.**

Die dokumentierten Dienste für zeitliche Verfügbarkeit und Passwortpakete werden absichtlich erst in einem eigenen Auftrag umgesetzt. Im aktuellen UI gibt es dafür keine funktionslosen Schalter.

## Manueller Realtest

1. Textual starten und unter `Einstellungen > StreamingVideoProvider` API-Key und API-Code einrichten.
2. `Verbindung prüfen` wählen; erwartet werden `StreamingVideoProvider-Verbindung: OK` und die Videoanzahl.
3. Im Hauptmenü `Stream-Aufzeichnungen` öffnen, Laden, Suche, Sortierung und Detailauswahl prüfen.
4. Bei einer unkritischen Aufzeichnung `Zuschauer-Link kopieren` und danach `Video öffnen` testen.
5. In PowerShell `python -m predigt_uploader svp-diagnose` ausführen und die Recording-Zuordnung sowie die gemeldeten Property-Namen prüfen.
