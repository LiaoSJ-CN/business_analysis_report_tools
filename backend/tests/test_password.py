"""Unit tests for ``app.services.password`` (bcrypt hash / verify)."""

from __future__ import annotations

import pytest

from app.services.password import hash_password, verify_password


def test_hash_returns_string() -> None:
    """hash_password returns a non-empty string (utf-8 encoded bcrypt hash)."""
    h = hash_password("hello-world")
    assert isinstance(h, str)
    assert len(h) > 50  # bcrypt hashes are ~60 chars
    # Standard bcrypt prefix ($2a$, $2b$, $2y$) identifies the algorithm.
    assert h.startswith(("$2a$", "$2b$", "$2y$"))


def test_hash_is_salted() -> None:
    """Two hashes of the same password differ (random salt)."""
    a = hash_password("same-input")
    b = hash_password("same-input")
    assert a != b, "bcrypt hashes must be salted — identical input produced identical output"


def test_verify_correct_password() -> None:
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h) is True


def test_verify_wrong_password() -> None:
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", h) is False


def test_verify_against_legacy_placeholder_hash_fails_cleanly() -> None:
    """A non-bcrypt hash string must raise (not return False silently)."""
    # Plaintext "hash" — would be the pre-P3 storage format. verify_password
    # must refuse to silently treat it as a valid bcrypt hash.
    with pytest.raises(ValueError):
        verify_password("any-password", "not-a-bcrypt-hash")


def test_verify_empty_password() -> None:
    """bcrypt allows empty passwords; verify roundtrips cleanly."""
    h = hash_password("")
    assert verify_password("", h) is True
    assert verify_password("non-empty", h) is False
