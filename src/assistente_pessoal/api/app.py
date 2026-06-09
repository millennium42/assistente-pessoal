"""Aplicacao FastAPI local, pensada para sidecar desktop."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from assistente_pessoal.api.schemas import (
    CalendarEventCreateRequest,
    ChatRequest,
    MemoryCreateRequest,
    NewsInterestRequest,
    StudyRequest,
)
from assistente_pessoal.application.services import AssistenteService
from assistente_pessoal.config import AppConfig, carregar_config
from assistente_pessoal.logs import redact_sensitive


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Cria API sem CORS aberto e sem exposicao de segredos."""
    app = FastAPI(
        title="Assistente Pessoal API",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.config = config or carregar_config()
    app.state.service = AssistenteService(app.state.config)

    def get_service() -> AssistenteService:
        return app.state.service

    service_dependency = Depends(get_service)
    memories_limit_query = Query(default=20, ge=1, le=100)
    news_limit_query = Query(default=100, ge=1, le=100)
    news_offset_query = Query(default=0, ge=0)
    music_days_query = Query(default=45, ge=1, le=365)
    export_destination_query = Query(default=Path("exports"))

    @app.get("/api/health")
    def health(service: AssistenteService = service_dependency) -> dict:
        """Status operacional local."""
        return service.health()

    @app.get("/api/dashboard")
    def dashboard(service: AssistenteService = service_dependency) -> dict:
        """Dashboard local-first sem chamadas externas automaticas."""
        return service.dashboard()

    @app.get("/api/memories")
    def memories(
        service: AssistenteService = service_dependency,
        limite: int = memories_limit_query,
    ) -> list[dict[str, str]]:
        """Lista memorias recentes."""
        return service.listar_memorias(limite=limite)

    @app.post("/api/memories")
    def create_memory(
        payload: MemoryCreateRequest,
        service: AssistenteService = service_dependency,
    ) -> dict:
        """Cria memoria local."""
        return service.salvar_memoria(payload.titulo, payload.conteudo, payload.tags)

    @app.delete("/api/memories")
    def delete_memory(
        caminho: Path,
        service: AssistenteService = service_dependency,
    ) -> dict:
        """Apaga memoria dentro do vault."""
        try:
            return service.apagar_memoria(caminho)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/weather")
    def weather(service: AssistenteService = service_dependency) -> dict:
        """Consulta clima por acao explicita."""
        return _safe_call(service.clima)

    @app.get("/api/news")
    def news(
        service: AssistenteService = service_dependency,
        limite: int = news_limit_query,
        offset: int = news_offset_query,
    ) -> dict:
        """Consulta noticias por acao explicita."""
        return _safe_call(lambda: service.noticias(limite=limite, offset=offset))

    @app.post("/api/news/interest")
    def news_interest(
        payload: NewsInterestRequest,
        service: AssistenteService = service_dependency,
    ) -> dict[str, str]:
        """Registra noticia clicada/salva como sinal local de interesse."""
        return service.registrar_interesse_noticia(
            titulo=payload.titulo,
            link=payload.link,
            fonte=payload.fonte,
            resumo=payload.resumo,
            publicado=payload.publicado,
            tags=payload.tags,
        )

    @app.get("/api/music")
    def music(
        service: AssistenteService = service_dependency,
        dias: int = music_days_query,
    ) -> dict:
        """Consulta lancamentos musicais por acao explicita."""
        return _safe_call(lambda: service.musica(dias=dias))

    @app.post("/api/study-notes")
    def study_notes(
        payload: StudyRequest,
        service: AssistenteService = service_dependency,
    ) -> dict:
        """Cria nota de estudo local."""
        return _safe_call(
            lambda: service.criar_estudo(payload.tema, payload.conteudo, payload.perguntas)
        )

    @app.post("/api/chat")
    def chat(
        payload: ChatRequest,
        service: AssistenteService = service_dependency,
    ) -> dict:
        """Executa chat com opt-in explicito para envio a LLM externo."""
        return _safe_call(
            lambda: service.chat(
                payload.mensagem,
                permitir_llm_externo=payload.permitir_llm_externo,
            )
        )

    @app.get("/api/config/safe")
    def config_safe(service: AssistenteService = service_dependency) -> dict:
        """Retorna configuracao redigida."""
        return service.config_segura()

    @app.get("/api/privacy/data-map")
    def privacy_data_map(service: AssistenteService = service_dependency) -> list[dict]:
        """Retorna mapa LGPD de dados tratados."""
        return service.mapa_de_dados()

    @app.post("/api/privacy/export")
    def privacy_export(
        service: AssistenteService = service_dependency,
        destino: Path = export_destination_query,
    ) -> dict[str, str]:
        """Exporta dados locais para pacote JSON."""
        return service.exportar_privacidade(destino)

    @app.post("/api/privacy/purge")
    def privacy_purge(service: AssistenteService = service_dependency) -> dict:
        """Remove caches e indices gerados sem apagar notas."""
        return service.limpar_dados_gerados()

    @app.get("/api/google-calendar/status")
    def google_calendar_status(service: AssistenteService = service_dependency) -> dict:
        """Retorna status da integracao do Google Agenda."""
        return service.calendar_status()

    @app.get("/api/google-calendar/auth/start")
    def google_calendar_auth_start(
        service: AssistenteService = service_dependency,
    ) -> RedirectResponse:
        """Redireciona o usuario para o consentimento OAuth do Google."""
        return RedirectResponse(service.calendar_auth_url())

    @app.get("/api/google-calendar/auth/callback")
    def google_calendar_auth_callback(
        code: str,
        service: AssistenteService = service_dependency,
    ) -> RedirectResponse:
        """Completa OAuth e devolve o usuario para a GUI local."""
        service.complete_calendar_auth(code)
        return RedirectResponse("/?calendar=connected")

    @app.get("/api/google-calendar/events")
    def google_calendar_events(
        service: AssistenteService = service_dependency,
        limite: int = Query(default=5, ge=1, le=20),
    ) -> list[dict[str, str]]:
        """Lista proximos eventos do calendario primario."""
        return _safe_call(lambda: service.calendar_events(limite=limite))

    @app.post("/api/google-calendar/events")
    def google_calendar_create_event(
        payload: CalendarEventCreateRequest,
        service: AssistenteService = service_dependency,
    ) -> dict[str, str]:
        """Cria evento no calendario primario pela API oficial."""
        return _safe_call(
            lambda: service.criar_evento_agenda(
                titulo=payload.titulo,
                inicio=payload.inicio,
                fim=payload.fim,
                descricao=payload.descricao,
            )
        )

    static_dir = _static_dir()
    index_path = static_dir / "index.html"
    if static_dir.exists() and index_path.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        def root() -> FileResponse:
            """Entrega a GUI embutida quando o frontend foi buildado."""
            return FileResponse(index_path)

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            """Mantem o SPA funcional sem expor stack traces ao usuario final."""
            requested = static_dir / full_path
            if requested.exists() and requested.is_file():
                return FileResponse(requested)
            return FileResponse(index_path)

    return app


def _safe_call(func):
    """Converte erros internos em mensagens redigidas para o renderer."""
    try:
        return func()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(redact_sensitive(str(exc)))) from exc


def _static_dir() -> Path:
    """Resolve a pasta do frontend buildado quando a API serve a GUI em desenvolvimento."""
    custom = os.getenv("ASSISTENTE_STATIC_DIR")
    if custom:
        return Path(custom)
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "apps" / "desktop" / "dist"
