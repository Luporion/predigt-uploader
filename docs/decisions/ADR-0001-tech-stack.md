# ADR-0001: Technologiestack für den Start

## Entscheidung

Der Starter verwendet Python 3.11+ mit Standardbibliothek und CLI-Prototyp.

## Gründe

- schnell entwickelbar
- gut von Codex bearbeitbar
- auf Windows gut nutzbar
- FFmpeg kann einfach extern aufgerufen werden
- GUI kann später ergänzt werden
- Tests sind einfach möglich

## Alternativen

- C#/.NET/WPF: sehr gut für Windows, aber für schnellen KI-Prototyp mehr Projektstruktur
- Electron/Tauri: gute GUI, aber mehr Build-Komplexität
- PowerShell: schnell, aber als dauerhaftes GUI-Tool weniger angenehm

## Konsequenz

Zuerst entsteht ein stabiler CLI-/Logik-Kern. GUI und Installer folgen später.
