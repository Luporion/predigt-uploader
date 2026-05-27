from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .config import default_service_types, load_config
from .filename import build_filename_preview, build_media_filename, service_type_config_for
from .folders import suggest_folder
from .models import AppConfig, ProcessingPlan, SermonInfo, ServiceTypeConfig
from .report import summary_file_path

TUI_MP4_PREVIEW_LIMIT = 5
TUI_FILE_CHOICE_LIMIT = 10
TUI_START_SAFETY_TITLE = "WICHTIGER CHECK VOR DEM START"
TUI_START_SAFETY_QUESTIONS = (
    "Ist die Aufnahme in vMix beendet?",
    "Ist der Stream in vMix beendet?",
)
TUI_START_SAFETY_WARNING = (
    "Wenn der Stream weiterlaeuft, verbraucht der Streaminganbieter weiter Datenvolumen/Kosten."
)
TUI_START_SAFETY_CANCEL_LABEL = "Nein, erst in vMix pruefen"
TUI_START_SAFETY_CONFIRM_LABEL = "Ja, Aufnahme und Stream sind beendet"


@dataclass(frozen=True)
class TuiDateOption:
    label: str
    value: date
    kind: str


@dataclass(frozen=True)
class TuiMp4SelectionConfig:
    mode: str
    start_folder: Path
    title: str
    note: str
    suggest_newest: bool = True
    allow_search: bool = True
    allow_manual_input: bool = True


@dataclass(frozen=True)
class TuiMp4FileRow:
    path: Path
    filename: str
    modified: str
    size: str


@dataclass(frozen=True)
class TuiPreparation:
    source_mp4: Path | None
    raw_recording: Path | None
    already_cut: bool
    info: SermonInfo
    target_folder: Path
    target_mp4: Path
    target_mp3: Path
    summary_path: Path

    @property
    def plan(self) -> ProcessingPlan | None:
        if self.source_mp4 is None:
            return None
        return ProcessingPlan(
            source_mp4=self.source_mp4,
            target_mp4=self.target_mp4,
            target_mp3=self.target_mp3,
            info=self.info,
        )


def load_tui_config(config_path: str | None = None) -> AppConfig:
    explicit_config = Path(config_path) if config_path else None
    return load_config(explicit_config)


GERMAN_MONTHS = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "maerz": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}


def build_tui_preview_text(info: SermonInfo, config: AppConfig) -> str:
    preview = build_filename_preview(info, config)
    target_folder = suggest_folder(config, info)
    summary_path = summary_file_path(target_folder)
    return "\n".join(
        [
            f"Zielordner: {target_folder}",
            f"MP4-Dateiname: {preview.mp4}",
            f"MP3-Dateiname: {preview.mp3}",
            f"Zusammenfassung: {summary_path}",
        ]
    )


def build_tui_preparation(
    *,
    config: AppConfig,
    source_mp4: Path | None,
    raw_recording: Path | None,
    already_cut: bool,
    info: SermonInfo,
) -> TuiPreparation:
    target_folder = suggest_folder(config, info)
    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    return TuiPreparation(
        source_mp4=source_mp4,
        raw_recording=raw_recording,
        already_cut=already_cut,
        info=info,
        target_folder=target_folder,
        target_mp4=target_mp4,
        target_mp3=target_mp3,
        summary_path=summary_file_path(target_folder),
    )


