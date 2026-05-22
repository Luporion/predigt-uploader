from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .config import default_service_types, load_config
from .filename import build_filename_preview, service_type_config_for
from .folders import suggest_folder
from .models import AppConfig, SermonInfo, ServiceTypeConfig

TUI_MP4_PREVIEW_LIMIT = 5


def load_tui_config(config_path: str | None = None) -> AppConfig:
    explicit_config = Path(config_path) if config_path else None
    return load_config(explicit_config)


def build_tui_preview_text(info: SermonInfo, config: AppConfig) -> str:
    preview = build_filename_preview(info, config)
    target_folder = suggest_folder(config, info)
    return "\n".join(
        [
            f"Zielordner: {target_folder}",
            f"MP4-Dateiname: {preview.mp4}",
            f"MP3-Dateiname: {preview.mp3}",
        ]
    )


def build_tui_start_status_text(config: AppConfig) -> str:
    return "\n".join(
        [
            "Experimentelle Oberfläche",
            "Produktiver Workflow: normaler Wizard",
            f"Ziel-Basisordner: {config.recordings_base}",
            f"Rohaufnahme-Ordner: {config.vmix_storage}",
        ]
    )


def build_tui_file_candidates_lines(config: AppConfig, *, limit: int = TUI_MP4_PREVIEW_LIMIT) -> tuple[str, ...]:
    lines: list[str] = ["MP4-Dateien zur Orientierung"]
    if config.cut_mp4_folder is None:
        lines.append("Schnitt-/Exportordner: noch nicht gemerkt")
    else:
        lines.extend(_build_tui_folder_file_lines("Schnitt-/Exportordner", config.cut_mp4_folder, limit=limit))
    lines.append("")
    lines.extend(_build_tui_folder_file_lines("Rohaufnahme-Ordner", config.vmix_storage, limit=limit))
    return tuple(lines)


def _build_tui_folder_file_lines(label: str, folder: Path, *, limit: int) -> tuple[str, ...]:
    lines = [f"{label}: {folder}"]
    if not folder.exists():
        return tuple(lines + ["Ordner wurde nicht gefunden."])
    if not folder.is_dir():
        return tuple(lines + ["Pfad ist kein Ordner."])

    files = _newest_mp4_files(folder, limit=limit)
    if not files:
        return tuple(lines + ["Keine MP4-Dateien gefunden."])
    lines.extend(_format_tui_file_line(path) for path in files)
    return tuple(lines)


def _newest_mp4_files(folder: Path, *, limit: int) -> tuple[Path, ...]:
    files = [path for path in folder.glob("*.mp4") if path.is_file()]
    return tuple(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:limit])


