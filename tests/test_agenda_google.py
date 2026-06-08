"""Testes da integracao somente leitura com Google Agenda."""

from pathlib import Path

from assistente_pessoal.agenda_google import ClienteGoogleAgenda, formatar_eventos_google
from assistente_pessoal.config import GoogleAgendaConfig


def test_cliente_google_disponivel_quando_habilitado(tmp_path: Path) -> None:
    """Considera a integracao disponivel apenas com credenciais configuradas."""
    credenciais = tmp_path / "google-oauth-client.json"
    credenciais.write_text("{}", encoding="utf-8")
    config = GoogleAgendaConfig(habilitado=True, credentials_path=credenciais)

    assert ClienteGoogleAgenda(config).disponivel() is True


def test_formatar_eventos_google_vazio() -> None:
    """Explica claramente quando nao ha eventos retornados."""
    assert "Nenhum evento" in formatar_eventos_google([])
