"""Integracao opcional com Google Agenda via Google Calendar API oficial.

Fornece funcionalidades para autenticar, consultar os proximos eventos e
criar eventos no calendario configurado do usuario.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente_pessoal.config import GoogleAgendaConfig

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@dataclass(frozen=True)
class EventoGoogleAgenda:
    """Evento normalizado do Google Agenda para CLI e dashboard.

    Attributes:
        titulo: Titulo ou sumario do evento.
        inicio: Data e hora do inicio no formato ISO 8601.
        fim: Data e hora do fim no formato ISO 8601.
        link: URL para visualizar o evento na web.
        local: O local onde ocorrera o evento.
        origem: O email de quem organizou.
        id: Identificador interno do evento no Google Agenda, usado para cancelamento.
    """

    titulo: str
    inicio: str
    fim: str
    link: str
    local: str
    origem: str
    id: str = ""


@dataclass(frozen=True)
class ResultadoGoogleAgenda:
    """Empacota eventos e estado de conectividade para a GUI e CLI.

    Attributes:
        eventos: Uma lista com os eventos recebidos.
        erro: Texto em caso de falha de leitura (None se obteve sucesso).
        mes_referencia: O mes utilizado na consulta (usado pela GUI para montar calendario).
    """

    eventos: list[EventoGoogleAgenda]
    erro: str | None = None
    mes_referencia: date | None = None


@dataclass(frozen=True)
class NovoEventoGoogleAgenda:
    """Representa um novo evento a ser criado pela UI ou CLI.

    Attributes:
        titulo: Titulo a ser inserido na agenda.
        inicio: O datetime indicando o inicio.
        fim: O datetime indicando o fim.
        local: Local (opcional).
        descricao: Descricao em texto do evento.
    """

    titulo: str
    inicio: datetime
    fim: datetime
    local: str = ""
    descricao: str = ""


class ClienteGoogleAgenda:
    """Autentica no Google e lista eventos futuros pelo endpoint oficial Calendar API v3."""

    def __init__(self, config: GoogleAgendaConfig) -> None:
        """Guarda apenas a configuracao da integracao.

        Args:
            config: A configuracao com caminhos para as credenciais e tokens.
        """
        self.config = config

    def disponivel(self) -> bool:
        """Indica se a integracao foi habilitada e tem um arquivo de credenciais configurado.

        Returns:
            True se estiver habilitada, False caso contrario.
        """
        return self.config.habilitado and self.config.credentials_path.exists()

    def autenticar_interativo(self) -> Path:
        """Executa o fluxo OAuth de desktop e persiste o token localmente.

        Returns:
            O caminho do arquivo de token persistido.
        """
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
        """Le os proximos eventos do calendario principal configurado.

        Returns:
            Lista de objetos EventoGoogleAgenda representando eventos futuros.
        """
        return self.obter_eventos_intervalo().eventos

    def obter_eventos_intervalo(
        self,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        limite: int | None = None,
    ) -> ResultadoGoogleAgenda:
        """Busca eventos em um intervalo e preserva erros de conectividade.

        Args:
            inicio: Limite inicial para a consulta. Padrao e agora em UTC.
            fim: Limite final da consulta. Padrao e calculado baseado na janela de dias configurada.
            limite: Numero maximo de eventos retornados.

        Returns:
            Um ResultadoGoogleAgenda com os eventos ou o motivo do erro.
        """
        if not self.config.habilitado:
            return ResultadoGoogleAgenda(eventos=[])
        try:
            credenciais = self._obter_credenciais()
        except FileNotFoundError:
            return ResultadoGoogleAgenda(
                eventos=[],
                erro="Arquivo de credenciais da Google Agenda nao encontrado.",
            )
        except RuntimeError as exc:
            return ResultadoGoogleAgenda(eventos=[], erro=str(exc))
        if credenciais is None:
            return ResultadoGoogleAgenda(
                eventos=[],
                erro="Google Agenda ainda nao autenticada neste ambiente.",
            )
        build = _import_build()
        try:
            servico = build("calendar", "v3", credentials=credenciais)
            agora = inicio or datetime.now(UTC)
            ate = fim or (agora + timedelta(days=self.config.janela_dias))
            resposta = (
                servico.events()
                .list(
                    calendarId=self.config.calendar_id,
                    timeMin=agora.isoformat(),
                    timeMax=ate.isoformat(),
                    maxResults=limite or self.config.max_eventos,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception:
            return ResultadoGoogleAgenda(
                eventos=[],
                erro=(
                    "Falha ao consultar a Google Agenda. "
                    "Verifique autenticacao e estabilidade da conexao."
                ),
            )
        return ResultadoGoogleAgenda(
            eventos=[normalizar_evento_google(item) for item in resposta.get("items", [])]
        )

    def obter_eventos_mes(self, referencia: date | None = None) -> ResultadoGoogleAgenda:
        """Busca os eventos do mes inteiro para visualizacao em calendario.

        Args:
            referencia: Data dentro do mes e ano que deve ser buscado.

        Returns:
            O resultado da chamada a API cobrindo todo aquele mes.
        """
        data_base = referencia or datetime.now(UTC).date()
        primeiro_dia = data_base.replace(day=1)
        ultimo_dia = calendar.monthrange(primeiro_dia.year, primeiro_dia.month)[1]
        inicio = datetime.combine(primeiro_dia, datetime.min.time(), tzinfo=UTC)
        fim = datetime.combine(
            primeiro_dia.replace(day=ultimo_dia) + timedelta(days=1),
            datetime.min.time(),
            tzinfo=UTC,
        )
        resultado = self.obter_eventos_intervalo(
            inicio=inicio,
            fim=fim,
            limite=max(self.config.max_eventos, 250),
        )
        return ResultadoGoogleAgenda(
            eventos=resultado.eventos,
            erro=resultado.erro,
            mes_referencia=primeiro_dia,
        )

    def criar_evento(self, evento: NovoEventoGoogleAgenda) -> EventoGoogleAgenda:
        """Cria um evento no calendario configurado usando a API oficial.

        Args:
            evento: Dados do novo evento que deve ser criado.

        Returns:
            O evento criado e devolvido pelo Google.

        Raises:
            RuntimeError: Em falhas de rede ou de credenciais.
        """
        if not self.config.habilitado:
            raise RuntimeError("Google Agenda desabilitada no config.toml.")
        try:
            credenciais = self._obter_credenciais()
        except FileNotFoundError as exc:
            raise RuntimeError("Arquivo de credenciais da Google Agenda nao encontrado.") from exc
        if credenciais is None:
            raise RuntimeError("Google Agenda ainda nao autenticada neste ambiente.")
        build = _import_build()
        try:
            servico = build("calendar", "v3", credentials=credenciais)
            timezone = evento.inicio.tzinfo.key if hasattr(evento.inicio.tzinfo, "key") else "UTC"
            resposta = (
                servico.events()
                .insert(
                    calendarId=self.config.calendar_id,
                    body={
                        "summary": evento.titulo,
                        "location": evento.local,
                        "description": evento.descricao,
                        "start": {
                            "dateTime": evento.inicio.isoformat(),
                            "timeZone": timezone,
                        },
                        "end": {
                            "dateTime": evento.fim.isoformat(),
                            "timeZone": timezone,
                        },
                    },
                )
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(
                "Nao foi possivel criar o evento. Verifique autenticacao e estabilidade da conexao."
            ) from exc
        return normalizar_evento_google(resposta)

    def cancelar_evento(self, evento_id: str) -> None:
        """Remove um evento do calendario configurado usando o ID oficial do Google.

        Args:
            evento_id: Identificador do evento recebido na listagem da Calendar API.

        Raises:
            RuntimeError: Em falhas de rede, credenciais ou configuracao.
        """
        if not self.config.habilitado:
            raise RuntimeError("Google Agenda desabilitada no config.toml.")
        if not evento_id.strip():
            raise RuntimeError("Nao recebi o identificador do evento para cancelar.")
        try:
            credenciais = self._obter_credenciais()
        except FileNotFoundError as exc:
            raise RuntimeError("Arquivo de credenciais da Google Agenda nao encontrado.") from exc
        if credenciais is None:
            raise RuntimeError("Google Agenda ainda nao autenticada neste ambiente.")
        build = _import_build()
        try:
            (
                build("calendar", "v3", credentials=credenciais)
                .events()
                .delete(calendarId=self.config.calendar_id, eventId=evento_id)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(
                "Nao foi possivel cancelar o evento. "
                "Verifique autenticacao e estabilidade da conexao."
            ) from exc

    def _obter_credenciais(self):
        """Carrega, renova ou cria as credenciais OAuth conforme o estado local.

        Returns:
            O objeto de credenciais OAuth, ou None caso precise intervir.
        """
        Credentials = _import_credentials()
        Request = _import_request()
        credenciais = None
        if self.config.token_path.exists():
            credenciais = Credentials.from_authorized_user_file(str(self.config.token_path))
        if credenciais and not _credenciais_tem_escopos_esperados(credenciais):
            raise RuntimeError(
                "Token da Google Agenda foi criado com permissoes antigas. "
                "Execute 'assistente-pessoal agenda google-auth' novamente."
            )
        if credenciais and credenciais.valid:
            return credenciais
        if credenciais and credenciais.expired and credenciais.refresh_token:
            try:
                credenciais.refresh(Request())
            except Exception as exc:
                raise RuntimeError(
                    "Falha ao renovar token da Google Agenda. "
                    "Verifique a conexao ou autentique novamente."
                ) from exc
            self.config.token_path.write_text(credenciais.to_json(), encoding="utf-8")
            return credenciais
        if self.config.credentials_path.exists():
            return None
        raise FileNotFoundError(
            f"Nao encontrei o arquivo de credenciais do Google em {self.config.credentials_path}."
        )


def normalizar_evento_google(item: dict) -> EventoGoogleAgenda:
    """Converte o payload da API do Google para o formato interno do assistente.

    Args:
        item: Dicionario proveniente da resposta da API.

    Returns:
        Um EventoGoogleAgenda bem formad.
    """
    inicio = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date") or ""
    fim = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date") or ""
    return EventoGoogleAgenda(
        titulo=item.get("summary", "Evento sem titulo"),
        inicio=inicio,
        fim=fim,
        link=item.get("htmlLink", ""),
        local=item.get("location", ""),
        origem=item.get("organizer", {}).get("email", ""),
        id=item.get("id", ""),
    )


def formatar_eventos_google(eventos: list[EventoGoogleAgenda]) -> str:
    """Formata eventos para visualizacao rapida na CLI.

    Args:
        eventos: Lista de eventos.

    Returns:
        Texto formatado em blocos numerados.
    """
    if not eventos:
        return "Nenhum evento futuro encontrado no Google Agenda."
    linhas = ["Proximos eventos do Google Agenda:"]
    for indice, evento in enumerate(eventos, start=1):
        linhas.append(
            f"{indice}. {evento.titulo} | {evento.inicio} | "
            f"{evento.local or 'sem local'} {evento.link}"
        )
    return "\n".join(linhas)


def data_evento_google(evento: EventoGoogleAgenda) -> date | None:
    """Extrai a data local basica do inicio do evento para montar calendarios.

    Args:
        evento: O evento alvo.

    Returns:
        A data extraida ou None caso invalido.
    """
    valor = evento.inicio.strip()
    if not valor:
        return None
    if len(valor) == 10:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def evento_google_ainda_futuro(
    evento: EventoGoogleAgenda,
    timezone: str,
    agora: datetime | None = None,
) -> bool:
    """Indica se o evento ainda nao terminou no fuso informado.

    Args:
        evento: Evento da agenda.
        timezone: String indicando o fuso horario.
        agora: Base datetime de referencia.

    Returns:
        True se o evento estiver no futuro, senao False.
    """
    tzinfo = ZoneInfo(timezone)
    referencia = agora or datetime.now(tzinfo)
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=tzinfo)
    else:
        referencia = referencia.astimezone(tzinfo)

    fim = _parse_data_hora_google(evento.fim, timezone)
    if fim is not None:
        return fim >= referencia

    inicio = _parse_data_hora_google(evento.inicio, timezone)
    if inicio is not None:
        return inicio >= referencia
    return False


def formatar_data_hora_google(valor: str, timezone: str) -> str:
    """Converte timestamps ISO do Google Agenda em texto local curto.

    Args:
        valor: A string de data vinda do Google API.
        timezone: O fuso para conversao.

    Returns:
        Uma string resumida como 'DD/MM HH:MM' ou semelhante.
    """
    if not valor:
        return "--"
    if len(valor) == 10:
        try:
            return date.fromisoformat(valor).strftime("%d/%m")
        except ValueError:
            return valor
    try:
        data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return data.astimezone(ZoneInfo(timezone)).strftime("%d/%m %H:%M")
    except ValueError:
        return valor


def _parse_data_hora_google(valor: str, timezone: str) -> datetime | None:
    """Converte datas do Google Agenda para datetime com timezone.

    Args:
        valor: A string de data original.
        timezone: O fuso horario alvo para datas full-day.

    Returns:
        Um datetime valido ou None.
    """
    if not valor:
        return None
    tzinfo = ZoneInfo(timezone)
    if len(valor) == 10:
        try:
            return datetime.combine(date.fromisoformat(valor), datetime.min.time(), tzinfo=tzinfo)
        except ValueError:
            return None
    try:
        data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    if data.tzinfo is None:
        return data.replace(tzinfo=tzinfo)
    return data.astimezone(tzinfo)


def _credenciais_tem_escopos_esperados(credenciais) -> bool:
    """Confere se o token local cobre leitura e escrita de eventos.

    Args:
        credenciais: Objeto de token oauth carregado.

    Returns:
        True se tudo ok, ou False se o escopo for muito antigo.
    """
    if not hasattr(credenciais, "has_scopes"):
        return True
    return bool(credenciais.has_scopes(SCOPES))


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
