"""Integracao opcional com Google Agenda em modo somente leitura."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from assistente_pessoal.config import GoogleAgendaConfig

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@dataclass(frozen=True)
class EventoGoogleAgenda:
    """Evento normalizado do Google Agenda para CLI e dashboard."""

    titulo: str
    inicio: str
    fim: str
    link: str
    local: str
    origem: str


class ClienteGoogleAgenda:
    """Autentica no Google e lista eventos futuros do calendario configurado."""

    def __init__(self, config: GoogleAgendaConfig) -> None:
        """Guarda apenas a configuracao da integracao."""
        self.config = config

    def disponivel(self) -> bool:
        """Indica se a integracao foi habilitada e tem um arquivo de credenciais configurado."""
        return self.config.habilitado and self.config.credentials_path.exists()

    def autenticar_interativo(self) -> Path:
        """Executa o fluxo OAuth de desktop e persiste o token localmente."""
        InstalledAppFlow = _import_installed_app_flow()
        self.config.token_path.parent.mkdir(parents=True, exist_ok=True)
        fluxo = InstalledAppFlow.from_client_secrets_file(
            str(self.config.credentials_path),
            SCOPES,
        )
        credenciais = fluxo.run_local_server(port=0)
        self.config.token_path.write_text(credenciais.to_json(), encoding="utf-8")
        return self.config.token_path

    def listar_eventos(self) -> list[EventoGoogleAgenda]:
        """Le os proximos eventos do calendario principal configurado."""
        if not self.config.habilitado:
            return []
        try:
            credenciais = self._obter_credenciais()
        except FileNotFoundError:
            return []
        if credenciais is None:
            return []
        build = _import_build()
        servico = build("calendar", "v3", credentials=credenciais)
        agora = datetime.now(UTC)
        ate = agora + timedelta(days=self.config.janela_dias)
        resposta = (
            servico.events()
            .list(
                calendarId=self.config.calendar_id,
                timeMin=agora.isoformat(),
                timeMax=ate.isoformat(),
                maxResults=self.config.max_eventos,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [normalizar_evento_google(item) for item in resposta.get("items", [])]

    def _obter_credenciais(self):
        """Carrega, renova ou cria as credenciais OAuth conforme o estado local."""
        Credentials = _import_credentials()
        Request = _import_request()
        credenciais = None
        if self.config.token_path.exists():
            credenciais = Credentials.from_authorized_user_file(str(self.config.token_path), SCOPES)
        if credenciais and credenciais.valid:
            return credenciais
        if credenciais and credenciais.expired and credenciais.refresh_token:
            credenciais.refresh(Request())
            self.config.token_path.write_text(credenciais.to_json(), encoding="utf-8")
            return credenciais
        if self.config.credentials_path.exists():
            return None
        raise FileNotFoundError(
            f"Nao encontrei o arquivo de credenciais do Google em {self.config.credentials_path}."
        )


def normalizar_evento_google(item: dict) -> EventoGoogleAgenda:
    """Converte o payload da API do Google para o formato interno do assistente."""
    inicio = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date") or ""
    fim = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date") or ""
    return EventoGoogleAgenda(
        titulo=item.get("summary", "Evento sem titulo"),
        inicio=inicio,
        fim=fim,
        link=item.get("htmlLink", ""),
        local=item.get("location", ""),
        origem=item.get("organizer", {}).get("email", ""),
    )


def formatar_eventos_google(eventos: list[EventoGoogleAgenda]) -> str:
    """Formata eventos para visualizacao rapida na CLI."""
    if not eventos:
        return "Nenhum evento futuro encontrado no Google Agenda."
    linhas = ["Proximos eventos do Google Agenda:"]
    for indice, evento in enumerate(eventos, start=1):
        linhas.append(
            f"{indice}. {evento.titulo} | {evento.inicio} | "
            f"{evento.local or 'sem local'} {evento.link}"
        )
    return "\n".join(linhas)


def _import_credentials():
    """Importa a classe de credenciais apenas quando a integracao e usada."""
    from google.oauth2.credentials import Credentials

    return Credentials


def _import_installed_app_flow():
    """Importa o fluxo OAuth de aplicativo instalado apenas sob demanda."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    return InstalledAppFlow


def _import_request():
    """Importa a classe de refresh apenas quando ha token para renovar."""
    from google.auth.transport.requests import Request

    return Request


def _import_build():
    """Importa o construtor do cliente da API do Google apenas sob demanda."""
    from googleapiclient.discovery import build

    return build
