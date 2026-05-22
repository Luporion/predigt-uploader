import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_manual_test_guide_documents_phase_1_usage() -> None:
    guide = PROJECT_ROOT / "docs" / "manual-test-v1.md"

    content = guide.read_text(encoding="utf-8")

    assert "Voraussetzungen" in content
    assert "FFmpeg" in content
    assert "config.toml" in content
    assert "Wizard starten" in content
    assert "logs/" in content
    assert "Vimeo" in content
    assert "WordPress" in content


def test_run_wizard_script_checks_venv_and_starts_cli_wizard() -> None:
    script = PROJECT_ROOT / "scripts" / "run-wizard.ps1"

    content = script.read_text(encoding="utf-8")

    assert ".venv" in content
    assert "python.exe" in content
    assert "Die virtuelle Python-Umgebung .venv wurde nicht gefunden." in content
    assert "Python wurde auf diesem Rechner nicht gefunden." in content
    assert "[Console]::OutputEncoding" in content
    assert "-m predigt_uploader @args" in content


def test_pytest_config_does_not_pin_machine_local_temp_paths() -> None:
    config = PROJECT_ROOT / "pyproject.toml"

    content = config.read_text(encoding="utf-8")

    assert 'addopts = "-q"' in content
    assert "--basetemp=.pytest-tmp" not in content
    assert "--basetemp=.pytest-tmp/run" not in content
    assert 'cache_dir = ".pytest-tmp/cache"' not in content


def test_test_script_uses_portable_temp_and_cache_folders() -> None:
    script = PROJECT_ROOT / "scripts" / "test.ps1"

    content = script.read_text(encoding="utf-8")

    assert script.exists()
    assert "[Console]::OutputEncoding" in content
    assert "$env:LOCALAPPDATA" in content
    assert "PredigtUploader\\pytest" in content
    assert "$env:TEMP" in content
    assert "PredigtUploader-pytest" in content
    assert "--basetemp" in content
    assert "cache_dir=" in content
    assert "-m pytest" in content


def test_local_setup_script_prepares_venv_and_installs_package() -> None:
    script = PROJECT_ROOT / "scripts" / "setup-local.ps1"

    content = script.read_text(encoding="utf-8")

    assert "Python 3.11 oder neuer wurde nicht gefunden." in content
    assert "-m venv" in content
    assert ".venv" in content
    assert "-m pip install -e" in content
    assert "Einrichtung abgeschlossen." in content
    assert "Abhaengigkeiten" in content
    assert "FFmpeg wurde nicht gefunden." in content
    assert "winget install --id Gyan.FFmpeg -e" in content
    assert "neues PowerShell-Fenster" in content
    assert "[Console]::OutputEncoding" in content


def test_system_check_script_checks_wizard_ffmpeg_and_losslesscut() -> None:
    script = PROJECT_ROOT / "scripts" / "check-system.ps1"

    content = script.read_text(encoding="utf-8")

    assert "PredigtUploader Systempruefung" in content
    assert "-m predigt_uploader --help" in content
    assert "ffmpeg_available" in content
    assert "losslesscut_path" in content
    assert "FFmpeg wurde nicht gefunden" in content
    assert "verfuegbar" in content
    assert "[Console]::OutputEncoding" in content


def test_windows_starter_scripts_avoid_umlauts_in_console_text() -> None:
    script_paths = [
        PROJECT_ROOT / "scripts" / "setup-local.ps1",
        PROJECT_ROOT / "scripts" / "check-system.ps1",
        PROJECT_ROOT / "scripts" / "run-wizard.ps1",
        PROJECT_ROOT / "PredigtUploader starten.cmd",
        PROJECT_ROOT / "PredigtUploader einrichten.cmd",
        PROJECT_ROOT / "PredigtUploader Systemcheck.cmd",
        PROJECT_ROOT / "Tests ausführen.cmd",
    ]

    for path in script_paths:
        content = path.read_text(encoding="utf-8")
        assert not any(char in content for char in "äöüÄÖÜß")


