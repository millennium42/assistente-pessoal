"""Testes da CLI Typer."""

from pathlib import Path

from typer.testing import CliRunner

from assistente_pessoal.cli import app


def test_cli_init_e_memoria(tmp_path: Path) -> None:
    """Inicializa configuracao e salva memoria via CLI."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"

    init_result = runner.invoke(
        app,
        ["--config", str(config_path), "init", "--vault", str(vault)],
    )
    salvar_result = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "memoria",
            "salvar",
            "Teste",
            "Conteudo de memoria",
        ],
    )

    assert init_result.exit_code == 0
    assert salvar_result.exit_code == 0
    assert list(vault.rglob("*.md"))


def test_cli_chat_sem_llm(tmp_path: Path) -> None:
    """Chat sem LLM configurado mostra fallback local."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"
    runner.invoke(app, ["--config", str(config_path), "init", "--vault", str(vault)])

    result = runner.invoke(app, ["--config", str(config_path), "chat", "oi"])

    assert result.exit_code == 0
    assert "LLM" in result.output
