from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Protocol


VIMEO_TOKEN_ENV = "PREDIGT_UPLOADER_VIMEO_TOKEN"
VIMEO_KEYRING_SERVICE = "PredigtUploader Vimeo"
VIMEO_KEYRING_USERNAME = "access-token"


class CredentialError(RuntimeError):
    pass


class CredentialNotConfiguredError(CredentialError):
    pass


class CredentialStoreError(CredentialError):
    pass


class CredentialBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class KeyringCredentialBackend:
    """Small adapter around keyring so tests can inject an in-memory backend."""

    def _module(self):
        try:
            import keyring
        except ImportError as exc:
            raise CredentialStoreError(
                "Der sichere Windows-Zugangsspeicher ist nicht installiert. Bitte PredigtUploader erneut einrichten."
            ) from exc
        return keyring

    def get_password(self, service: str, username: str) -> str | None:
        try:
            return self._module().get_password(service, username)
        except Exception as exc:
            raise CredentialStoreError(
                "Der sichere Windows-Zugangsspeicher konnte nicht gelesen werden."
            ) from exc

    def set_password(self, service: str, username: str, password: str) -> None:
        try:
            self._module().set_password(service, username, password)
        except Exception as exc:
            raise CredentialStoreError(
                "Der Vimeo-Zugang konnte nicht sicher im Windows-Zugangsspeicher abgelegt werden."
            ) from exc

    def delete_password(self, service: str, username: str) -> None:
        try:
            self._module().delete_password(service, username)
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name == "PasswordDeleteError":
                return
            raise CredentialStoreError(
                "Der gespeicherte Vimeo-Zugang konnte nicht entfernt werden."
            ) from exc


@dataclass(frozen=True)
class VimeoToken:
    value: str
    source: str


class VimeoCredentialManager:
    def __init__(
        self,
        backend: CredentialBackend | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.backend = backend or KeyringCredentialBackend()
        self.environ = os.environ if environ is None else environ

    def resolve(self) -> VimeoToken:
        environment_token = str(self.environ.get(VIMEO_TOKEN_ENV, "")).strip()
        if environment_token:
            return VimeoToken(environment_token, "environment")
        stored = self.backend.get_password(VIMEO_KEYRING_SERVICE, VIMEO_KEYRING_USERNAME)
        stored_token = str(stored or "").strip()
        if stored_token:
            return VimeoToken(stored_token, "keyring")
        raise CredentialNotConfiguredError(
            "Vimeo ist noch nicht eingerichtet. Öffne Einstellungen > Vimeo und richte den Zugang ein."
        )

    def status_text(self) -> str:
        try:
            token = self.resolve()
        except CredentialNotConfiguredError:
            return "nicht eingerichtet"
        except CredentialStoreError:
            return "sicherer Zugangsspeicher nicht verfügbar"
        if token.source == "environment":
            return "eingerichtet (Umgebungsvariable hat Vorrang)"
        return "eingerichtet (Windows-Zugangsspeicher)"

    def store(self, token: str) -> None:
        cleaned = token.strip()
        if not cleaned:
            raise CredentialNotConfiguredError("Bitte einen Vimeo-Token eingeben.")
        self.backend.set_password(VIMEO_KEYRING_SERVICE, VIMEO_KEYRING_USERNAME, cleaned)

    def remove_stored(self) -> None:
        self.backend.delete_password(VIMEO_KEYRING_SERVICE, VIMEO_KEYRING_USERNAME)
