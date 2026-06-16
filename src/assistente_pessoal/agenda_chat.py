"""Acoes de agenda acionadas por texto livre no chat da APPA."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from assistente_pessoal.agenda_google import (
    EventoGoogleAgenda,
    NovoEventoGoogleAgenda,
    ResultadoGoogleAgenda,
    data_evento_google,
    evento_google_ainda_futuro,
    formatar_data_hora_google,
)


@dataclass(frozen=True)
class ResultadoAgendaChat:
    """Resultado de uma acao de agenda feita pelo chat."""

    texto: str
    agenda_alterada: bool = False
    referencia: date | None = None


@dataclass(frozen=True)
class PedidoAgendaPendente:
    """Rascunho de compromisso aguardando informacoes do usuario."""

    titulo: str | None = None
    data_alvo: date | None = None
    horario: time | None = None
    local: str = ""
    duracao_minutos: int = 60


class AssistenteAgendaChat:
    """Interpreta pedidos simples de marcar e desmarcar compromissos."""

    def __init__(self, cliente_google, timezone: str, janela_cancelamento_dias: int = 60) -> None:
        self.cliente_google = cliente_google
        self.timezone = timezone
        self.janela_cancelamento_dias = janela_cancelamento_dias
        self.pedido_pendente: PedidoAgendaPendente | None = None

    def tentar_executar(
        self,
        texto: str,
        agora: datetime | None = None,
    ) -> ResultadoAgendaChat | None:
        """Executa uma acao de agenda se o texto trouxer uma intencao conhecida."""
        comando = texto.strip()
        if not comando:
            return None
        normalizado = _normalizar(comando)
        agora_local = _normalizar_agora(agora, self.timezone)
        if (
            self.pedido_pendente is not None
            and not _tem_intencao_cancelar(normalizado)
            and not _tem_intencao_criar(normalizado)
        ):
            return self._completar_pedido(comando, agora_local)
        if _tem_intencao_cancelar(normalizado):
            self.pedido_pendente = None
            return self._cancelar(comando, agora_local)
        if _tem_intencao_criar(normalizado):
            return self._criar(comando, agora_local)
        return None

    def _criar(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        pedido = PedidoAgendaPendente(
            titulo=_extrair_titulo_criacao(texto) or None,
            data_alvo=_extrair_data(texto, agora.date()),
            horario=_extrair_horario(texto),
            local=_extrair_local(texto),
            duracao_minutos=_extrair_duracao(texto),
        )
        pergunta = _pergunta_campos_faltantes(pedido)
        if pergunta:
            self.pedido_pendente = pedido
            return ResultadoAgendaChat(pergunta)
        return self._finalizar_criacao(pedido, agora)

    def _completar_pedido(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        pendente = self.pedido_pendente
        if pendente is None:
            return ResultadoAgendaChat("Nao encontrei um compromisso pendente para completar.")
        titulo = pendente.titulo or _extrair_titulo_criacao(texto) or None
        data_alvo = _extrair_data(texto, agora.date()) or pendente.data_alvo
        horario = _extrair_horario(texto) or pendente.horario
        local = _extrair_local(texto) or pendente.local
        duracao = _extrair_duracao(texto)
        if duracao == 60:
            duracao = pendente.duracao_minutos
        pedido = PedidoAgendaPendente(
            titulo=titulo,
            data_alvo=data_alvo,
            horario=horario,
            local=local,
            duracao_minutos=duracao,
        )
        pergunta = _pergunta_campos_faltantes(pedido)
        if pergunta:
            self.pedido_pendente = pedido
            return ResultadoAgendaChat(pergunta)
        return self._finalizar_criacao(pedido, agora)

    def _finalizar_criacao(
        self,
        pedido: PedidoAgendaPendente,
        agora: datetime,
    ) -> ResultadoAgendaChat:
        if pedido.titulo is None or pedido.data_alvo is None or pedido.horario is None:
            return ResultadoAgendaChat("Ainda faltam dados para marcar esse compromisso.")
        inicio = datetime.combine(pedido.data_alvo, pedido.horario, tzinfo=ZoneInfo(self.timezone))
        if inicio < agora:
            self.pedido_pendente = None
            return ResultadoAgendaChat(
                "Esse horario ja passou. Me diga uma data e hora futuras para eu marcar."
            )
        evento = NovoEventoGoogleAgenda(
            titulo=pedido.titulo,
            inicio=inicio,
            fim=inicio + timedelta(minutes=pedido.duracao_minutos),
            local=pedido.local,
            descricao=f"Criado pelo chat da APPA em {agora.isoformat(timespec='minutes')}.",
        )
        try:
            self.cliente_google.criar_evento(evento)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        self.pedido_pendente = None
        data_formatada = inicio.strftime("%d/%m/%Y")
        hora_formatada = inicio.strftime("%H:%M")
        complemento = f" em {pedido.local}" if pedido.local else ""
        return ResultadoAgendaChat(
            f'Pronto, marquei "{pedido.titulo}" para '
            f"{data_formatada} as {hora_formatada}{complemento}.",
            agenda_alterada=True,
            referencia=pedido.data_alvo,
        )

    def _cancelar(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        data_alvo = _extrair_data(texto, agora.date())
        consulta = _extrair_consulta_cancelamento(texto)
        if data_alvo is None and not consulta:
            return ResultadoAgendaChat(
                "Consigo desmarcar, mas preciso identificar o compromisso por titulo ou data."
            )

        inicio_busca = agora.astimezone(UTC)
        fim_busca = inicio_busca + timedelta(days=self.janela_cancelamento_dias)
        try:
            resultado = self.cliente_google.obter_eventos_intervalo(
                inicio=inicio_busca,
                fim=fim_busca,
                limite=50,
            )
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        if isinstance(resultado, ResultadoGoogleAgenda) and resultado.erro:
            return ResultadoAgendaChat(f"Nao consegui consultar sua agenda: {resultado.erro}")
        eventos = resultado.eventos if isinstance(resultado, ResultadoGoogleAgenda) else []
        candidatos = _selecionar_candidatos(
            eventos,
            consulta=consulta,
            data_alvo=data_alvo,
            timezone=self.timezone,
            agora=agora,
        )
        if not candidatos:
            return ResultadoAgendaChat("Nao encontrei um compromisso futuro com esses dados.")
        if len(candidatos) > 1:
            opcoes = "; ".join(_resumir_evento(evento, self.timezone) for evento in candidatos[:4])
            return ResultadoAgendaChat(
                f"Encontrei mais de um compromisso possivel: {opcoes}. "
                "Me diga o titulo ou horario exato para eu desmarcar com seguranca."
            )

        evento = candidatos[0]
        if not evento.id:
            return ResultadoAgendaChat(
                "Encontrei o compromisso, mas ele veio sem identificador do Google Agenda."
            )
        try:
            self.cliente_google.cancelar_evento(evento.id)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        referencia = data_evento_google(evento) or data_alvo
        return ResultadoAgendaChat(
            f'Pronto, desmarquei "{evento.titulo}" de '
            f"{formatar_data_hora_google(evento.inicio, self.timezone)}.",
            agenda_alterada=True,
            referencia=referencia,
        )


def _tem_intencao_criar(texto_normalizado: str) -> bool:
    padrao = (
        r"\b(marque|marcar|agende|agendar|crie|criar|adicione|adicionar|"
        r"coloque|colocar)\b"
    )
    if re.search(padrao, texto_normalizado) or texto_normalizado.startswith("agenda "):
        return True
    return bool(
        re.search(r"\b(anote|anotar)\b", texto_normalizado)
        and "agenda" in texto_normalizado
    )


def _tem_intencao_cancelar(texto_normalizado: str) -> bool:
    padrao = (
        r"\b(desmarque|desmarcar|cancele|cancelar|remova|remover|apague|apagar|"
        r"exclua|excluir)\b"
    )
    return bool(re.search(padrao, texto_normalizado))


def _extrair_data(texto: str, hoje: date) -> date | None:
    normalizado = _normalizar(texto)
    if "depois de amanha" in normalizado:
        return hoje + timedelta(days=2)
    if "amanha" in normalizado:
        return hoje + timedelta(days=1)
    if re.search(r"\bhoje\b", normalizado):
        return hoje

    iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", normalizado)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    data_curta = re.search(
        r"(?:\bdia\s+)?\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b",
        normalizado,
    )
    if data_curta:
        dia = int(data_curta.group(1))
        mes = int(data_curta.group(2))
        ano_texto = data_curta.group(3)
        ano = hoje.year
        if ano_texto:
            ano = int(ano_texto)
            if ano < 100:
                ano += 2000
        try:
            data = date(ano, mes, dia)
        except ValueError:
            return None
        if not ano_texto and data < hoje:
            data = date(ano + 1, mes, dia)
        return data

    for nome, indice in _DIAS_SEMANA.items():
        if re.search(rf"\b{re.escape(nome)}\b", normalizado):
            dias = (indice - hoje.weekday()) % 7
            if dias == 0 and (
                "proxima" in normalizado
                or "proximo" in normalizado
                or "que vem" in normalizado
            ):
                dias = 7
            return hoje + timedelta(days=dias)
    return None


def _extrair_horario(texto: str) -> time | None:
    normalizado = _normalizar(texto)
    padroes = [
        r"(?:\bas|\bpara as|\bpara|por volta das|por volta de)\s+(\d{1,2})(?:[:h](\d{2}))?\b",
        r"\b(\d{1,2})h(\d{2})?\b",
    ]
    for padrao in padroes:
        match = re.search(padrao, normalizado)
        if not match:
            continue
        hora = int(match.group(1))
        minuto = int(match.group(2) or 0)
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return time(hour=hora, minute=minuto)
    return None


def _extrair_duracao(texto: str) -> int:
    normalizado = _normalizar(texto)
    match = re.search(
        r"\b(?:por|duracao(?: de)?|dura(?:ndo)?)\s+(\d{1,3})\s*"
        r"(min|mins|minuto|minutos|h|hora|horas)\b",
        normalizado,
    )
    if not match:
        return 60
    quantidade = int(match.group(1))
    unidade = match.group(2)
    if unidade in {"h", "hora", "horas"}:
        return max(15, min(quantidade * 60, 720))
    return max(15, min(quantidade, 720))


def _extrair_local(texto: str) -> str:
    texto_limpo = re.sub(
        r"(?i)\b(?:na|no|em)?\s*(?:minha\s+|meu\s+)?agenda\b",
        " ",
        texto,
    )
    match = re.search(
        r"\b(?:local|lugar|no|na|em)\s+(.+)$",
        texto_limpo,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    local = _remover_fragmentos_temporais(match.group(1))
    local = re.sub(
        r"(?i)\b(?:por|duracao(?: de)?|dura(?:ndo)?)\s+\d{1,3}\s*"
        r"(?:min|mins|minuto|minutos|h|hora|horas)\b",
        " ",
        local,
    )
    local = _limpar_espacos(local.strip(" -:,."))
    if not local or re.match(r"^\d", local):
        return ""
    return local[:1].upper() + local[1:]


def _extrair_titulo_criacao(texto: str) -> str:
    trabalho = _remover_ruido_inicial(texto)
    trabalho = re.sub(
        r"(?i)\b(marque|marcar|agende|agendar|anote|anotar|agenda|crie|criar|"
        r"adicione|adicionar|coloque|colocar)\b",
        "",
        trabalho,
        count=1,
    )
    trabalho = re.sub(
        r"(?i)\b(?:na|no|em)?\s*(?:minha\s+|meu\s+)?agenda\b",
        " ",
        trabalho,
    )
    trabalho = _remover_fragmentos_temporais(trabalho)
    local = _extrair_local(texto)
    if local:
        trabalho = re.sub(
            rf"(?i)\b(?:local|lugar|no|na|em)\s+{re.escape(local)}\b",
            "",
            trabalho,
            count=1,
        )
    trabalho = re.sub(r"(?i)\b(?:um|uma|o|a|meu|minha)\b", " ", trabalho)
    trabalho = re.sub(r"(?i)\b(?:em|no|na|para|as|às)\s*$", " ", trabalho)
    titulo = _limpar_espacos(trabalho.strip(" -:,."))
    if _normalizar(titulo) in {"", "compromisso", "evento", "agenda"}:
        return ""
    return titulo[:1].upper() + titulo[1:]


def _extrair_consulta_cancelamento(texto: str) -> str:
    trabalho = _remover_ruido_inicial(texto)
    trabalho = re.sub(
        r"(?i)\b(desmarque|desmarcar|cancele|cancelar|remova|remover|apague|apagar|exclua|excluir)\b",
        "",
        trabalho,
        count=1,
    )
    trabalho = _remover_fragmentos_temporais(trabalho)
    trabalho = re.sub(
        r"(?i)\b(meu|minha|meus|minhas|o|a|os|as|um|uma|compromisso|evento|agenda)\b",
        " ",
        trabalho,
    )
    return _limpar_espacos(trabalho.strip(" -:,."))


def _selecionar_candidatos(
    eventos: list[EventoGoogleAgenda],
    consulta: str,
    data_alvo: date | None,
    timezone: str,
    agora: datetime,
) -> list[EventoGoogleAgenda]:
    futuros = [
        evento
        for evento in eventos
        if evento_google_ainda_futuro(evento, timezone, agora=agora)
    ]
    if data_alvo is not None:
        futuros = [evento for evento in futuros if data_evento_google(evento) == data_alvo]
    tokens = _tokens_busca(consulta)
    if not tokens:
        return sorted(futuros, key=lambda evento: evento.inicio)

    pontuados: list[tuple[int, EventoGoogleAgenda]] = []
    for evento in futuros:
        texto_evento = f"{evento.titulo} {evento.local}"
        tokens_evento = set(_tokens_busca(texto_evento))
        pontuacao = sum(1 for token in tokens if token in tokens_evento)
        if pontuacao > 0:
            pontuados.append((pontuacao, evento))
    if not pontuados:
        return []
    maior = max(pontuacao for pontuacao, _evento in pontuados)
    return [evento for pontuacao, evento in pontuados if pontuacao == maior]


def _tokens_busca(texto: str) -> list[str]:
    normalizado = _normalizar(texto)
    tokens = re.findall(r"\b[a-z0-9]{3,}\b", normalizado)
    return [token for token in tokens if token not in _STOPWORDS_BUSCA]


def _pergunta_campos_faltantes(pedido: PedidoAgendaPendente) -> str:
    faltando_titulo = not pedido.titulo
    faltando_data = pedido.data_alvo is None
    faltando_horario = pedido.horario is None
    faltando_local = not pedido.local
    if faltando_titulo:
        return "Qual compromisso devo colocar na agenda?"
    if faltando_data and faltando_horario and faltando_local:
        return "Para qual dia, que horas e onde?"
    if faltando_data and faltando_horario:
        return "Para qual dia e que horas?"
    if faltando_data and faltando_local:
        return "Para qual dia e onde?"
    if faltando_horario and faltando_local:
        return "Que horas e onde?"
    if faltando_data:
        return "Para qual dia?"
    if faltando_horario:
        return "Que horas?"
    if faltando_local:
        return "Onde vai ser?"
    return ""


def _remover_ruido_inicial(texto: str) -> str:
    texto = re.sub(r"(?i)\bappa\b", " ", texto)
    return re.sub(
        r"(?i)\b(por favor|favor|pode|voce pode|você pode|quero|preciso|para mim|pra mim)\b",
        " ",
        texto,
    )


def _remover_fragmentos_temporais(texto: str) -> str:
    trabalho = texto
    substituicoes = [
        r"(?i)\bdepois de amanh[aã]\b",
        r"(?i)\bamanh[aã]\b",
        r"(?i)\bhoje\b",
        r"(?i)\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"(?i)\b(?:dia\s+)?\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
        r"(?i)(?:\b[aà]s|\bpara [aà]s|\bpara|por volta das|por volta de)\s+"
        r"\d{1,2}(?:[:h]\d{0,2})?\b",
        r"(?i)\b\d{1,2}h\d{0,2}\b",
        r"(?i)\b(?:por|duracao(?: de)?|duração(?: de)?|dura(?:ndo)?)\s+\d{1,3}\s*"
        r"(?:min|mins|minuto|minutos|h|hora|horas)\b",
    ]
    for padrao in substituicoes:
        trabalho = re.sub(padrao, " ", trabalho)
    for nome in _DIAS_SEMANA:
        trabalho = re.sub(rf"(?i)\b{re.escape(nome)}\b", " ", trabalho)
    trabalho = re.sub(r"(?i)\b(proxima|proximo|que vem)\b", " ", trabalho)
    return trabalho


def _resumir_evento(evento: EventoGoogleAgenda, timezone: str) -> str:
    return f"{evento.titulo} ({formatar_data_hora_google(evento.inicio, timezone)})"


def _normalizar_agora(agora: datetime | None, timezone: str) -> datetime:
    tzinfo = ZoneInfo(timezone)
    referencia = agora or datetime.now(tzinfo)
    if referencia.tzinfo is None:
        return referencia.replace(tzinfo=tzinfo)
    return referencia.astimezone(tzinfo)


def _normalizar(texto: str) -> str:
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caractere) != "Mn"
    )
    return _limpar_espacos(sem_acentos)


def _limpar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


_DIAS_SEMANA = {
    "segunda": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terca-feira": 1,
    "terça": 1,
    "terça-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

_STOPWORDS_BUSCA = {
    "agenda",
    "aos",
    "com",
    "das",
    "dos",
    "evento",
    "meu",
    "meus",
    "minha",
    "minhas",
    "para",
    "por",
    "uma",
}
