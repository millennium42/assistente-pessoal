"""Adaptador local para autenticacao e eventos do Google Agenda."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from assistente_pessoal.logs import redact_sensitive

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


@dataclass(frozen=True)
class CalendarEvent:
    """Evento resumido para a GUI local."""

    titulo: str
    inicio: str
    link: str

    def to_dict(self) -> dict[str, str]:
        """Serializa evento para API."""
        return {"titulo": self.titulo, "inicio": self.inicio, "link": self.link}


class GoogleCalendarAdapter:
    """Gerencia OAuth local e eventos seguros do Google Agenda."""

    def __init__(
        self,
        credentials_path: Path | None = None,
        token_path: Path | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """Resolve caminhos padrao sem expor client secret para o frontend."""
        self.credentials_path = credentials_path or _credentials_path()
        self.token_path = token_path or _token_path()
        self.redirect_uri = redirect_uri or os.getenv(
            "GOOGLE_CALENDAR_REDIRECT_URI",
            "http://localhost:8777/api/google-calendar/auth/callback",
        )

    def status(self) -> dict[str, Any]:
        """Retorna status da agenda sem expor segredos."""
        configured = self.credentials_path.exists() and self.credentials_path.is_file()
        token_present = self.token_path.exists() and self.token_path.is_file()
        return {
            "configured": configured,
            "connected": bool(configured and token_present and self._credentials(valid_only=False)),
            "credentials_file": self.credentials_path.name if configured else "",
            "token_present": token_present,
        }

    def authorization_url(self) -> str:
        """Cria URL de autorizacao OAuth com state local."""
        flow = self._build_flow()
        url, _state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return url

    def complete_authorization(self, code: str) -> None:
        """Troca o code por token e persiste apenas no backend."""
        flow = self._build_flow()
        flow.fetch_token(code=code)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(flow.credentials.to_json(), encoding="utf-8")

    def upcoming_events(self, limite: int = 5) -> list[CalendarEvent]:
        """Lista proximos eventos do calendario primario."""
        credentials = self._credentials(valid_only=True)
        if credentials is None:
            return []
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        now = datetime.now(UTC).isoformat()
        resultado = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=limite,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        eventos = []
        for item in resultado.get("items", []):
            inicio = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date", "")
            eventos.append(
                CalendarEvent(
                    titulo=item.get("summary", "Sem titulo"),
                    inicio=inicio,
                    link=item.get("htmlLink", ""),
                )
            )
        return eventos

    def create_event(
        self,
        titulo: str,
        inicio: str,
        fim: str | None = None,
        descricao: str = "",
        timezone: str = "America/Sao_Paulo",
    ) -> CalendarEvent:
        """Cria evento no calendario primario pela API oficial."""
        credentials = self._credentials(valid_only=True)
        if credentials is None:
            raise RuntimeError("Google Agenda nao conectado.")
        inicio_dt = _parse_event_datetime(inicio, timezone)
        fim_dt = _parse_event_datetime(fim, timezone) if fim else inicio_dt + timedelta(hours=1)
        if fim_dt <= inicio_dt:
            raise RuntimeError("O fim do evento precisa ser depois do inicio.")

        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        criado = (
            service.events()
            .insert(
                calendarId="primary",
                body={
                    "summary": titulo,
                    "description": descricao,
                    "start": {
                        "dateTime": inicio_dt.isoformat(),
                        "timeZone": timezone,
                    },
                    "end": {
                        "dateTime": fim_dt.isoformat(),
                        "timeZone": timezone,
                    },
                },
            )
            .execute()
        )
        inicio_criado = criado.get("start", {}).get("dateTime") or criado.get("start", {}).get(
            "date", ""
        )
        return CalendarEvent(
            titulo=criado.get("summary", titulo),
            inicio=inicio_criado,
            link=criado.get("htmlLink", ""),
        )

    def _build_flow(self):
        """Constroi flow OAuth a partir do arquivo local da raiz."""
        if not self.credentials_path.exists():
            raise RuntimeError(
                "Arquivo googleAgenda.json nao encontrado na raiz ou no caminho configurado."
            )
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_secrets_file(
            str(self.credentials_path),
            scopes=GOOGLE_CALENDAR_SCOPES,
        )
        flow.redirect_uri = self.redirect_uri
        return flow

    def _credentials(self, valid_only: bool) -> Any | None:
        """Carrega credenciais do token local sem vazar conteudo."""
        if not self.token_path.exists():
            return None
        try:
            from google.oauth2.credentials import Credentials

            credentials = Credentials.from_authorized_user_info(
                json.loads(self.token_path.read_text(encoding="utf-8")),
                GOOGLE_CALENDAR_SCOPES,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(str(redact_sensitive(str(exc)))) from exc
        if valid_only and not credentials.valid:
            return None
        return credentials


def _credentials_path() -> Path:
    """Resolve o arquivo raiz do OAuth do Google Agenda."""
    custom = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
    if custom:
        return Path(custom)
    return Path.cwd() / "googleAgenda.json"


def _token_path() -> Path:
    """Resolve onde o token do Google Agenda fica salvo localmente."""
    custom = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE")
    if custom:
        return Path(custom)
    return Path.cwd() / ".assistente" / "google-calendar-token.json"


def _parse_event_datetime(valor: str, timezone: str) -> datetime:
    """Converte entrada da GUI em datetime com timezone local."""
    normalizado = valor.strip().replace("Z", "+00:00")
    try:
        data = datetime.fromisoformat(normalizado)
    except ValueError as exc:
        raise RuntimeError("Data de evento invalida. Use formato ISO.") from exc
    if data.tzinfo is None:
        return data.replace(tzinfo=ZoneInfo(timezone))
    return data.astimezone(ZoneInfo(timezone))
