"""Testes da API local."""

from pathlib import Path

from fastapi.testclient import TestClient

from assistente_pessoal.api.app import create_app
from assistente_pessoal.config import AppConfig, LLMConfig


def test_api_health_e_config_segura(tmp_path: Path) -> None:
    """API deve iniciar e nunca expor nome de variavel de segredo em claro."""
    config = AppConfig(
        vault_path=tmp_path / "vault",
        llm=LLMConfig(base_url="https://llm.test/v1", modelo="modelo", api_key_env="SECRET_ENV"),
    )
    client = TestClient(create_app(config))

    health = client.get("/api/health")
    safe_config = client.get("/api/config/safe")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert safe_config.status_code == 200
    assert safe_config.json()["llm"]["api_key_env"] == "***redacted***"


def test_api_memorias_cria_lista_e_apaga(tmp_path: Path) -> None:
    """Fluxo CRUD minimo de memoria fica restrito ao vault."""
    client = TestClient(create_app(AppConfig(vault_path=tmp_path / "vault")))

    created = client.post(
        "/api/memories",
        json={"titulo": "Teste", "conteudo": "Conteudo local", "tags": ["teste"]},
    )
    listed = client.get("/api/memories")
    caminho = created.json()["caminho"]
    deleted = client.delete("/api/memories", params={"caminho": caminho})

    assert created.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["titulo"] == "Teste"
    assert deleted.status_code == 200
    assert deleted.json()["apagado"] is True


def test_api_chat_exige_opt_in_para_llm_externo(tmp_path: Path) -> None:
    """LLM configurado nao deve receber dados sem consentimento explicito."""
    config = AppConfig(
        vault_path=tmp_path / "vault",
        llm=LLMConfig(base_url="https://llm.test/v1", modelo="modelo"),
    )
    client = TestClient(create_app(config))

    response = client.post("/api/chat", json={"mensagem": "oi", "permitir_llm_externo": False})

    assert response.status_code == 200
    body = response.json()
    assert body["llm_usado"] is False
    assert body["opt_in_necessario"] is True


def test_api_privacidade_exporta_e_limpa_dados_gerados(tmp_path: Path) -> None:
    """Exportacao e purge atendem portabilidade e limpeza de caches locais."""
    config = AppConfig(vault_path=tmp_path / "vault")
    client = TestClient(create_app(config))
    client.post("/api/memories", json={"titulo": "LGPD", "conteudo": "Dado local"})

    exported = client.post("/api/privacy/export", params={"destino": tmp_path / "exports"})
    purged = client.post("/api/privacy/purge")

    assert exported.status_code == 200
    assert Path(exported.json()["arquivo"]).exists()
    assert purged.status_code == 200
    assert "removidos" in purged.json()


def test_api_google_calendar_status_sem_credencial(tmp_path: Path, monkeypatch) -> None:
    """GUI deve conseguir saber que o googleAgenda ainda nao esta disponivel."""
    monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", str(tmp_path / "inexistente.json"))
    monkeypatch.setenv("GOOGLE_CALENDAR_TOKEN_FILE", str(tmp_path / "token.json"))
    client = TestClient(create_app(AppConfig(vault_path=tmp_path / "vault")))

    response = client.get("/api/google-calendar/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["connected"] is False


def test_api_registra_noticia_clicada_com_links_obsidian(tmp_path: Path) -> None:
    """Noticias clicadas devem virar notas relacionaveis no Obsidian."""
    client = TestClient(create_app(AppConfig(vault_path=tmp_path / "vault")))

    primeira = client.post(
        "/api/news/interest",
        json={
            "titulo": "IA na faculdade",
            "link": "https://exemplo.test/ia",
            "fonte": "Fonte Teste",
            "resumo": "Uso de inteligencia artificial na rotina de estudos.",
            "publicado": "2026-06-09T10:00:00",
            "tags": ["faculdade"],
        },
    )
    segunda = client.post(
        "/api/news/interest",
        json={
            "titulo": "IA em estudos",
            "link": "https://exemplo.test/ia-estudos",
            "fonte": "Fonte Teste",
            "resumo": "Ferramentas de inteligencia artificial para estudar melhor.",
            "publicado": "2026-06-09T11:00:00",
            "tags": ["faculdade"],
        },
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    texto = Path(segunda.json()["caminho"]).read_text(encoding="utf-8")
    assert "## Trecho copiado" in texto
    assert "Categoria:" in texto
    assert "[[" in texto


def test_api_dashboard_preserva_cards_centrais_da_v1(tmp_path: Path) -> None:
    """Dashboard deve expor contrato estavel para os cards centrais da GUI."""
    client = TestClient(create_app(AppConfig(vault_path=tmp_path / "vault")))

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    cards = response.json()["cards"]
    assert set(cards) >= {
        "clima_atual",
        "clima_futuro",
        "noticias",
        "musica",
        "memoria",
        "estudo",
        "chat",
        "google_calendar",
        "privacidade",
    }
    assert cards["clima_futuro"]["source"] == "weather.futuro"
