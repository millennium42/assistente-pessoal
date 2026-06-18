"""Testes do roteador de comandos livres."""

from pathlib import Path

from assistente_pessoal.agenda_google import EventoGoogleAgenda, ResultadoGoogleAgenda
from assistente_pessoal.config import AppConfig
from assistente_pessoal.roteador import RoteadorComandos


class GoogleAgendaFake:
    """Agenda fake usada pelo roteador sem side effects externos."""

    def __init__(self) -> None:
        self.evento_criado = None
        self.evento_atualizado = None
        self.eventos = [
            EventoGoogleAgenda(
                titulo="Consulta",
                inicio="2099-06-20T14:00:00-03:00",
                fim="2099-06-20T15:00:00-03:00",
                link="",
                local="Consultorio",
                origem="",
                id="evt-existente",
            )
        ]

    def criar_evento(self, evento):
        self.evento_criado = evento
        return EventoGoogleAgenda(
            titulo=evento.titulo,
            inicio=evento.inicio.isoformat(),
            fim=evento.fim.isoformat(),
            link="",
            local=evento.local,
            origem="",
            id="evt-roteador",
        )

    def atualizar_evento(self, evento_id: str, evento):
        self.evento_atualizado = (evento_id, evento)
        return EventoGoogleAgenda(
            titulo=evento.titulo,
            inicio=evento.inicio.isoformat(),
            fim=evento.fim.isoformat(),
            link="",
            local=evento.local,
            origem="",
            id=evento_id,
        )

    def obter_eventos_intervalo(self, *_args, **_kwargs) -> ResultadoGoogleAgenda:
        return ResultadoGoogleAgenda(eventos=self.eventos)


class GeminiEstruturadoFake:
    """Gemini fake que devolve payloads estruturados do novo roteador."""

    def __init__(self, respostas: list[dict]) -> None:
        self.respostas = respostas

    def disponivel(self) -> bool:
        return True

    def gerar_json(self, _prompt: str, **_kwargs) -> dict:
        return self.respostas.pop(0)


def test_roteador_salva_memoria(tmp_path: Path) -> None:
    """O Gemini pode mandar persistir uma anotacao livre no banco."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "criar",
                    "destino": "anotacoes",
                    "conteudo": "Revisar algebra linear",
                    "campos_estruturados": {},
                    "nivel_confianca": "alto",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Memoria salva.",
                }
            ]
        ),
    )

    resposta = roteador.executar("memorizar revisar algebra linear")

    assert "Memoria salva" in resposta
    assert roteador.memoria.buscar("revisar algebra linear")


def test_roteador_bloqueia_sem_gemini(tmp_path: Path) -> None:
    """Sem Gemini operacional, o roteador devolve a mensagem de bloqueio."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(config)

    resposta = roteador.executar("buscar derivadas")

    assert "Gemini" in resposta
    assert "bloqueado" in resposta.lower()


def test_roteador_chat_marca_compromisso_no_google_agenda(tmp_path: Path) -> None:
    """Pedidos de agenda no chat passam pelo roteador operacional."""
    config = AppConfig(db_path=tmp_path / "banco")
    agenda = GoogleAgendaFake()
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "responder",
                    "destino": "agenda_google",
                    "conteudo": "",
                    "campos_estruturados": {
                        "agenda": {
                            "acao": "criar",
                            "titulo": "Consulta",
                            "data": "2099-06-08",
                            "horario": "14:00",
                            "local": "Consultorio",
                            "duracao_minutos": 60,
                        }
                    },
                    "nivel_confianca": "alto",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Processando agenda.",
                }
            ]
        ),
        google_agenda=agenda,
    )

    resposta = roteador.executar_interacao("marque consulta em 2099-06-08 as 14h no consultorio")

    assert resposta.agenda_alterada is True
    assert agenda.evento_criado is not None
    assert agenda.evento_criado.titulo == "Consulta"


