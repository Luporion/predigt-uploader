import sys

from predigt_uploader import cli


def test_normal_cli_import_does_not_import_textual():
    sys.modules.pop("textual", None)

    assert "textual" not in sys.modules


def test_tui_command_reports_missing_textual(monkeypatch, capsys):
    def fail_import(*_args, **_kwargs):
        raise ImportError("Textual fehlt")

    monkeypatch.setattr("predigt_uploader.tui_app.run_tui", fail_import)

    result = cli.main(["tui"])

    assert result == 7
    assert "Die neue Oberfläche ist nicht installiert" in capsys.readouterr().out