def build_tui_preparation_text(preparation: TuiPreparation) -> str:
    source_text = str(preparation.source_mp4) if preparation.source_mp4 is not None else "noch nicht ausgewaehlt"
    raw_text = str(preparation.raw_recording) if preparation.raw_recording is not None else "-"
    return "\n".join(
        [
            f"Quell-MP4: {source_text}",
            f"Rohaufnahme: {raw_text}",
            f"Zielordner: {preparation.target_folder}",
            f"Finale MP4: {preparation.target_mp4.name}",
            f"Finale MP3: {preparation.target_mp3.name}",
            f"Zusammenfassung: {preparation.summary_path}",
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


def build_tui_start_safety_text() -> str:
    return "\n".join(
        [
            *TUI_START_SAFETY_QUESTIONS,
            "",
            f"[!] {TUI_START_SAFETY_WARNING}",
        ]
    )


def tui_start_safety_route(action_id: str | None) -> str:
    if action_id == "confirm":
        return "source"
    return "start"


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


def tui_cut_mp4_folder(config: AppConfig) -> Path:
    return config.cut_mp4_folder or config.vmix_storage


def build_tui_mp4_selection_config(config: AppConfig, *, mode: str) -> TuiMp4SelectionConfig:
    if mode == "cut":
        return TuiMp4SelectionConfig(
            mode="cut",
            start_folder=tui_cut_mp4_folder(config),
            title="Geschnittene MP4 auswaehlen",
            note="Waehle die bereits geschnittene MP4. Es wird noch nichts kopiert oder verschoben.",
            suggest_newest=True,
            allow_search=True,
            allow_manual_input=True,
        )
    if mode == "raw":
        return TuiMp4SelectionConfig(
            mode="raw",
            start_folder=config.vmix_storage,
            title="Rohaufnahme auswaehlen",
            note="Waehle die Rohaufnahme. Der Schnitt bleibt weiterhin ein bewusster Schritt mit LosslessCut.",
            suggest_newest=True,
            allow_search=True,
            allow_manual_input=True,
        )
    raise ValueError(f"Unbekannter MP4-Auswahlmodus: {mode}")


def build_tui_mp4_selection_actions(selection: TuiMp4SelectionConfig) -> tuple[str, ...]:
    actions: list[str] = []
    if selection.suggest_newest:
        actions.append("newest")
    actions.append("recent")
    if selection.allow_search:
        actions.append("search")
    if selection.allow_manual_input:
        actions.append("manual")
    actions.extend(("back", "cancel"))
    return tuple(actions)


def newest_tui_mp4_candidates(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[Path, ...]:
    if not folder.exists() or not folder.is_dir():
        return ()
    normalized = search_text.strip().casefold()
    files = [path for path in folder.glob("*.mp4") if path.is_file()]
    if normalized:
        files = [path for path in files if normalized in path.name.casefold()]
    return tuple(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:limit])


def newest_tui_mp4_candidate(folder: Path) -> Path | None:
    candidates = newest_tui_mp4_candidates(folder, limit=1)
    if not candidates:
        return None
    return candidates[0]


def build_tui_mp4_file_rows(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[TuiMp4FileRow, ...]:
    return tuple(_build_tui_mp4_file_row(path) for path in newest_tui_mp4_candidates(folder, search_text=search_text, limit=limit))


def _build_tui_mp4_file_row(path: Path) -> TuiMp4FileRow:
    try:
        stat = path.stat()
    except OSError:
        return TuiMp4FileRow(path=path, filename=path.name, modified="unbekannt", size="unbekannt")
    changed = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    size_mb = stat.st_size / (1024 * 1024)
    return TuiMp4FileRow(path=path, filename=path.name, modified=changed, size=f"{size_mb:.1f} MB")


def build_tui_file_choice_lines(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[str, ...]:
    candidates = newest_tui_mp4_candidates(folder, search_text=search_text, limit=limit)
    if not folder.exists():
        return (f"Ordner wurde nicht gefunden: {folder}",)
    if not folder.is_dir():
        return (f"Pfad ist kein Ordner: {folder}",)
    if not candidates:
        return ("Keine passenden MP4-Dateien gefunden.",)
    return tuple(_format_tui_file_line(path) for path in candidates)


def detect_tui_recording_date_from_filename(path: Path) -> date | None:
    match = re.search(r"\b(\d{1,2})\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})\b", path.stem)
    if match is None:
        return None
    day = int(match.group(1))
    month_name = match.group(2).casefold().replace("ä", "ae")
    month = GERMAN_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, day)
    except ValueError:
        return None


def tui_file_modified_date(path: Path) -> date | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError:
        return None


def build_tui_date_options(source_mp4: Path | None, today: date | None = None) -> tuple[TuiDateOption, ...]:
    current = today or date.today()
    options = [TuiDateOption(f"Heutiges Datum: {current.isoformat()}", current, "today")]
    if source_mp4 is not None:
        filename_date = detect_tui_recording_date_from_filename(source_mp4)
        if filename_date is not None:
            options.append(TuiDateOption(f"Aufnahmedatum aus Dateiname: {filename_date.isoformat()}", filename_date, "filename"))
        else:
            modified_date = tui_file_modified_date(source_mp4)
            if modified_date is not None:
                options.append(TuiDateOption(f"Dateidatum der MP4: {modified_date.isoformat()}", modified_date, "filedate"))
    options.append(TuiDateOption("Benutzerdefiniertes Datum", current, "custom"))
    return tuple(options)


def date_from_tui_option(kind: str, options: tuple[TuiDateOption, ...], custom_text: str) -> date:
    if kind == "custom":
        return parse_tui_date_or_today(custom_text)
    for option in options:
        if option.kind == kind:
            return option.value
    return options[0].value


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


def missing_tui_metadata_fields(info: SermonInfo, config: AppConfig, *, date_text: str | None = None) -> tuple[str, ...]:
    fields: list[str] = []
    if date_text is not None and parse_tui_date(date_text) is None:
        fields.append("date")

    service_type = service_type_config_for(config, info.sermon_type)
    if service_type.requires_title and not info.title.strip():
        fields.append("title")
    if service_type.requires_bible_reference and not info.bible_reference.strip():
        fields.append("bible")
    if service_type.requires_speaker and not info.speaker.strip():
        fields.append("speaker")
    return tuple(fields)


def build_tui_validation_text(messages: tuple[str, ...]) -> str:
    if not messages:
        return "Metadaten vollstaendig. Der vollstaendige Workflow laeuft weiterhin im normalen Wizard."
    return "Bitte ergaenzen:\n" + "\n".join(f"- {message}" for message in messages)


def build_tui_field_labels(service_type: ServiceTypeConfig, *, missing_fields: tuple[str, ...] = ()) -> dict[str, str]:
    if service_type.requires_title:
        title_suffix = ""
    elif service_type.optional_title:
        title_suffix = " (optional)"
    else:
        title_suffix = " (nicht nötig)"
    bible_suffix = "" if service_type.requires_bible_reference else " (optional)"
    speaker_suffix = "" if service_type.requires_speaker else " (optional)"
    if not service_type.optional_bible_reference and not service_type.requires_bible_reference:
        bible_suffix = " (nicht nötig)"
    speaker_label = service_type.speaker_label
    if speaker_label.casefold() == "redner":
        speaker_label = "Redner / Leitung"

    def mark_missing(key: str, label: str) -> str:
        if key in missing_fields:
            return f"{label} - FEHLT"
        return label

    return {
        "title": mark_missing("title", f"{service_type.title_label}{title_suffix}"),
        "bible": mark_missing("bible", f"{service_type.bible_reference_label}{bible_suffix}"),
        "speaker": mark_missing("speaker", f"{speaker_label}{speaker_suffix}"),
    }


def run_tui(config_path: str | None = None) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.screen import Screen
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static
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
                self.app.push_screen(StartSafetyScreen(config))
            elif event.button.id == "files":
                self.app.push_screen(FileCandidatesScreen(config))
            elif event.button.id == "settings":
                self.app.push_screen(SettingsScreen(config))
            elif event.button.id == "systemcheck":
                self.notify("Bitte PredigtUploader Systemcheck.cmd ausführen.")
            elif event.button.id == "quit":
                self.app.exit()

    class StartSafetyScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Vertical(id="safety_page"):
                yield Static(TUI_START_SAFETY_TITLE, id="safety_title")
                yield Static("\n".join(TUI_START_SAFETY_QUESTIONS), id="safety_questions")
                yield Static(f"[!] {TUI_START_SAFETY_WARNING}", id="safety_warning")
                with Horizontal(id="safety_actions"):
                    yield Button(TUI_START_SAFETY_CANCEL_LABEL, id="cancel", variant="error")
                    yield Button(TUI_START_SAFETY_CONFIRM_LABEL, id="confirm", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#cancel", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            route = tui_start_safety_route(event.button.id)
            if route == "source":
                self.app.push_screen(SourceChoiceScreen(self.app_config))
            else:
                self.app.pop_screen()

    class SourceChoiceScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Neue Aufnahme vorbereiten", id="screen_title")
            yield Static(
                "Textual sammelt Quelle und Metadaten. Die Verarbeitung laeuft weiterhin im normalen Wizard.",
                id="screen_note",
            )
            yield Button("Ja, fertig geschnittene MP4 auswaehlen", id="cut", variant="primary")
            yield Button("Nein, Rohaufnahme auswaehlen", id="raw")
            yield Button("Abbrechen", id="cancel")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cut":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=True))
            elif event.button.id == "raw":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=False))
            elif event.button.id == "cancel":
                self.app.pop_screen()

    class FileSelectionScreen(Screen[None]):
        def __init__(self, app_config: AppConfig, *, already_cut: bool) -> None:
            super().__init__()
            self.app_config = app_config
            self.already_cut = already_cut
            mode = "cut" if already_cut else "raw"
            self.selection = build_tui_mp4_selection_config(app_config, mode=mode)
            self.current_folder = self.selection.start_folder
            self._visible_candidates: tuple[Path, ...] = ()

        @property
        def source_folder(self) -> Path:
            return self.current_folder

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(self.selection.title, id="screen_title")
            yield Static(self.selection.note, id="screen_note")
            yield Static(f"Ordner: {self.source_folder}", id="source_folder")
            with Horizontal(id="file_actions"):
                if self.selection.suggest_newest:
                    newest_label = "Neueste geschnittene MP4 verwenden" if self.already_cut else "Neueste Aufnahme verwenden"
                    yield Button(newest_label, id="newest", variant="primary")
                yield Button("Ausgewaehlte Datei verwenden", id="select")
                yield Button("Zurueck", id="back")
                yield Button("Abbrechen", id="cancel")
            if self.selection.allow_search:
                yield Input(placeholder="Dateiname suchen oder filtern", id="file_search")
            yield Static("Neueste MP4-Dateien", id="file_table_heading")
            yield DataTable(id="file_table")
            if self.selection.allow_manual_input:
                yield Input(placeholder="Datei oder Ordner manuell eingeben", id="manual_path")
                yield Button("Manuellen Pfad verwenden", id="manual")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#file_table", DataTable)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("Dateiname", "Geaendert", "Groesse")
            self._update_file_table()
            table.focus()

        def on_input_changed(self, _event: Input.Changed) -> None:
            self._update_file_table()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self._choose_file_by_row_key(event.row_key.value)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self.app.pop_screen()
                self.app.pop_screen()
                return
            if event.button.id == "newest":
                selected = newest_tui_mp4_candidate(self.source_folder)
                if selected is None:
                    self.notify("Keine MP4-Datei im aktuellen Ordner gefunden.")
                    return
                self._open_metadata(selected)
                return
            if event.button.id == "select":
                table = self.query_one("#file_table", DataTable)
                if not self._visible_candidates or table.cursor_row >= len(self._visible_candidates):
                    self.notify("Bitte zuerst eine MP4-Datei in der Liste auswaehlen.")
                    return
                self._open_metadata(self._visible_candidates[table.cursor_row])
                return
            if event.button.id == "manual":
                self._use_manual_path()

        def _candidates(self) -> tuple[Path, ...]:
            return newest_tui_mp4_candidates(
                self.source_folder,
                search_text=self._search_text(),
                limit=TUI_FILE_CHOICE_LIMIT,
            )

        def _search_text(self) -> str:
            if not self.selection.allow_search:
                return ""
            return self.query_one("#file_search", Input).value

        def _update_file_table(self) -> None:
            table = self.query_one("#file_table", DataTable)
            rows = build_tui_mp4_file_rows(self.source_folder, search_text=self._search_text(), limit=TUI_FILE_CHOICE_LIMIT)
            self._visible_candidates = tuple(row.path for row in rows)
            table.clear()
            for index, row in enumerate(rows):
                table.add_row(row.filename, row.modified, row.size, key=str(index))
            self.query_one("#source_folder", Static).update(f"Ordner: {self.source_folder}")

        def _choose_file_by_row_key(self, row_key: object) -> None:
            try:
                index = int(str(row_key))
            except ValueError:
                return
            if index < len(self._visible_candidates):
                self._open_metadata(self._visible_candidates[index])

        def _use_manual_path(self) -> None:
            path_text = self.query_one("#manual_path", Input).value.strip()
            if not path_text:
                self.notify("Bitte eine MP4-Datei oder einen Ordner eingeben.")
                return
            path = Path(path_text).expanduser()
            if path.is_file() and path.suffix.casefold() == ".mp4":
                self._open_metadata(path)
                return
            if path.is_dir():
                self.current_folder = path
                self._update_file_table()
                self.notify("Ordner wurde fuer diese Auswahl uebernommen.")
                return
            self.notify("Der eingegebene Pfad ist keine MP4-Datei und kein vorhandener Ordner.")

        def _open_metadata(self, selected: Path) -> None:
            raw_recording = None if self.already_cut else selected
            self.app.push_screen(
                MetadataPreviewScreen(
                    self.app_config,
                    source_mp4=selected,
                    raw_recording=raw_recording,
                    already_cut=self.already_cut,
                )
            )

    class MetadataPreviewScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            *,
            source_mp4: Path | None = None,
            raw_recording: Path | None = None,
            already_cut: bool = True,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.source_mp4 = source_mp4
            self.raw_recording = raw_recording
            self.already_cut = already_cut

        def compose(self) -> ComposeResult:
            today = date.today()
            date_options = build_tui_date_options(self.source_mp4, today)
            service_names = [(service.name, service.name) for service in service_types_for_tui(self.app_config)]
            default_service = default_tui_service_type_name(self.app_config, date_options[0].value)
            yield Static("Metadaten erfassen", id="screen_title")
            yield Static(
                "Experiment: Diese Oberfläche speichert noch nichts und ersetzt den normalen Wizard nicht.",
                id="screen_note",
            )
            with Horizontal():
                with Vertical(id="form"):
                    yield Label("Dienstart")
                    yield Select(service_names, value=default_service, id="service_type")
                    yield Label("Datum", id="date_label")
                    yield Select([(option.label, option.kind) for option in date_options], value=date_options[0].kind, id="date_choice")
                    yield Input(value=date_options[0].value.isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")
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
                    yield Button("Zurueck", id="back")
                    yield Button("Abbrechen", id="cancel")
                    yield Button("Metadaten pruefen", id="next", variant="primary")
                with Vertical(id="preview_box"):
                    yield Label("Live-Vorschau", id="preview_heading")
                    yield Static("", id="filename_preview")
                    yield Static("", id="validation_status")
                    yield Static("", id="source_status")
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
            elif event.button.id == "cancel":
                self._return_to_start()
            elif event.button.id == "next":
                messages = self._validation_messages()
                if messages:
                    self.notify("Bitte fehlende Pflichtfelder ergaenzen.")
                else:
                    self.notify("Metadaten sind vollstaendig. Bitte den normalen Wizard fuer die Verarbeitung nutzen.")

        def _update_preview(self) -> None:
            preview_widget = self.query_one("#filename_preview", Static)
            validation_widget = self.query_one("#validation_status", Static)
            source_widget = self.query_one("#source_status", Static)
            service_type = str(self.query_one("#service_type", Select).value or default_tui_service_type_name(self.app_config, date.today()))
            service_config = service_type_by_name(self.app_config, service_type)
            info = self._current_info()
            date_text = self._validation_date_text()
            messages = validate_tui_metadata(info, self.app_config, date_text=date_text)
            missing_fields = missing_tui_metadata_fields(info, self.app_config, date_text=date_text)
            self._update_field_state(service_config, missing_fields)
            preparation = build_tui_preparation(
                config=self.app_config,
                source_mp4=self.source_mp4,
                raw_recording=self.raw_recording,
                already_cut=self.already_cut,
                info=info,
            )
            preview_widget.update(build_tui_preparation_text(preparation))
            validation_widget.update(build_tui_validation_text(messages))
            source_widget.update(self._source_hint())
            self.query_one("#next", Button).disabled = bool(messages)

        def _validation_messages(self, info: SermonInfo | None = None) -> tuple[str, ...]:
            date_text = self._validation_date_text()
            if info is None:
                info = self._current_info()
            return validate_tui_metadata(info, self.app_config, date_text=date_text)

        def _current_info(self) -> SermonInfo:
            service_type = str(self.query_one("#service_type", Select).value or default_tui_service_type_name(self.app_config, date.today()))
            return build_tui_metadata_info(
                config=self.app_config,
                date_text=self._selected_date().isoformat(),
                service_type_name=service_type,
                title=self.query_one("#title_input", Input).value,
                bible_reference=self.query_one("#bible_input", Input).value,
                speaker=self.query_one("#speaker_input", Input).value,
                folder_note=self.query_one("#folder_note_input", Input).value,
            )

        def _selected_date(self) -> date:
            options = build_tui_date_options(self.source_mp4)
            kind = str(self.query_one("#date_choice", Select).value or "today")
            return date_from_tui_option(kind, options, self.query_one("#sermon_date", Input).value)

        def _validation_date_text(self) -> str:
            kind = str(self.query_one("#date_choice", Select).value or "today")
            if kind == "custom":
                return self.query_one("#sermon_date", Input).value
            return self._selected_date().isoformat()

        def _source_hint(self) -> str:
            if self.source_mp4 is None:
                return "Quelle: noch nicht ausgewaehlt"
            if self.already_cut:
                return f"Quelle: geschnittene MP4\n{self.source_mp4}"
            return "Quelle: Rohaufnahme\nBitte den Schnitt weiterhin bewusst mit LosslessCut/normalem Wizard abschliessen."

        def _update_field_state(self, service_type: ServiceTypeConfig, missing_fields: tuple[str, ...]) -> None:
            labels = build_tui_field_labels(service_type, missing_fields=missing_fields)
            date_label = "Datum - FEHLT" if "date" in missing_fields else "Datum"
            self.query_one("#date_label", Label).update(date_label)
            self.query_one("#title_label", Label).update(labels["title"])
            self.query_one("#bible_label", Label).update(labels["bible"])
            self.query_one("#speaker_label", Label).update(labels["speaker"])
            self.query_one("#title_input", Input).disabled = not service_type.requires_title and not service_type.optional_title
            self.query_one("#bible_input", Input).disabled = (
                not service_type.requires_bible_reference and not service_type.optional_bible_reference
            )
            self.query_one("#speaker_input", Input).disabled = (
                not service_type.requires_speaker and not service_type.optional_speaker
            )

        def _return_to_start(self) -> None:
            for _ in range(3):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

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
        #safety_page {
            align: center middle;
            height: 1fr;
        }
        #safety_title {
            text-style: bold;
            text-align: center;
            width: 100%;
            border: heavy $error;
            padding: 1 2;
            margin-bottom: 1;
        }
        #safety_questions {
            text-style: bold;
            text-align: center;
            width: 100%;
            border: solid $warning;
            padding: 1 2;
            margin-bottom: 1;
        }
        #safety_warning {
            text-align: center;
            width: 100%;
            border: heavy $warning;
            padding: 1 2;
            margin-bottom: 2;
        }
        #safety_actions {
            align-horizontal: center;
            height: auto;
        }
        #safety_actions Button {
            width: 34;
            margin: 0 1 1 1;
        }
        #file_actions {
            height: auto;
            margin-bottom: 1;
        }
        #file_table {
            height: 12;
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
