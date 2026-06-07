"""Testes do roteador de comandos livres."""

from pathlib import Path

from assistente_pessoal.config import AppConfig
from assistente_pessoal.roteador import RoteadorComandos


def test_roteador_salva_memoria(tmp_path: Path) -> None:
    """Comando de memoria rapida cria uma nota no vault."""
    config = AppConfig(vault_path=tmp_path / "vault")
    roteador = RoteadorComandos(config)

    resposta = roteador.executar("memorizar revisar algebra linear")

    assert "Memoria salva" in resposta
    assert list((tmp_path / "vault").rglob("*.md"))


def test_roteador_busca_memoria(tmp_path: Path) -> None:
    """Comando de busca encontra uma memoria salva anteriormente."""
    config = AppConfig(vault_path=tmp_path / "vault")
    roteador = RoteadorComandos(config)
    roteador.executar("memorizar estudar derivadas")

    resposta = roteador.executar("buscar derivadas")

    assert "Memoria rapida" in resposta