def test_install_v1_5_guide_documents_target_machine_setup() -> None:
    guide = PROJECT_ROOT / "docs" / "install-v1-5.md"

    content = guide.read_text(encoding="utf-8")

    assert "Installation auf" in content or "Installation: lokale Version 1.5" in content
    assert "setup-local.ps1" in content
    assert "check-system.ps1" in content
    assert "FFmpeg" in content
    assert "LosslessCut" in content
    assert "config.toml" in content
    assert "losslesscut_path" in content
    assert "run-wizard.ps1" in content
    assert "Vimeo" in content
    assert "WordPress" in content


def test_clickable_cmd_launchers_exist_and_call_expected_scripts() -> None:
    launchers = {
        "PredigtUploader starten.cmd": "scripts\\run-wizard.ps1",
        "PredigtUploader einrichten.cmd": "scripts\\setup-local.ps1",
        "PredigtUploader Systemcheck.cmd": "scripts\\check-system.ps1",
        "Tests ausführen.cmd": "scripts\\test.ps1",
    }

    for filename, expected_script in launchers.items():
        launcher = PROJECT_ROOT / filename
        content = launcher.read_text(encoding="utf-8")

        assert launcher.exists()
        assert "chcp 65001 >nul" in content
        assert 'cd /d "%~dp0"' in content
        assert "powershell.exe -NoProfile -ExecutionPolicy Bypass -File" in content
        assert expected_script in content
        assert "pause >nul" in content
        assert "Druecke eine Taste" in content


def test_install_v1_5_guide_documents_clickable_cmd_files() -> None:
    guide = PROJECT_ROOT / "docs" / "install-v1-5.md"

    content = guide.read_text(encoding="utf-8")

    assert "PredigtUploader einrichten.cmd" in content
    assert "PredigtUploader Systemcheck.cmd" in content
    assert "PredigtUploader starten.cmd" in content
    assert "Doppelklick" in content
    assert "Desktop" in content
    assert "Verknüpfung" in content


def test_release_zip_script_documents_included_and_excluded_paths() -> None:
    script = PROJECT_ROOT / "scripts" / "make-release-zip.ps1"

    content = script.read_text(encoding="utf-8")

    release_name = re.search(r'\$ReleaseName\s*=\s*"([^"]+)"', content)
    assert release_name is not None
    assert release_name.group(1).startswith("predigt-uploader-v$Version-")
    assert release_name.group(1).endswith("textual-preview")
    assert "dist" in content
    assert "Compress-Archive" in content
    assert '"src"' in content
    assert '"scripts"' in content
    assert '"docs\\install-v1-5.md"' in content
    assert '"docs\\manual-test-v1-5.md"' in content
    assert '"README.md"' in content
    assert '"pyproject.toml"' in content
    assert '"config.example.toml"' in content
    assert '"PredigtUploader starten.cmd"' in content
    assert '"PredigtUploader einrichten.cmd"' in content
    assert '"PredigtUploader Systemcheck.cmd"' in content
    assert '"Tests ausführen.cmd"' in content
    assert '".git"' in content
    assert '".venv"' in content
    assert '"logs"' in content
    assert '"dist"' in content
    assert '"build"' in content
    assert '"__pycache__"' in content
    assert '".pytest_cache"' in content
    assert '".pytest-tmp"' in content
    assert '"test-extract"' in content
    assert '"Windows PowerShell.txt"' in content
    assert '"config.toml"' in content
    assert '"*.egg-info"' in content
    assert '"*.pyc"' in content
    assert "ExcludedPatterns" in content


def test_release_v1_5_guide_documents_zip_contents_and_target_setup() -> None:
    guide = PROJECT_ROOT / "docs" / "release-v1-5.md"

    content = guide.read_text(encoding="utf-8")

    assert "predigt-uploader-v0.1.6-local.zip" in content
    assert "src/" in content
    assert "scripts/" in content
    assert "docs/install-v1-5.md" in content
    assert "docs/manual-test-v1-5.md" in content
    assert "README.md" in content
    assert "pyproject.toml" in content
    assert "config.example.toml" in content
    assert "PredigtUploader starten.cmd" in content
    assert ".git/" in content
    assert ".venv/" in content
    assert "logs/" in content
    assert "dist/" in content
    assert "build/" in content
    assert "*.egg-info/" in content
    assert "src/predigt_uploader.egg-info/" in content
    assert "*.pyc" in content
    assert "config.toml" in content
    assert "Gemeinderechner" in content
    assert "Doppelklick" in content
