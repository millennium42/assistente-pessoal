"""Testes da integracao com Google Agenda."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import assistente_pessoal.agenda_google as agenda_google
from assistente_pessoal.agenda_google import (
    ClienteGoogleAgenda,
    EventoGoogleAgenda,
    NovoEventoGoogleAgenda,
    ResultadoGoogleAgenda,
    evento_google_ainda_futuro,
    formatar_eventos_google,
)
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


def test_obter_eventos_intervalo_erro_sem_credencial(tmp_path: Path) -> None:
    """Explicita o erro de configuracao para a GUI reagir com um estado visivel."""
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=tmp_path / "inexistente.json",
        token_path=tmp_path / "token-inexistente.json",
    )

    resultado = ClienteGoogleAgenda(config).obter_eventos_intervalo()

    assert isinstance(resultado, ResultadoGoogleAgenda)
    assert resultado.erro is not None


def test_obter_eventos_intervalo_preserva_erro_de_token(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Mantem erro de token no resultado para o dashboard nao cair inteiro."""
    credenciais = tmp_path / "google-oauth-client.json"
    credenciais.write_text("{}", encoding="utf-8")
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=credenciais,
        token_path=tmp_path / "token.json",
    )
    cliente = ClienteGoogleAgenda(config)

    def falhar_credenciais():
        """Simula token criado com escopos antigos ou refresh invalido."""
        raise RuntimeError("Token antigo")

    monkeypatch.setattr(cliente, "_obter_credenciais", falhar_credenciais)

    resultado = cliente.obter_eventos_intervalo()

    assert resultado.eventos == []
    assert resultado.erro == "Token antigo"


def test_evento_google_ainda_futuro_ignora_evento_encerrado() -> None:
    """Nao considera evento ja encerrado como futuro no painel."""
    evento_passado = EventoGoogleAgenda(
        titulo="Reuniao encerrada",
        inicio="2026-06-08T08:00:00-03:00",
        fim="2026-06-08T09:00:00-03:00",
        link="",
        local="",
        origem="",
    )
    evento_futuro = EventoGoogleAgenda(
        titulo="Consulta",
        inicio="2026-06-08T11:00:00-03:00",
        fim="2026-06-08T12:00:00-03:00",
        link="",
        local="",
        origem="",
    )
    agora = datetime(2026, 6, 8, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))

    assert evento_google_ainda_futuro(evento_passado, "America/Sao_Paulo", agora=agora) is False
    assert evento_google_ainda_futuro(evento_futuro, "America/Sao_Paulo", agora=agora) is True


