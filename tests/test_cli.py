"""Testes da CLI Typer."""

from pathlib import Path

from typer.testing import CliRunner

from assistente_pessoal.cli import app


def test_cli_init_e_memoria(tmp_path: Path) -> None:
    """Inicializa configuracao e salva memoria via CLI."""
    runner = CliRunner()
    config_path = tmp_path / "config" / "config.toml"
    vault = Path("vault")

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
    assert list((config_path.parent / "vault").rglob("*.md"))


def test_cli_chat_sem_llm(tmp_path: Path) -> None:
    """Chat sem LLM configurado mostra fallback local."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"
    runner.invoke(app, ["--config", str(config_path), "init", "--vault", str(vault)])

    result = runner.invoke(app, ["--config", str(config_path), "chat", "oi"])

    assert result.exit_code == 0
    assert "LLM" in result.output


def test_cli_clima_aceita_dia(monkeypatch, tmp_path: Path) -> None:
    """Propaga o argumento de dia para o cliente de clima."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"
    runner.invoke(app, ["--config", str(config_path), "init", "--vault", str(vault)])

    class ClienteClimaFake:
        """Cliente fake para inspecionar o argumento do comando."""

        def obter_previsao(self, localizacao, dia=None):
            """Devolve um resumo simples sem chamar a API real."""
            from assistente_pessoal.clima import PrevisaoClima

            assert dia == "amanha"
            return PrevisaoClima(
                cidade=localizacao.cidade,
                data_alvo=__import__("datetime").date(2026, 6, 9),
                temperatura_atual=20.0,
                sensacao=19.0,
                vento=12.0,
                maxima=26.0,
                minima=16.0,
                chuva=10.0,
            )

    monkeypatch.setattr("assistente_pessoal.cli.ClienteClima", ClienteClimaFake)

    result = runner.invoke(app, ["--config", str(config_path), "clima", "--dia", "amanha"])

    assert result.exit_code == 0
    assert "2026-06-09" in result.output
