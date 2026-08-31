from __future__ import annotations

import logging

import pytest

from predigt_uploader.credentials import (
    CredentialNotConfiguredError,
    VIMEO_KEYRING_SERVICE,
    VIMEO_KEYRING_USERNAME,
    VIMEO_TOKEN_ENV,
    VimeoCredentialManager,
)
from predigt_uploader.publishing.vimeo import VimeoCredentialError, load_vimeo_token


class MemoryCredentialBackend:
    def __init__(self, password: str | None = None) -> None:
        self.password = password

    def get_password(self, service: str, username: str) -> str | None:
        assert service == VIMEO_KEYRING_SERVICE
        assert username == VIMEO_KEYRING_USERNAME
        return self.password

    def set_password(self, service: str, username: str, password: str) -> None:
        assert service == VIMEO_KEYRING_SERVICE
        assert username == VIMEO_KEYRING_USERNAME
        self.password = password

    def delete_password(self, service: str, username: str) -> None:
        assert service == VIMEO_KEYRING_SERVICE
        assert username == VIMEO_KEYRING_USERNAME
        self.password = None


def test_environment_token_has_priority_over_secure_store():
    manager = VimeoCredentialManager(
        MemoryCredentialBackend("stored-token"),
        {VIMEO_TOKEN_ENV: "environment-token"},
    )

    token = manager.resolve()

    assert token.value == "environment-token"
    assert token.source == "environment"


def test_secure_store_is_used_when_environment_is_empty():
    manager = VimeoCredentialManager(MemoryCredentialBackend("stored-token"), {})

    assert manager.resolve().value == "stored-token"
    assert load_vimeo_token(credential_manager=manager) == "stored-token"


def test_missing_token_has_friendly_setup_message_without_secret():
    manager = VimeoCredentialManager(MemoryCredentialBackend(), {})

    with pytest.raises(CredentialNotConfiguredError, match="Einstellungen > Vimeo"):
        manager.resolve()
    with pytest.raises(VimeoCredentialError, match="Vimeo ist noch nicht eingerichtet"):
        load_vimeo_token(credential_manager=manager)


def test_token_can_be_stored_and_removed_without_being_logged(caplog):
    backend = MemoryCredentialBackend()
    manager = VimeoCredentialManager(backend, {})

    with caplog.at_level(logging.DEBUG):
        manager.store("very-secret-vimeo-token")
        assert manager.resolve().source == "keyring"
        manager.remove_stored()

    assert backend.password is None
    assert "very-secret-vimeo-token" not in caplog.text

