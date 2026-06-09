"""Testes de redaction de logs."""

from assistente_pessoal.logs import redact_sensitive


def test_redact_sensitive_remove_tokens_em_texto() -> None:
    """Tokens e headers Authorization nao podem aparecer em logs."""
    texto = "authorization: Bearer abc.def token=valor client_secret=valorfake"

    redigido = redact_sensitive(texto)

    assert "abc.def" not in redigido
    assert "valor" not in redigido
    assert "valorfake" not in redigido
    assert "***redacted***" in redigido


def test_redact_sensitive_remove_chaves_em_dict() -> None:
    """Dicionarios enviados a logs tambem devem ser redigidos."""
    redigido = redact_sensitive({"api_key": "123", "ok": "valor"})

    assert redigido == {"api_key": "***redacted***", "ok": "valor"}
