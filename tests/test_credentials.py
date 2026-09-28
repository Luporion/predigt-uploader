from __future__ import annotations

import logging

import pytest

from predigt_uploader.credentials import (
    CredentialNotConfiguredError,
    VIMEO_KEYRING_SERVICE,
    VIMEO_KEYRING_USERNAME,
    VIMEO_TOKEN_ENV,
    VimeoCredentialManager,
    SVP_API_CODE_ENV,
    SVP_API_KEY_ENV,
    SVP_KEYRING_SERVICE,
    SVP_KEYRING_USERNAME,
    StreamingVideoProviderCredentialManager,
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


class MultiCredentialBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def test_svp_credentials_are_stored_as_one_secure_pair_and_removed(caplog):
    backend = MultiCredentialBackend()
    manager = StreamingVideoProviderCredentialManager(backend, {})
    with caplog.at_level(logging.DEBUG):
        manager.store("super-secret-key", "super-secret-code")
        resolved = manager.resolve()
        manager.remove_stored()
    assert resolved.api_key == "super-secret-key"
    assert resolved.api_code == "super-secret-code"
    assert resolved.source == "keyring"
    assert (SVP_KEYRING_SERVICE, SVP_KEYRING_USERNAME) not in backend.values
    assert "super-secret-key" not in caplog.text
    assert "super-secret-code" not in caplog.text


def test_svp_environment_pair_has_priority():
    backend = MultiCredentialBackend()
    manager = StreamingVideoProviderCredentialManager(
        backend,
        {SVP_API_KEY_ENV: "environment-key", SVP_API_CODE_ENV: "environment-code"},
    )
    manager.store("stored-key", "stored-code")
    assert manager.resolve().api_key == "environment-key"
    assert manager.resolve().source == "environment"


def test_svp_incomplete_environment_is_not_silently_mixed_with_store():
    backend = MultiCredentialBackend()
    manager = StreamingVideoProviderCredentialManager(backend, {SVP_API_KEY_ENV: "only-key"})
    manager.store("stored-key", "stored-code")
    with pytest.raises(CredentialNotConfiguredError, match="unvollständig"):
        manager.resolve()

