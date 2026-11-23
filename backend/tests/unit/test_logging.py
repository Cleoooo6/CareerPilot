from app.core.logging import clear_registered_secrets, redact, register_secret


def test_dsn_password_is_redacted():
    text = redact("postgresql://careerpilot:super-secret@localhost:5433/careerpilot")
    assert "super-secret" not in text
    assert "***REDACTED***" in text


def test_bearer_and_sk_are_redacted():
    text = redact("Authorization: Bearer abcdef123456 sk-1234secret")
    assert "abcdef123456" not in text
    assert "sk-1234secret" not in text


def test_registered_secret_is_redacted():
    clear_registered_secrets()
    register_secret("my-glm-key-without-sk-prefix")
    try:
        assert "my-glm-key-without-sk-prefix" not in redact(
            "key=my-glm-key-without-sk-prefix"
        )
    finally:
        clear_registered_secrets()
