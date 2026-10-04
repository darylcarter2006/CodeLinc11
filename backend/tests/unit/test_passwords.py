from __future__ import annotations

from app.security.passwords import hash_password, needs_rehash, password_problem, verify_password


def test_hash_and_verify() -> None:
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "correct horse battery")
    assert not verify_password(stored, "Correct horse battery")
    assert not needs_rehash(stored)


def test_each_hash_is_salted() -> None:
    assert hash_password("same password") != hash_password("same password")


def test_no_stored_hash_or_a_corrupt_one_never_verifies() -> None:
    assert not verify_password(None, "timing-equalizer-not-a-real-password")
    assert not verify_password("not-a-hash", "anything")


def test_password_rules() -> None:
    assert password_problem("a long enough phrase", "riley@example.com") is None
    assert password_problem("1234567", "") is not None
    assert password_problem("PASSWORD123", "") is not None  # common, any case
    assert password_problem("riley", "riley@example.com") is not None
    assert password_problem("RILEY@example.com", "riley@example.com") is not None
    assert password_problem("éèêëàâäô", "") is None  # any characters are allowed
