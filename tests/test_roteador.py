"""Testes do roteador de comandos livres."""

from pathlib import Path

from assistente_pessoal.config import AppConfig
from assistente_pessoal.roteador import RoteadorComandos


class GoogleAgendaFake:
    """Agenda fake usada pelo roteador sem side effects externos."""

    def __init__(self) -> None:
        self.evento_criado = None

    def criar_evento(self, evento) -> None:
        self.evento_criado = evento


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


def test_roteador_chat_marca_compromisso_no_google_agenda(tmp_path: Path) -> None:
    """Pedidos de agenda no chat passam pelo roteador operacional."""
    config = AppConfig(db_path=tmp_path / "banco")
    agenda = GoogleAgendaFake()
    roteador = RoteadorComandos(config, google_agenda=agenda)

    resposta = roteador.executar_interacao("marque consulta em 2099-06-08 as 14h no consultorio")

    assert resposta.agenda_alterada is True
    assert agenda.evento_criado is not None
    assert agenda.evento_criado.titulo == "Consulta"
