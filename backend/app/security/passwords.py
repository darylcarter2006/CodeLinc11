"""Password hashing (Argon2id) and the password rules.

Only the Argon2id hash is stored; the password itself is never logged, stored or returned.
Rules follow NIST SP 800-63B: a minimum length, a generous maximum, no composition rules, and
a check against very common passwords.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 8
MAX_LENGTH = 128

# OWASP's recommended Argon2id settings (19 MiB, 2 passes): about 50 ms per hash.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
# Verified against when no account matches, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")

# A short list of the most common passwords that pass the length rule.
_COMMON = frozenset(
    [
        "12345678",
        "123456789",
        "1234567890",
        "0123456789",
        "87654321",
        "11111111",
        "00000000",
        "12341234",
        "11223344",
        "password",
        "password1",
        "password12",
        "password123",
        "passw0rd",
        "p@ssw0rd",
        "p@ssword",
        "iloveyou1",
        "qwertyui",
        "qwerty123",
        "qwertyuiop",
        "1q2w3e4r",
        "1qaz2wsx",
        "zaq12wsx",
        "asdfghjk",
        "asdfasdf",
        "abcd1234",
        "abcdefgh",
        "abc12345",
        "letmein1",
        "welcome1",
        "welcome123",
        "sunshine",
        "princess",
        "football",
        "baseball",
        "superman",
        "batman123",
        "trustno1",
        "starwars",
        "iloveyou",
        "monkey123",
        "dragon12",
        "master123",
        "whatever",
        "computer",
        "internet",
        "changeme",
        "changeme1",
        "default1",
        "admin123",
        "administrator",
        "insurance",
        "lifeinsurance",
        "coverage",
        "coveragecompass",
        "lincoln123",
        "lincolnfinancial",
    ]
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """True if it matches. With no stored hash, still does the work and returns False."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """True when the hash was made with older settings; rehash it after a successful log-in."""
    return _hasher.check_needs_rehash(stored_hash)


def password_problem(password: str, email: str) -> str | None:
    """A message for the person if the password isn't acceptable, else None."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters for your password."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters for your password."
    lowered = password.lower()
    if lowered in _COMMON or len(set(password)) < 3:
        return "That password is too easy to guess. Try a longer phrase."
    local_part = email.split("@")[0].lower()
    if lowered in (email.lower(), local_part):
        return "Your password can't be your email address."
    return None
