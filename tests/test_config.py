"""Testes da configuracao inicial do assistente."""

from pathlib import Path

from assistente_pessoal.config import carregar_config, criar_config_inicial


def test_criar_e_carregar_config_inicial(tmp_path: Path) -> None:
    """Garante que o config.toml inicial pode ser lido de volta."""
    config_path = tmp_path / "config.toml"
    vault = tmp_path / "vault"

    criar_config_inicial(
        caminho=config_path,
        vault_path=vault,
        cidade="Santa Maria, RS",
        latitude=-29.68,
        longitude=-53.81,
        timezone="America/Sao_Paulo",
    )
    config = carregar_config(config_path)

    assert config.vault_path == vault
    assert config.localizacao.cidade == "Santa Maria, RS"
    assert config.localizacao.latitude == -29.68
    assert config.fontes.incluir_the_news_tecnologia is True
    assert "tecnoblog.net" in config.fontes.rss[0]


def test_carregar_config_inexistente_retorna_padrao(tmp_path: Path) -> None:
    """Confirma que a aplicacao inicia com defaults se nao houver arquivo."""
    config = carregar_config(tmp_path / "nao-existe.toml")

    assert config.localizacao.timezone == "America/Sao_Paulo"
    assert config.vault_path.name == "AssistentePessoal"
