"""Testes da CLI Typer."""

from pathlib import Path

from typer.testing import CliRunner

from assistente_pessoal.cli import app
from assistente_pessoal.noticias import LIMITE_PADRAO_NOTICIAS


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
                e_hoje=False,
                temperatura_referencia=21.0,
                sensacao=None,
                vento=12.0,
                maxima=26.0,
                minima=16.0,
                chuva=10.0,
                codigo_tempo=1,
            )

    monkeypatch.setattr("assistente_pessoal.cli.ClienteClima", ClienteClimaFake)

    result = runner.invoke(app, ["--config", str(config_path), "clima", "--dia", "amanha"])

    assert result.exit_code == 0
    assert "2026-06-09" in result.output


def test_cli_noticias_usa_limite_padrao_100(monkeypatch, tmp_path: Path) -> None:
    """Comando de noticias usa 100 itens quando --limite nao e informado."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"
    runner.invoke(app, ["--config", str(config_path), "init", "--vault", str(vault)])
    chamadas: dict[str, int] = {}

    class ClienteNoticiasFake:
        """Cliente fake para capturar o limite padrao."""

        def listar(self, config, limite: int):
            """Registra o limite e nao chama fontes externas."""
            chamadas["limite"] = limite
            return []

    monkeypatch.setattr("assistente_pessoal.cli.ClienteNoticias", ClienteNoticiasFake)

    result = runner.invoke(app, ["--config", str(config_path), "noticias"])

    assert result.exit_code == 0
    assert chamadas["limite"] == LIMITE_PADRAO_NOTICIAS


def test_cli_gui_troca_porta_ocupada(monkeypatch, tmp_path: Path) -> None:
    """Quando a porta padrao estiver ocupada, a CLI escolhe outra e avisa."""
    runner = CliRunner()
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"
    runner.invoke(app, ["--config", str(config_path), "init", "--vault", str(vault)])

    chamadas: dict[str, object] = {}

    def porta_fake(host: str, porta_preferida: int, tentativas: int = 20) -> int:
        """Simula uma porta padrao ocupada e libera a proxima."""
        assert host == "127.0.0.1"
        assert porta_preferida == 8765
        return 8766

    def iniciar_fake(config, host: str, port: int) -> None:
        """Captura a porta final sem subir o servidor real."""
        chamadas["host"] = host
        chamadas["port"] = port

    monkeypatch.setattr("assistente_pessoal.gui.resolver_porta_dashboard", porta_fake)
    monkeypatch.setattr("assistente_pessoal.gui.iniciar_dashboard", iniciar_fake)

    result = runner.invoke(app, ["--config", str(config_path), "gui"])

    assert result.exit_code == 0
    assert "Porta 8765 ocupada" in result.output
    assert chamadas["port"] == 8766
