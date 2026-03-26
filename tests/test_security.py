from app.security import generate_csrf_token, hash_password, verify_password


def test_hash_password_round_trip() -> None:
    password_hash = hash_password("pilot-password")

    assert password_hash != "pilot-password"
    assert verify_password("pilot-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_generate_csrf_token_returns_unique_values() -> None:
    first = generate_csrf_token()
    second = generate_csrf_token()

    assert first
    assert second
    assert first != second
