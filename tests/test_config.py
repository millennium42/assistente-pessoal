"""Testes da configuracao inicial do assistente."""

from pathlib import Path

from assistente_pessoal.config import carregar_config, criar_config_inicial


def test_criar_e_carregar_config_inicial(tmp_path: Path) -> None:
    """Garante que o config.toml inicial pode ser lido de volta."""
    config_path = tmp_path / "config" / "config.toml"
    vault_relativo = Path("vault")

    criar_config_inicial(
        caminho=config_path,
        vault_path=vault_relativo,
        cidade="Santa Maria, RS",
        latitude=-29.68,
        longitude=-53.81,
        timezone="America/Sao_Paulo",
    )
    config = carregar_config(config_path)

    assert config.vault_path == (config_path.parent / "vault").resolve()
    assert config.localizacao.cidade == "Santa Maria, RS"
    assert config.localizacao.latitude == -29.68
    assert config.fontes.noticias.the_news.habilitado is True
    assert "tecnoblog.net" in config.fontes.noticias.tech.rss[0]
    assert (
        config.google_agenda.token_path
        == (config_path.parent / ".assistente" / "google-calendar-token.json").resolve()
    )


def test_carregar_config_inexistente_retorna_padrao(tmp_path: Path) -> None:
    """Confirma que a aplicacao inicia com defaults se nao houver arquivo."""
    caminho = tmp_path / "nao-existe.toml"
    config = carregar_config(caminho)

    assert config.localizacao.timezone == "America/Sao_Paulo"
    assert config.vault_path == (tmp_path / "vault" / "AssistentePessoal").resolve()
