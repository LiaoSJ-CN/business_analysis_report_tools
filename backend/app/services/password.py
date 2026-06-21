"""Bcrypt password hashing / verification.

P3 (SEC-18): the previous flow compared the user-supplied password against
``settings.admin_password`` with ``!=`` — plaintext on disk and on the wire
through the error path. The fix stores only the bcrypt hash; verify uses
``bcrypt.checkpw`` which is constant-time.

Two wrappers:
- ``hash_password(plain) -> str`` — return a utf-8 bcrypt hash.
- ``verify_password(plain, stored_hash) -> bool`` — constant-time compare.

Both encode inputs as ``str`` to keep the API friendly; bcrypt itself
operates on bytes and caps at 72 bytes (longer inputs are silently
truncated by the underlying algorithm, which is acceptable for passwords
that fit).
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return a salted bcrypt hash of *plain* (utf-8)."""
    if not isinstance(plain, str):
        raise TypeError(f"password must be str, got {type(plain).__name__}")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, stored_hash: str) -> bool:
    """Constant-time check of *plain* against *stored_hash*.

    Raises ``ValueError`` if *stored_hash* is not a valid bcrypt hash — we
    refuse to silently treat an arbitrary string (e.g. legacy plaintext
    from a pre-P3 database row) as a valid credential. The caller is
    expected to translate ``ValueError`` into a 401.
    """
    if not isinstance(plain, str):
        raise TypeError(f"password must be str, got {type(plain).__name__}")
    if not isinstance(stored_hash, str) or not stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
        raise ValueError("stored_hash is not a valid bcrypt hash")
    return bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