def test_criar_evento_envia_payload_para_google(monkeypatch, tmp_path: Path) -> None:
    """Cria evento usando o payload esperado pela Calendar API, sem rede."""
    credenciais = tmp_path / "google-oauth-client.json"
    credenciais.write_text("{}", encoding="utf-8")
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=credenciais,
        calendar_id="agenda-teste",
    )
    cliente = ClienteGoogleAgenda(config)
    credenciais_fake = object()
    requisicao: dict = {}

    class EventosFake:
        """Captura a chamada de insert e devolve um evento normalizado."""

        def insert(self, *, calendarId: str, body: dict):
            """Guarda os argumentos enviados para a API."""
            requisicao["calendarId"] = calendarId
            requisicao["body"] = body
            return self

        def execute(self) -> dict:
            """Simula a resposta da Calendar API."""
            return {
                "summary": "Consulta",
                "start": {"dateTime": "2026-06-09T14:30:00-03:00"},
                "end": {"dateTime": "2026-06-09T15:15:00-03:00"},
                "htmlLink": "https://calendar.google.com/event",
                "location": "Sala 2",
                "organizer": {"email": "milla@example.com"},
            }

    class ServicoFake:
        """Expoe apenas o recurso de eventos usado pelo cliente."""

        def events(self) -> EventosFake:
            """Devolve o recurso fake de eventos."""
            return EventosFake()

    def build_fake(nome: str, versao: str, credentials):
        """Confere a API solicitada e devolve o servico fake."""
        assert nome == "calendar"
        assert versao == "v3"
        assert credentials is credenciais_fake
        return ServicoFake()

    monkeypatch.setattr(cliente, "_obter_credenciais", lambda: credenciais_fake)
    monkeypatch.setattr(agenda_google, "_import_build", lambda: build_fake)

    inicio = datetime(2026, 6, 9, 14, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    evento = NovoEventoGoogleAgenda(
        titulo="Consulta",
        inicio=inicio,
        fim=inicio + timedelta(minutes=45),
        local="Sala 2",
        descricao="Levar exames.",
    )

    criado = cliente.criar_evento(evento)

    assert requisicao["calendarId"] == "agenda-teste"
    assert requisicao["body"] == {
        "summary": "Consulta",
        "location": "Sala 2",
        "description": "Levar exames.",
        "start": {
            "dateTime": "2026-06-09T14:30:00-03:00",
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": "2026-06-09T15:15:00-03:00",
            "timeZone": "America/Sao_Paulo",
        },
    }
    assert criado.titulo == "Consulta"
    assert criado.local == "Sala 2"
    assert criado.link == "https://calendar.google.com/event"


def test_criar_evento_explica_credencial_ausente(tmp_path: Path) -> None:
    """Mostra erro de configuracao sem derrubar a GUI com FileNotFoundError cru."""
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=tmp_path / "inexistente.json",
        token_path=tmp_path / "token-inexistente.json",
    )
    inicio = datetime(2026, 6, 9, 14, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    evento = NovoEventoGoogleAgenda("Consulta", inicio, inicio + timedelta(minutes=60))

    with pytest.raises(RuntimeError, match="Arquivo de credenciais"):
        ClienteGoogleAgenda(config).criar_evento(evento)


def test_cancelar_evento_envia_delete_para_google(monkeypatch, tmp_path: Path) -> None:
    """Cancela evento pelo ID usando o endpoint oficial, sem rede."""
    credenciais = tmp_path / "google-oauth-client.json"
    credenciais.write_text("{}", encoding="utf-8")
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=credenciais,
        calendar_id="agenda-teste",
    )
    cliente = ClienteGoogleAgenda(config)
    credenciais_fake = object()
    requisicao: dict = {}

    class EventosFake:
        """Captura a chamada de delete."""

        def delete(self, *, calendarId: str, eventId: str):
            """Guarda os argumentos enviados para a API."""
            requisicao["calendarId"] = calendarId
            requisicao["eventId"] = eventId
            return self

        def execute(self) -> dict:
            """Simula a resposta vazia da Calendar API."""
            return {}

    class ServicoFake:
        """Expoe apenas o recurso de eventos usado pelo cliente."""

        def events(self) -> EventosFake:
            """Devolve o recurso fake de eventos."""
            return EventosFake()

    def build_fake(nome: str, versao: str, credentials):
        """Confere a API solicitada e devolve o servico fake."""
        assert nome == "calendar"
        assert versao == "v3"
        assert credentials is credenciais_fake
        return ServicoFake()

    monkeypatch.setattr(cliente, "_obter_credenciais", lambda: credenciais_fake)
    monkeypatch.setattr(agenda_google, "_import_build", lambda: build_fake)

    cliente.cancelar_evento("evt-123")

    assert requisicao == {"calendarId": "agenda-teste", "eventId": "evt-123"}


def test_token_antigo_nao_e_mascarado_por_escopo_novo(tmp_path: Path) -> None:
    """Recusa token somente leitura em vez de injeta-lo com permissoes novas."""
    token = tmp_path / "token.json"
    token.write_text(
        json.dumps(
            {
                "token": "token-antigo",
                "refresh_token": "refresh-antigo",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
            }
        ),
        encoding="utf-8",
    )
    config = GoogleAgendaConfig(
        habilitado=True,
        credentials_path=tmp_path / "google-oauth-client.json",
        token_path=token,
    )

    with pytest.raises(RuntimeError, match="permissoes antigas"):
        ClienteGoogleAgenda(config)._obter_credenciais()
