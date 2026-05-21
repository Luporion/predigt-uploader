from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import default_config, default_service_types, load_config
from .filename import build_filename_preview
from .models import AppConfig, SermonInfo


def run_tui(config_path: str | None = None) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.screen import Screen
        from textual.widgets import Button, Footer, Header, Input, Label, Select, Static
    except ImportError as exc:
        raise ImportError("Textual ist nicht installiert.") from exc

    explicit_config = Path(config_path) if config_path else None
    config = load_config(explicit_config) if explicit_config else default_config()

    class StartScreen(Screen[None]):
        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("PredigtUploader", id="title")
            yield Static("Experimentelle Textoberfläche. Der normale Wizard bleibt Standard.")
            yield Button("Neue Predigt vorbereiten", id="new", variant="primary")
            yield Button("Einstellungen", id="settings")
            yield Button("Systemcheck-Hinweis", id="systemcheck")
            yield Button("Beenden", id="quit")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "new":
                self.app.push_screen(MetadataPreviewScreen(config))
            elif event.button.id == "settings":
                self.notify("Einstellungen bleiben vorerst im normalen Wizard.")
            elif event.button.id == "systemcheck":
                self.notify("Bitte PredigtUploader Systemcheck.cmd ausführen.")
            elif event.button.id == "quit":
                self.app.exit()

    class MetadataPreviewScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            service_names = [(service.name, service.name) for service in default_service_types(self.app_config)]
            with Horizontal():
                with Vertical(id="form"):
                    yield Label("Dienstart")
                    yield Select(service_names, value="Predigt", id="service_type")
                    yield Input(value=date.today().isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")
                    yield Input(placeholder="Titel oder Thema", id="title_input")
                    yield Input(placeholder="Bibelstelle", id="bible_input")
                    yield Input(placeholder="Redner oder Leitung", id="speaker_input")
                    yield Button("Zurück", id="back")
                    yield Button("Weiter", id="next", variant="primary")
                with Vertical(id="preview_box"):
                    yield Label("Live-Dateiname")
                    yield Static("", id="filename_preview")
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
                self.notify("Der vollständige Workflow läuft weiterhin im normalen Wizard.")

        def _update_preview(self) -> None:
            preview_widget = self.query_one("#filename_preview", Static)
            sermon_date = _parse_date(self.query_one("#sermon_date", Input).value)
            service_type = str(self.query_one("#service_type", Select).value or "Predigt")
            info = SermonInfo(
                sermon_date=sermon_date,
                title=self.query_one("#title_input", Input).value,
                bible_reference=self.query_one("#bible_input", Input).value,
                speaker=self.query_one("#speaker_input", Input).value,
                sermon_type=service_type,
            )
            preview = build_filename_preview(info, self.app_config)
            preview_widget.update(f"{preview.mp4}\n{preview.mp3}")

    class PredigtUploaderTui(App[None]):
        CSS = """
        Screen {
            padding: 1 2;
        }
        #title {
            text-style: bold;
            margin-bottom: 1;
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
        Input, Select, Button {
            margin-bottom: 1;
        }
        """

        def on_mount(self) -> None:
            self.push_screen(StartScreen())

    PredigtUploaderTui().run()
    return 0


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return date.today()
