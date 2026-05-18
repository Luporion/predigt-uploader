import pytest

from predigt_uploader.ui import MenuOption, UserAbortError, ask_yes_no, choose_from_options


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


def test_ask_yes_no_uses_questionary_when_available(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    monkeypatch.setattr("predigt_uploader.ui._questionary_select", lambda _prompt, _options, _default: True)

    assert ask_yes_no("Weiter?", False, input_func=lambda _prompt: "no") is True


def test_choose_from_options_uses_questionary_when_available(monkeypatch):
    monkeypatch.delenv("PREDIGT_UPLOADER_TEXT_UI", raising=False)
    options = [MenuOption("A", "a"), MenuOption("B", "b")]
    monkeypatch.setattr("predigt_uploader.ui._questionary_select", lambda _prompt, _options, _default: "b")

    assert choose_from_options("Auswahl", options, input_func=lambda _prompt: "1") == "b"


def test_text_fallback_ctrl_c_raises_user_abort(monkeypatch):
    monkeypatch.setenv("PREDIGT_UPLOADER_TEXT_UI", "1")

    def raise_keyboard_interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    with pytest.raises(UserAbortError):
        ask_yes_no("Weiter?", input_func=raise_keyboard_interrupt)
