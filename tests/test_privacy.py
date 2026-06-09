"""Testes de privacidade e inventario LGPD."""

from pathlib import Path

from assistente_pessoal.application.privacy import data_map, export_privacy_bundle, safe_config
from assistente_pessoal.config import AppConfig, LLMConfig


def test_data_map_declara_segredos_e_dados_pessoais() -> None:
    """Inventario deve cobrir categorias sensiveis do app."""
    nomes = {item["nome"] for item in data_map()}

    assert "Chaves de API e tokens OAuth" in nomes
    assert "Memorias e notas Markdown" in nomes


def test_safe_config_redige_api_key_env(tmp_path: Path) -> None:
    """Configuracao segura nao pode entregar nomes de variaveis sensiveis ao renderer."""
    config = AppConfig(
        vault_path=tmp_path / "vault",
        llm=LLMConfig(api_key_env="SUPER_SECRET_ENV"),
    )

    redigida = safe_config(config)

    assert redigida["llm"]["api_key_env"] == "***redacted***"
    assert "SUPER_SECRET_ENV" not in str(redigida)


def test_export_privacy_bundle_inclui_markdown_sem_segredos(tmp_path: Path) -> None:
    """Exportacao deve ser portavel e usar configuracao redigida."""
    config = AppConfig(vault_path=tmp_path / "vault")
    nota = config.vault_path / "10_memoria" / "nota.md"
    nota.parent.mkdir(parents=True)
    nota.write_text("# Nota\n\nConteudo", encoding="utf-8")

    arquivo = export_privacy_bundle(config, tmp_path / "exports")

    texto = arquivo.read_text(encoding="utf-8")
    assert "Conteudo" in texto
    assert "OPENAI_API_KEY" not in texto
