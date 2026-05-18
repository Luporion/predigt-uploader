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
    assert "-m predigt_uploader wizard" in content
