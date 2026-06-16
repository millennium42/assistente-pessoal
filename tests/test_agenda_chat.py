"""Testes das acoes de agenda acionadas pelo chat da APPA."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from assistente_pessoal.agenda_chat import AssistenteAgendaChat
from assistente_pessoal.agenda_google import EventoGoogleAgenda, ResultadoGoogleAgenda


class AgendaFake:
    """Agenda fake para validar o chat sem chamar a API real."""

    def __init__(self, eventos: list[EventoGoogleAgenda] | None = None) -> None:
        self.eventos = eventos or []
        self.evento_criado = None
        self.evento_cancelado = ""

    def criar_evento(self, evento) -> None:
        self.evento_criado = evento

    def obter_eventos_intervalo(self, *_args, **_kwargs) -> ResultadoGoogleAgenda:
        return ResultadoGoogleAgenda(eventos=self.eventos)

    def cancelar_evento(self, evento_id: str) -> None:
        self.evento_cancelado = evento_id


def test_chat_agenda_cria_evento_a_partir_de_frase() -> None:
    """Converte um pedido natural em NovoEventoGoogleAgenda."""
    agora = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    agenda = AgendaFake()

    resposta = AssistenteAgendaChat(agenda, "America/Sao_Paulo").tentar_executar(
        "marque consulta amanha as 14h por 45 minutos no Consultorio",
        agora=agora,
    )

    assert resposta is not None
    assert resposta.agenda_alterada is True
    assert agenda.evento_criado.titulo == "Consulta"
    assert agenda.evento_criado.local == "Consultorio"
    assert agenda.evento_criado.inicio == datetime(
        2026, 6, 16, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo")
    )
    assert agenda.evento_criado.fim - agenda.evento_criado.inicio == timedelta(minutes=45)


def test_chat_agenda_pede_data_e_horario_quando_faltam_dados() -> None:
    """Nao cria evento quando a frase ainda nao tem data ou hora suficiente."""
    agora = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    agenda = AgendaFake()

    resposta = AssistenteAgendaChat(agenda, "America/Sao_Paulo").tentar_executar(
        "marque consulta",
        agora=agora,
    )

    assert resposta is not None
    assert resposta.agenda_alterada is False
    assert resposta.texto == "Para qual dia, que horas e onde?"
    assert agenda.evento_criado is None


def test_chat_agenda_completa_evento_em_dois_turnos() -> None:
    """Mantem o pedido pendente e agenda quando o usuario responde hora e local."""
    agora = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    agenda = AgendaFake()
    chat = AssistenteAgendaChat(agenda, "America/Sao_Paulo")

    pergunta = chat.tentar_executar("Appa anote na minha agenda psicologo amanha", agora=agora)
    resposta = chat.tentar_executar("15h30 no Henrique Ballen, na vitta ceter", agora=agora)

    assert pergunta is not None
    assert pergunta.texto == "Que horas e onde?"
    assert resposta is not None
    assert resposta.agenda_alterada is True
    assert agenda.evento_criado.titulo == "Psicologo"
    assert agenda.evento_criado.local == "Henrique Ballen, na vitta ceter"
    assert agenda.evento_criado.inicio == datetime(
        2026, 6, 16, 15, 30, tzinfo=ZoneInfo("America/Sao_Paulo")
    )


def test_chat_agenda_cancela_evento_futuro_unico() -> None:
    """Cancela somente quando a busca encontra um candidato claro."""
    agora = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    agenda = AgendaFake(
        [
            EventoGoogleAgenda(
                titulo="Consulta",
                inicio="2026-06-16T14:00:00-03:00",
                fim="2026-06-16T15:00:00-03:00",
                link="",
                local="Consultorio",
                origem="",
                id="evt-1",
            )
        ]
    )

    resposta = AssistenteAgendaChat(agenda, "America/Sao_Paulo").tentar_executar(
        "desmarque minha consulta amanha",
        agora=agora,
    )

    assert resposta is not None
    assert resposta.agenda_alterada is True
    assert agenda.evento_cancelado == "evt-1"
    assert "desmarquei" in resposta.texto


def test_chat_agenda_nao_cancela_evento_ambiguo() -> None:
    """Evita excluir algo quando duas opcoes parecem corresponder ao pedido."""
    agora = datetime(2026, 6, 15, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    agenda = AgendaFake(
        [
            EventoGoogleAgenda(
                titulo="Consulta",
                inicio="2026-06-16T14:00:00-03:00",
                fim="2026-06-16T15:00:00-03:00",
                link="",
                local="Consultorio",
                origem="",
                id="evt-1",
            ),
            EventoGoogleAgenda(
                titulo="Consulta retorno",
                inicio="2026-06-16T16:00:00-03:00",
                fim="2026-06-16T17:00:00-03:00",
                link="",
                local="Consultorio",
                origem="",
                id="evt-2",
            ),
        ]
    )

    resposta = AssistenteAgendaChat(agenda, "America/Sao_Paulo").tentar_executar(
        "cancele consulta amanha",
        agora=agora,
    )

    assert resposta is not None
    assert resposta.agenda_alterada is False
    assert agenda.evento_cancelado == ""
    assert "mais de um compromisso" in resposta.texto
