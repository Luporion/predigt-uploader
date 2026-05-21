import pytest

from predigt_uploader.ui import BACK, MenuOption, UserAbortError, ask_file_path, ask_yes_no, choose_from_options, search_from_options


def test_ask_yes_no_fallback_accepts_words(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")

    assert ask_yes_no("Weiter?", input_func=lambda _prompt: "yes") is True
    assert ask_yes_no("Weiter?", input_func=lambda _prompt: "no") is False


def test_ask_yes_no_fallback_uses_enter_default(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")

    assert ask_yes_no("Weiter?", True, input_func=lambda _prompt: "") is True


def test_choose_from_options_fallback_uses_number(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    options = [MenuOption("A", "a"), MenuOption("B", "b")]

    assert choose_from_options("Auswahl", options, input_func=lambda _prompt: "2") == "b"


def test_choose_from_options_fallback_accepts_alias(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    options = [
        MenuOption("Behalten", "keep", ("b", "behalten")),
        MenuOption("Überschreiben", "overwrite", ("o", "overwrite", "überschreiben")),
    ]

    assert choose_from_options("Auswahl", options, input_func=lambda _prompt: "überschreiben") == "overwrite"


def test_ask_yes_no_uses_questionary_when_available(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    monkeypatch.setattr("predigt_uploader.ui._questionary_select", lambda _prompt, _options, _default: True)

    assert ask_yes_no("Weiter?", False, input_func=lambda _prompt: "no") is True


def test_choose_from_options_uses_questionary_when_available(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    options = [MenuOption("A", "a"), MenuOption("B", "b")]
    monkeypatch.setattr("predigt_uploader.ui._questionary_select", lambda _prompt, _options, _default: "b")

    assert choose_from_options("Auswahl", options, input_func=lambda _prompt: "1") == "b"


def test_search_from_options_uses_questionary_autocomplete_when_available(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    options = [MenuOption("Predigt.mp4", "predigt"), MenuOption("Chor.mp4", "chor")]
    monkeypatch.setattr("predigt_uploader.ui._questionary_autocomplete", lambda _prompt, _options: "predigt")

    assert search_from_options("Suchen", options, input_func=lambda _prompt: "chor") == "predigt"


def test_search_from_options_fallback_filters_then_uses_number(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    options = [MenuOption("Predigt.mp4", "predigt"), MenuOption("Chor.mp4", "chor")]
    inputs = iter(["predigt", "1"])

    assert search_from_options("Suchen", options, input_func=lambda _prompt: next(inputs)) == "predigt"


def test_search_from_options_fallback_empty_search_shows_full_limited_list(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    options = [MenuOption(f"Datei {index}.mp4", index) for index in range(20)]
    inputs = iter(["", "15"])

    assert search_from_options("Suchen", options, input_func=lambda _prompt: next(inputs)) == 14


def test_search_from_options_fallback_accepts_back_alias(monkeypatch, capsys):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    options = [MenuOption("Predigt.mp4", "predigt")]

    assert search_from_options("Suchen", options, input_func=lambda _prompt: "zurück") is BACK
    output = capsys.readouterr().out
    assert "Wähle 'Zurück'" in output


def test_search_from_options_adds_visible_back_option_for_questionary(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    captured = {}

    def fake_autocomplete(prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        return BACK

    monkeypatch.setattr("predigt_uploader.ui._questionary_autocomplete", fake_autocomplete)

    assert search_from_options("Suchen", [MenuOption("Predigt.mp4", "predigt")]) is BACK
    assert "Tippe zum Suchen" in captured["prompt"]
    assert any(option.value is BACK for option in captured["options"])


def test_choose_from_options_questionary_can_return_back_without_text_fallback(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    monkeypatch.setattr("predigt_uploader.ui._questionary_select", lambda _prompt, _options, _default: BACK)

    selected = choose_from_options(
        "Auswahl",
        [MenuOption("Zurück", BACK)],
        input_func=lambda _prompt: pytest.fail("Text-Fallback darf nicht laufen"),
    )

    assert selected is BACK


def test_choose_from_options_fallback_enter_uses_first_option(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    selected = choose_from_options(
        "Auswahl",
        [MenuOption("Standard", "standard"), MenuOption("Andere", "andere")],
        input_func=lambda _prompt: "",
    )

    assert selected == "standard"


def test_text_fallback_ctrl_c_raises_user_abort(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")

    def raise_keyboard_interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    with pytest.raises(UserAbortError):
        ask_yes_no("Weiter?", input_func=raise_keyboard_interrupt)


def test_ask_file_path_selects_single_matching_file_from_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    mp4 = tmp_path / "predigt.mp4"
    mp4.write_bytes(b"video")
    inputs = iter([str(tmp_path), "1"])

    selected = ask_file_path(
        "MP4",
        extensions=(".mp4",),
        file_description="MP4-Dateien",
        input_func=lambda _prompt: next(inputs),
    )

    assert selected == mp4


def test_ask_file_path_requires_choice_for_multiple_matching_files(monkeypatch, tmp_path):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    first = tmp_path / "chor.mp4"
    second = tmp_path / "predigt.mp4"
    first.write_bytes(b"chor")
    second.write_bytes(b"predigt")
    inputs = iter([str(tmp_path), "2"])

    selected = ask_file_path(
        "MP4",
        extensions=(".mp4",),
        file_description="MP4-Dateien",
        input_func=lambda _prompt: next(inputs),
    )

    assert selected in {first, second}
    assert selected.name in {"chor.mp4", "predigt.mp4"}


def test_ask_file_path_retries_folder_without_matching_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    empty = tmp_path / "leer"
    empty.mkdir()
    mp4 = tmp_path / "predigt.mp4"
    mp4.write_bytes(b"video")
    inputs = iter([str(empty), str(mp4)])

    selected = ask_file_path(
        "MP4",
        extensions=(".mp4",),
        file_description="MP4-Dateien",
        input_func=lambda _prompt: next(inputs),
    )

    assert selected == mp4
    assert "keine passenden Dateien" in capsys.readouterr().out


def test_ask_file_path_selects_losslesscut_exe_from_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")
    exe = tmp_path / "LosslessCut.exe"
    exe.write_bytes(b"exe")
    inputs = iter([str(tmp_path), "1"])

    selected = ask_file_path(
        "LosslessCut",
        extensions=(".exe",),
        file_description="EXE-Dateien",
        input_func=lambda _prompt: next(inputs),
    )

    assert selected == exe
