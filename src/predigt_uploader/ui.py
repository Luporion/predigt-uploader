from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")

InputFunc = Callable[[str], str]


@dataclass(frozen=True)
class MenuOption[T]:
    label: str
    value: T


YES_VALUES = {"j", "ja", "y", "yes"}
NO_VALUES = {"n", "nein", "no"}
TEXT_UI_ENV = "PREDIGT_UPLOADER_TEXT_UI"


class UserAbortError(RuntimeError):
    pass


def _force_text_ui() -> bool:
    return os.environ.get(TEXT_UI_ENV, "").strip().casefold() in {"1", "true", "ja", "yes", "on"}


def _can_try_questionary() -> bool:
    return not _force_text_ui() and sys.stdin.isatty() and sys.stdout.isatty()


def _questionary_select(prompt: str, options: Sequence[MenuOption[T]], default_index: int) -> T | None:
    if not _can_try_questionary():
        return None
    try:
        import questionary
    except ImportError:
        return None

    try:
        labels = [option.label for option in options]
        selected = questionary.select(
            prompt,
            choices=labels,
            default=labels[default_index],
            use_shortcuts=True,
        ).ask()
    except (KeyboardInterrupt, EOFError) as exc:
        raise UserAbortError("Abbruch durch Nutzer.") from exc
    except Exception:
        return None

    if selected is None:
        raise UserAbortError("Abbruch durch Nutzer.")
    for option in options:
        if option.label == selected:
            print(f"{prompt}: {option.label}")
            return option.value
    return None


def ask_yes_no(prompt: str, default: bool = False, *, input_func: InputFunc | None = None) -> bool:
    if input_func is None:
        input_func = input
    default_label = "Ja" if default else "Nein"
    options = [MenuOption("Ja", True), MenuOption("Nein", False)]
    default_index = 0 if default else 1
    selected = _questionary_select(prompt, options, default_index)
    if selected is not None:
        return selected

    default_text = "ja" if default else "nein"
    help_text = f"Antwort: j/ja/y/yes = Ja, n/nein/no = Nein, Enter = {default_label}"
    while True:
        print(help_text)
        try:
            value = input_func(f"{prompt} [{default_text}]: ").strip().casefold()
        except (KeyboardInterrupt, EOFError) as exc:
            raise UserAbortError("Abbruch durch Nutzer.") from exc
        if not value:
            return default
        if value in YES_VALUES:
            return True
        if value in NO_VALUES:
            return False
        print("Bitte j, ja, y oder yes für Ja eingeben - oder n, nein oder no für Nein.")


def choose_from_options(
    prompt: str,
    options: Sequence[MenuOption[T]],
    *,
    input_func: InputFunc | None = None,
) -> T:
    if input_func is None:
        input_func = input
    if not options:
        raise ValueError("options darf nicht leer sein")

    selected = _questionary_select(prompt, options, 0)
    if selected is not None:
        return selected

    print(prompt)
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option.label}")
    while True:
        try:
            value = input_func("Nummer auswählen: ").strip()
        except (KeyboardInterrupt, EOFError) as exc:
            raise UserAbortError("Abbruch durch Nutzer.") from exc
        try:
            choice = int(value)
        except ValueError:
            print("Bitte eine Nummer aus der Liste eingeben.")
            continue
        if 1 <= choice <= len(options):
            return options[choice - 1].value
        print(f"Bitte eine Nummer zwischen 1 und {len(options)} eingeben.")