def _format_tui_file_line(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return f"- {path.name}"
    changed = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    size_mb = stat.st_size / (1024 * 1024)
    return f"- {path.name} | geaendert: {changed} | Groesse: {size_mb:.1f} MB"


def build_tui_settings_lines(config: AppConfig) -> tuple[str, ...]:
    losslesscut = config.losslesscut_path or "PATH / Windows-App-Alias"
    return (
        f"Ziel-Basisordner: {config.recordings_base}",
        f"Rohaufnahme-Ordner: {config.vmix_storage}",
        f"LosslessCut-Pfad: {losslesscut}",
        f"Jahresordner-Format: {config.year_folder_template}",
        f"Rohaufnahme-Aufräumen: {config.raw_archive_mode}",
    )


def service_types_for_tui(config: AppConfig) -> tuple[ServiceTypeConfig, ...]:
    return default_service_types(config) + config.custom_service_types


def service_type_by_name(config: AppConfig, name: str) -> ServiceTypeConfig:
    normalized = name.casefold()
    for service_type in service_types_for_tui(config):
        if service_type.name.casefold() == normalized:
            return service_type
    return service_types_for_tui(config)[0]


def default_tui_service_type_name(config: AppConfig, sermon_date: date) -> str:
    weekday_defaults = {
        2: "Bibelstunde",
        4: "Gebetsstunde",
        6: "Predigt",
    }
    preferred = weekday_defaults.get(sermon_date.weekday(), "Predigt")
    for service_type in service_types_for_tui(config):
        if service_type.name.casefold() == preferred.casefold():
            return service_type.name
    return service_types_for_tui(config)[0].name


def parse_tui_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse_tui_date_or_today(value: str) -> date:
    parsed = parse_tui_date(value)
    if parsed is None:
        return date.today()
    return parsed


def build_tui_metadata_info(
    *,
    config: AppConfig,
    date_text: str,
    service_type_name: str,
    title: str,
    bible_reference: str,
    speaker: str,
    folder_note: str,
) -> SermonInfo:
    return SermonInfo(
        sermon_date=parse_tui_date_or_today(date_text),
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        sermon_type=service_type_by_name(config, service_type_name).name,
        folder_note=folder_note,
    )


def validate_tui_metadata(info: SermonInfo, config: AppConfig, *, date_text: str | None = None) -> tuple[str, ...]:
    messages: list[str] = []
    if date_text is not None and parse_tui_date(date_text) is None:
        messages.append("Datum bitte im Format YYYY-MM-DD eingeben.")

    service_type = service_type_config_for(config, info.sermon_type)
    if service_type.requires_title and not info.title.strip():
        messages.append(f"{service_type.title_label} fehlt.")
    if service_type.requires_bible_reference and not info.bible_reference.strip():
        messages.append(f"{service_type.bible_reference_label} fehlt.")
    if service_type.requires_speaker and not info.speaker.strip():
        messages.append(f"{service_type.speaker_label} fehlt.")
    return tuple(messages)


def build_tui_validation_text(messages: tuple[str, ...]) -> str:
    if not messages:
        return "Metadaten vollstaendig. Der vollstaendige Workflow laeuft weiterhin im normalen Wizard."
    return "Bitte pruefen:\n" + "\n".join(f"- {message}" for message in messages)


def build_tui_field_labels(service_type: ServiceTypeConfig) -> dict[str, str]:
    title_suffix = "" if service_type.requires_title else " (nicht nötig)"
    bible_suffix = "" if service_type.requires_bible_reference else " (optional)"
    speaker_suffix = "" if service_type.requires_speaker else " (optional)"
    if not service_type.optional_bible_reference and not service_type.requires_bible_reference:
        bible_suffix = " (nicht nötig)"
    speaker_label = service_type.speaker_label
    if speaker_label.casefold() == "redner":
        speaker_label = "Redner / Leitung"
    return {
        "title": f"{service_type.title_label}{title_suffix}",
        "bible": f"{service_type.bible_reference_label}{bible_suffix}",
        "speaker": f"{speaker_label}{speaker_suffix}",
    }


def run_tui(config_path: str | None = None) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.screen import Screen
        from textual.widgets import Button, Footer, Header, Input, Label, Select, Static
    except ImportError as exc:
        raise ImportError("Textual ist nicht installiert.") from exc

    config = load_tui_config(config_path)

    class StartScreen(Screen[None]):
        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("PredigtUploader", id="title")
            with Horizontal():
                with Vertical(id="start_actions"):
                    yield Button("Neue Aufnahme vorbereiten", id="new", variant="primary")
                    yield Button("MP4-Dateien ansehen", id="files")
                    yield Button("Einstellungen", id="settings")
                    yield Button("Systemcheck-Hinweis", id="systemcheck")
                    yield Button("Beenden", id="quit")
                with Vertical(id="status_box"):
                    yield Static(build_tui_start_status_text(config), id="start_status")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "new":
                self.app.push_screen(MetadataPreviewScreen(config))
            elif event.button.id == "files":
                self.app.push_screen(FileCandidatesScreen(config))
            elif event.button.id == "settings":
                self.app.push_screen(SettingsScreen(config))
            elif event.button.id == "systemcheck":
                self.notify("Bitte PredigtUploader Systemcheck.cmd ausführen.")
            elif event.button.id == "quit":
                self.app.exit()

    class MetadataPreviewScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            today = date.today()
            service_names = [(service.name, service.name) for service in service_types_for_tui(self.app_config)]
            default_service = default_tui_service_type_name(self.app_config, today)
            yield Static("Metadaten erfassen", id="screen_title")
            yield Static(
                "Experiment: Diese Oberfläche speichert noch nichts und ersetzt den normalen Wizard nicht.",
                id="screen_note",
            )
            with Horizontal():
                with Vertical(id="form"):
                    yield Label("Dienstart")
                    yield Select(service_names, value=default_service, id="service_type")
                    yield Label("Datum")
                    yield Input(value=today.isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")
                    yield Label("Titel", id="title_label")
                    yield Input(placeholder="Titel oder Thema", id="title_input")
                    yield Label("Hauptbibelstelle", id="bible_label")
                    yield Input(placeholder="Bibelstelle", id="bible_input")
                    yield Label("Redner / Leitung", id="speaker_label")
                    yield Input(placeholder="Redner oder Leitung", id="speaker_input")
                    yield Label("Besonderheit im Ordner")
                    yield Input(placeholder="optional, z. B. Taufe oder Gastredner", id="folder_note_input")
                    yield Static(
                        "Der vollständige Workflow läuft weiterhin im normalen Wizard.",
                        id="workflow_note",
                    )
                    yield Button("Zurück", id="back")
                    yield Button("Metadaten pruefen", id="next", variant="primary")
                with Vertical(id="preview_box"):
                    yield Label("Live-Vorschau", id="preview_heading")
                    yield Static("", id="filename_preview")
                    yield Static("", id="validation_status")
            yield Footer()

        def on_mount(self) -> None:
            self._update_preview()

        def on_input_changed(self, _event: Input.Changed) -> None:
            self._update_preview()

        def on_select_changed(self, _event: Select.Changed) -> None:
            self._update_preview()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
            elif event.button.id == "next":
                messages = self._validation_messages()
                if messages:
                    self.notify("Bitte fehlende Pflichtfelder ergaenzen.")
                else:
                    self.notify("Metadaten sind vollstaendig. Bitte den normalen Wizard fuer die Verarbeitung nutzen.")

        def _update_preview(self) -> None:
            preview_widget = self.query_one("#filename_preview", Static)
            validation_widget = self.query_one("#validation_status", Static)
            service_type = str(self.query_one("#service_type", Select).value or default_tui_service_type_name(self.app_config, date.today()))
            service_config = service_type_by_name(self.app_config, service_type)
            self._update_field_state(service_config)
            info = build_tui_metadata_info(
                config=self.app_config,
                date_text=self.query_one("#sermon_date", Input).value,
                service_type_name=service_type,
                title=self.query_one("#title_input", Input).value,
                bible_reference=self.query_one("#bible_input", Input).value,
                speaker=self.query_one("#speaker_input", Input).value,
                folder_note=self.query_one("#folder_note_input", Input).value,
            )
            preview_widget.update(build_tui_preview_text(info, self.app_config))
            validation_widget.update(build_tui_validation_text(self._validation_messages(info)))

        def _validation_messages(self, info: SermonInfo | None = None) -> tuple[str, ...]:
            date_text = self.query_one("#sermon_date", Input).value
            if info is None:
                service_type = str(self.query_one("#service_type", Select).value or default_tui_service_type_name(self.app_config, date.today()))
                info = build_tui_metadata_info(
                    config=self.app_config,
                    date_text=date_text,
                    service_type_name=service_type,
                    title=self.query_one("#title_input", Input).value,
                    bible_reference=self.query_one("#bible_input", Input).value,
                    speaker=self.query_one("#speaker_input", Input).value,
                    folder_note=self.query_one("#folder_note_input", Input).value,
                )
            return validate_tui_metadata(info, self.app_config, date_text=date_text)

        def _update_field_state(self, service_type: ServiceTypeConfig) -> None:
            labels = build_tui_field_labels(service_type)
            self.query_one("#title_label", Label).update(labels["title"])
            self.query_one("#bible_label", Label).update(labels["bible"])
            self.query_one("#speaker_label", Label).update(labels["speaker"])
            self.query_one("#title_input", Input).disabled = not service_type.requires_title
            self.query_one("#bible_input", Input).disabled = (
                not service_type.requires_bible_reference and not service_type.optional_bible_reference
            )
            self.query_one("#speaker_input", Input).disabled = (
                not service_type.requires_speaker and not service_type.optional_speaker
            )

    class FileCandidatesScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("MP4-Dateien", id="screen_title")
            yield Static(
                "Nur Anzeige im Prototyp. Die Auswahl und Verarbeitung laufen weiterhin im normalen Wizard.",
                id="screen_note",
            )
            for line in build_tui_file_candidates_lines(self.app_config):
                yield Static(line)
            yield Button("Zurück", id="back")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()

    class SettingsScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Einstellungen", id="screen_title")
            yield Static(
                "Nur Anzeige im Prototyp. Ändern bitte weiterhin über den normalen Wizard.",
                id="screen_note",
            )
            for line in build_tui_settings_lines(self.app_config):
                yield Static(line)
            yield Button("Zurück", id="back")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()

    class PredigtUploaderTui(App[None]):
        CSS = """
        Screen {
            padding: 1 2;
        }
        #title {
            text-style: bold;
            margin-bottom: 1;
        }
        #screen_title {
            text-style: bold;
            margin-bottom: 1;
        }
        #screen_note {
            margin-bottom: 1;
        }
        #start_actions {
            width: 1fr;
            padding-right: 2;
        }
        #status_box {
            width: 1fr;
            border: solid $accent;
            padding: 1;
        }
        #form {
            width: 1fr;
            padding-right: 2;
        }
        #preview_box {
            width: 1fr;
            border: solid $accent;
            padding: 1;
        }
        #preview_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #workflow_note {
            border: solid $accent;
            padding: 1;
            margin-bottom: 1;
        }
        Input, Select, Button {
            margin-bottom: 1;
        }
        """

        def on_mount(self) -> None:
            self.push_screen(StartScreen())

    PredigtUploaderTui().run()
    return 0


def _parse_date(value: str) -> date:
    return parse_tui_date_or_today(value)
