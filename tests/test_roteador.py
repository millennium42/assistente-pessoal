"""Testes do roteador de comandos livres."""

from pathlib import Path

from assistente_pessoal.config import AppConfig
from assistente_pessoal.roteador import RoteadorComandos


def test_roteador_salva_memoria(tmp_path: Path) -> None:
    """Comando de memoria rapida cria uma nota no banco."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(config)

    resposta = roteador.executar("memorizar revisar algebra linear")

    assert "Memoria salva" in resposta
    assert roteador.memoria.buscar("revisar algebra linear")


def test_roteador_busca_memoria(tmp_path: Path) -> None:
    """Comando de busca encontra uma memoria salva anteriormente."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(config)
    roteador.executar("memorizar estudar derivadas")

    resposta = roteador.executar("buscar derivadas")

    assert "Memoria rapida" in resposta