def test_roteador_usa_plano_do_gemini_para_atualizar_ultimo_evento(tmp_path: Path) -> None:
    """A edicao do ultimo evento deve seguir o plano estruturado devolvido pelo Gemini."""
    config = AppConfig(db_path=tmp_path / "banco")
    agenda = GoogleAgendaFake()
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "responder",
                    "destino": "agenda_google",
                    "conteudo": "",
                    "campos_estruturados": {
                        "agenda": {
                            "acao": "criar",
                            "titulo": "Jogo do Brasil",
                            "data": "2099-06-19",
                            "horario": "21:30",
                            "duracao_minutos": 60,
                            "local": "",
                        }
                    },
                    "nivel_confianca": "alto",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Evento anotado.",
                },
                {
                    "acao": "responder",
                    "destino": "agenda_google",
                    "conteudo": "",
                    "campos_estruturados": {
                        "agenda": {
                            "acao": "atualizar_ultimo",
                            "titulo": "Jogo do Brasil",
                            "duracao_minutos": 120,
                        }
                    },
                    "nivel_confianca": "alto",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Atualizei a duracao do jogo.",
                },
            ]
        ),
        google_agenda=agenda,
    )

    primeira = roteador.executar_interacao(
        "Amanha a noite tenho um compromisso, 21:30 jogo do Brasil"
    )
    segunda = roteador.executar_interacao("a partida tem duracao de 2 horas")

    assert primeira.agenda_alterada is True
    assert segunda.agenda_alterada is True
    assert agenda.evento_criado is not None
    assert agenda.evento_atualizado is not None
    _, evento_atualizado = agenda.evento_atualizado
    assert evento_atualizado.titulo == "Jogo do Brasil"
    assert evento_atualizado.fim.hour == 23
    assert evento_atualizado.fim.minute == 30


def test_roteador_usa_plano_do_gemini_para_editar_evento_existente(tmp_path: Path) -> None:
    """O Gemini pode escolher um evento existente da agenda para atualizar."""
    config = AppConfig(db_path=tmp_path / "banco")
    agenda = GoogleAgendaFake()
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "responder",
                    "destino": "agenda_google",
                    "conteudo": "",
                    "campos_estruturados": {
                        "agenda": {
                            "acao": "atualizar_existente",
                            "alvo": "Consulta",
                            "alvo_data": "2099-06-20",
                            "data": "2099-06-20",
                            "horario": "16:30",
                            "local": "Clinica nova",
                            "duracao_minutos": 90,
                        }
                    },
                    "nivel_confianca": "alto",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Ajustei sua consulta para o novo horario.",
                }
            ]
        ),
        google_agenda=agenda,
    )

    resposta = roteador.executar_interacao(
        "Mude minha consulta de 20/06 para 16h30 na clinica nova"
    )

    assert resposta.agenda_alterada is True
    assert "Ajustei sua consulta" in resposta.texto
    assert agenda.evento_atualizado is not None
    evento_id, evento = agenda.evento_atualizado
    assert evento_id == "evt-existente"
    assert evento.inicio.hour == 16
    assert evento.inicio.minute == 30
    assert evento.local == "Clinica nova"


def test_roteador_salva_interesse_leve_automaticamente(tmp_path: Path) -> None:
    """Interesses leves inferidos pelo Gemini entram na memoria adaptativa sem heuristica local."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "reforcar",
                    "destino": "memoria_comportamental",
                    "conteudo": (
                        "A usuaria demonstra interesse recorrente por IA aplicada a educacao."
                    ),
                    "campos_estruturados": {
                        "tipo_comportamento": "interesse",
                        "interesses": ["IA", "Educacao"],
                    },
                    "nivel_confianca": "medio",
                    "precisa_confirmacao": False,
                    "mensagem_ao_usuario": "Vou manter isso no seu contexto.",
                }
            ]
        ),
    )

    resposta = roteador.executar_interacao("Tenho lido bastante sobre IA na educacao")

    assert "contexto" in resposta.texto.lower()
    assert roteador.memoria.listar_interesses() == ["IA", "Educacao"]
    assert roteador.memoria.listar_comportamentos(limite=1)[0]["tipo"] == "interesse"


def test_roteador_exige_confirmacao_para_preferencia_sensivel(tmp_path: Path) -> None:
    """Inferencias mais sensiveis nao devem ser persistidas sem confirmacao explicita."""
    config = AppConfig(db_path=tmp_path / "banco")
    roteador = RoteadorComandos(
        config,
        llm=GeminiEstruturadoFake(
            [
                {
                    "acao": "criar",
                    "destino": "memoria_comportamental",
                    "conteudo": "Preferencia pessoal sensivel.",
                    "campos_estruturados": {"tipo_comportamento": "preferencia"},
                    "nivel_confianca": "medio",
                    "precisa_confirmacao": True,
                    "mensagem_ao_usuario": "Quero sua confirmacao antes de salvar isso.",
                }
            ]
        ),
    )

    resposta = roteador.executar_interacao("Guarde algo sensivel sobre mim")

    assert "confirmacao" in resposta.texto.lower()
    assert roteador.memoria.listar_comportamentos() == []
