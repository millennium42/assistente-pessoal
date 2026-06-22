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
    _parse_data_hora_google,
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


@dataclass(frozen=True)
class EventoAgendaEmAndamento:
    """Mantem o ultimo evento criado para ajustes em turnos seguintes."""

    id: str
    titulo: str
    data_alvo: date
    horario: time
    local: str = ""
    duracao_minutos: int = 60


class AssistenteAgendaChat:
    """Interpreta pedidos simples de marcar e desmarcar compromissos."""

    def __init__(self, cliente_google, timezone: str, janela_cancelamento_dias: int = 60) -> None:
        self.cliente_google = cliente_google
        self.timezone = timezone
        self.janela_cancelamento_dias = janela_cancelamento_dias
        self.pedido_pendente: PedidoAgendaPendente | None = None
        self.evento_em_andamento: EventoAgendaEmAndamento | None = None

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
        if (
            self.evento_em_andamento is not None
            and not _tem_intencao_cancelar(normalizado)
            and not _tem_intencao_criar(normalizado)
            and _parece_atualizacao_agenda(comando, self.evento_em_andamento.titulo)
        ):
            return self._atualizar_evento_em_andamento(comando, agora_local)
        if _tem_intencao_cancelar(normalizado):
            self.pedido_pendente = None
            return self._cancelar(comando, agora_local)
        if _tem_intencao_criar(normalizado):
            return self._criar(comando, agora_local)
        return None

    def contexto_para_llm(self, agora: datetime | None = None) -> str:
        """Resume o estado atual da agenda para o Gemini decidir a proxima acao."""
        agora_local = _normalizar_agora(agora, self.timezone)
        linhas = [f"Agora local: {agora_local.isoformat(timespec='minutes')}"]
        if self.pedido_pendente is None:
            linhas.append("Pedido pendente: nenhum.")
        else:
            linhas.append(
                "Pedido pendente: "
                f"titulo={self.pedido_pendente.titulo!r}, "
                f"data={self.pedido_pendente.data_alvo}, "
                f"horario={self.pedido_pendente.horario}, "
                f"local={self.pedido_pendente.local!r}, "
                f"duracao_minutos={self.pedido_pendente.duracao_minutos}."
            )
        if self.evento_em_andamento is None:
            linhas.append("Ultimo evento em andamento: nenhum.")
        else:
            linhas.append(
                "Ultimo evento em andamento: "
                f"titulo={self.evento_em_andamento.titulo!r}, "
                f"data={self.evento_em_andamento.data_alvo}, "
                f"horario={self.evento_em_andamento.horario}, "
                f"local={self.evento_em_andamento.local!r}, "
                f"duracao_minutos={self.evento_em_andamento.duracao_minutos}."
            )
        if hasattr(self.cliente_google, "obter_eventos_intervalo"):
            try:
                resultado = self.cliente_google.obter_eventos_intervalo(
                    inicio=agora_local.astimezone(UTC),
                    fim=(agora_local + timedelta(days=7)).astimezone(UTC),
                    limite=8,
                )
            except Exception:
                resultado = None
            eventos = getattr(resultado, "eventos", []) if resultado is not None else []
            if eventos:
                linhas.append("Proximos eventos conhecidos:")
                for evento in eventos[:5]:
                    linhas.append(f"- {_resumir_evento(evento, self.timezone)}")
            else:
                linhas.append("Proximos eventos conhecidos: nenhum no recorte atual.")
        return "\n".join(linhas)

    def executar_plano(
        self,
        texto: str,
        plano: dict | None,
        mensagem_padrao: str = "",
        agora: datetime | None = None,
    ) -> ResultadoAgendaChat | None:
        """Aplica um plano de agenda decidido pelo Gemini."""
        if not plano:
            return self.tentar_executar(texto, agora=agora)
        acao = str(plano.get("acao") or "").strip().lower()
        if not acao or acao == "ignorar":
            return self.tentar_executar(texto, agora=agora)
        agora_local = _normalizar_agora(agora, self.timezone)
        if acao == "cancelar":
            self.pedido_pendente = None
            return self._cancelar(texto, agora_local)
        if acao == "atualizar_existente":
            return self._atualizar_evento_existente_via_plano(plano, mensagem_padrao, agora_local)
        if acao == "atualizar_ultimo" and self.evento_em_andamento is not None:
            return self._atualizar_evento_via_plano(plano, mensagem_padrao, agora_local)
        if acao in {"criar", "perguntar", "atualizar_ultimo"}:
            return self._criar_evento_via_plano(plano, mensagem_padrao, agora_local)
        return self.tentar_executar(texto, agora=agora_local)

    def _criar(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        pedido = PedidoAgendaPendente(
            titulo=_extrair_titulo_criacao(texto) or None,
            data_alvo=_extrair_data(texto, agora.date()),
            horario=_extrair_horario(texto),
            local=_extrair_local(texto),
            duracao_minutos=_extrair_duracao(texto) or 60,
        )
        pergunta = _pergunta_campos_faltantes(pedido)
        if pergunta:
            self.pedido_pendente = pedido
            return ResultadoAgendaChat(pergunta)
        return self._finalizar_criacao(pedido, agora)

    def _completar_pedido(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        pendente = self.pedido_pendente
        if pendente is None:
            return ResultadoAgendaChat(
                "Nao encontrei nenhum compromisso em aberto para eu completar."
            )
        titulo = _resolver_titulo_pendente(texto, pendente.titulo)
        data_alvo = _extrair_data(texto, agora.date()) or pendente.data_alvo
        horario = _extrair_horario(texto) or pendente.horario
        local = _extrair_local(texto) or pendente.local
        duracao = _extrair_duracao(texto) or pendente.duracao_minutos
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
            return ResultadoAgendaChat(
                "Ainda faltam alguns detalhes para eu colocar esse compromisso na agenda."
            )
        inicio = datetime.combine(pedido.data_alvo, pedido.horario, tzinfo=ZoneInfo(self.timezone))
        if inicio < agora:
            self.pedido_pendente = None
            return ResultadoAgendaChat(
                "Esse horario ja passou. Me diga uma data ou hora futura e eu ajusto para voce."
            )
        evento = NovoEventoGoogleAgenda(
            titulo=pedido.titulo,
            inicio=inicio,
            fim=inicio + timedelta(minutes=pedido.duracao_minutos),
            local=pedido.local,
            descricao=f"Criado pelo chat da APPA em {agora.isoformat(timespec='minutes')}.",
        )
        try:
            criado = self.cliente_google.criar_evento(evento)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        self.pedido_pendente = None
        self.evento_em_andamento = EventoAgendaEmAndamento(
            id=getattr(criado, "id", ""),
            titulo=pedido.titulo,
            data_alvo=pedido.data_alvo,
            horario=pedido.horario,
            local=pedido.local,
            duracao_minutos=pedido.duracao_minutos,
        )
        data_formatada = inicio.strftime("%d/%m/%Y")
        hora_formatada = inicio.strftime("%H:%M")
        complemento = f" em {pedido.local}" if pedido.local else ""
        return ResultadoAgendaChat(
            f'Anotei "{pedido.titulo}" para {data_formatada} as {hora_formatada}{complemento}.',
            agenda_alterada=True,
            referencia=pedido.data_alvo,
        )

    def _atualizar_evento_em_andamento(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        atual = self.evento_em_andamento
        if atual is None:
            return ResultadoAgendaChat("Nao encontrei um compromisso recente para ajustar agora.")
        titulo = _resolver_titulo_atualizacao(texto, atual.titulo)
        data_alvo = _extrair_data(texto, agora.date()) or atual.data_alvo
        horario = _extrair_horario(texto) or atual.horario
        local = _extrair_local(texto) or atual.local
        duracao = _extrair_duracao(texto) or atual.duracao_minutos
        inicio = datetime.combine(data_alvo, horario, tzinfo=ZoneInfo(self.timezone))
        if inicio < agora:
            return ResultadoAgendaChat(
                "Com esse ajuste o evento ficaria no passado. Me diga uma data ou hora futura."
            )
        evento = NovoEventoGoogleAgenda(
            titulo=titulo,
            inicio=inicio,
            fim=inicio + timedelta(minutes=duracao),
            local=local,
            descricao=f"Ajustado pelo chat da APPA em {agora.isoformat(timespec='minutes')}.",
        )
        try:
            if hasattr(self.cliente_google, "atualizar_evento") and atual.id:
                atualizado = self.cliente_google.atualizar_evento(atual.id, evento)
                evento_id = getattr(atualizado, "id", atual.id)
            else:
                criado = self.cliente_google.criar_evento(evento)
                evento_id = getattr(criado, "id", atual.id)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        self.evento_em_andamento = EventoAgendaEmAndamento(
            id=evento_id,
            titulo=titulo,
            data_alvo=data_alvo,
            horario=horario,
            local=local,
            duracao_minutos=duracao,
        )
        data_formatada = inicio.strftime("%d/%m/%Y")
        hora_formatada = inicio.strftime("%H:%M")
        complemento = f" em {local}" if local else ""
        return ResultadoAgendaChat(
            f'Atualizei "{titulo}" para {data_formatada} as {hora_formatada}{complemento}, '
            f"com duracao de {_formatar_duracao(duracao)}.",
            agenda_alterada=True,
            referencia=data_alvo,
        )

    def _criar_evento_via_plano(
        self,
        plano: dict,
        mensagem_padrao: str,
        agora: datetime,
    ) -> ResultadoAgendaChat:
        base = self.pedido_pendente or PedidoAgendaPendente()
        pedido = PedidoAgendaPendente(
            titulo=str(plano.get("titulo") or base.titulo or "").strip() or None,
            data_alvo=_data_plano(plano.get("data")) or base.data_alvo,
            horario=_horario_plano(plano.get("horario")) or base.horario,
            local=str(plano.get("local") or base.local or "").strip(),
            duracao_minutos=_duracao_plano(plano.get("duracao_minutos")) or base.duracao_minutos,
        )
        pergunta = _pergunta_campos_faltantes(pedido)
        if str(plano.get("acao") or "").strip().lower() == "perguntar" or pergunta:
            self.pedido_pendente = pedido
            return ResultadoAgendaChat(
                mensagem_padrao or pergunta or "Me passe o que falta e eu termino de organizar."
            )
        return self._finalizar_criacao(pedido, agora)

    def _atualizar_evento_via_plano(
        self,
        plano: dict,
        mensagem_padrao: str,
        agora: datetime,
    ) -> ResultadoAgendaChat:
        atual = self.evento_em_andamento
        if atual is None:
            return self._criar_evento_via_plano(plano, mensagem_padrao, agora)
        titulo = str(plano.get("titulo") or atual.titulo).strip() or atual.titulo
        data_alvo = _data_plano(plano.get("data")) or atual.data_alvo
        horario = _horario_plano(plano.get("horario")) or atual.horario
        local = str(plano.get("local") or atual.local).strip()
        duracao = _duracao_plano(plano.get("duracao_minutos")) or atual.duracao_minutos
        inicio = datetime.combine(data_alvo, horario, tzinfo=ZoneInfo(self.timezone))
        if inicio < agora:
            return ResultadoAgendaChat(
                "Com esse ajuste o evento ficaria no passado. Me diga uma data ou hora futura."
            )
        evento = NovoEventoGoogleAgenda(
            titulo=titulo,
            inicio=inicio,
            fim=inicio + timedelta(minutes=duracao),
            local=local,
            descricao=f"Ajustado pelo Gemini em {agora.isoformat(timespec='minutes')}.",
        )
        try:
            if hasattr(self.cliente_google, "atualizar_evento") and atual.id:
                atualizado = self.cliente_google.atualizar_evento(atual.id, evento)
                evento_id = getattr(atualizado, "id", atual.id)
            else:
                criado = self.cliente_google.criar_evento(evento)
                evento_id = getattr(criado, "id", atual.id)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        self.evento_em_andamento = EventoAgendaEmAndamento(
            id=evento_id,
            titulo=titulo,
            data_alvo=data_alvo,
            horario=horario,
            local=local,
            duracao_minutos=duracao,
        )
        data_formatada = inicio.strftime("%d/%m/%Y")
        hora_formatada = inicio.strftime("%H:%M")
        complemento = f" em {local}" if local else ""
        return ResultadoAgendaChat(
            mensagem_padrao
            or (
                f'Atualizei "{titulo}" para {data_formatada} as {hora_formatada}{complemento}, '
                f"com duracao de {_formatar_duracao(duracao)}."
            ),
            agenda_alterada=True,
            referencia=data_alvo,
        )

    def _atualizar_evento_existente_via_plano(
        self,
        plano: dict,
        mensagem_padrao: str,
        agora: datetime,
    ) -> ResultadoAgendaChat:
        consulta = str(plano.get("alvo") or "").strip()
        alvo_data = _data_plano(plano.get("alvo_data"))
        if not consulta and alvo_data is None:
            return ResultadoAgendaChat(
                "Consigo ajustar esse evento, mas preciso que voce me diga "
                "qual deles eu devo mexer."
            )
        candidatos = self._buscar_candidatos_agenda(consulta, alvo_data, agora)
        if not candidatos:
            return ResultadoAgendaChat(
                "Nao encontrei um evento correspondente na sua agenda para fazer esse ajuste."
            )
        if len(candidatos) > 1:
            opcoes = "; ".join(_resumir_evento(evento, self.timezone) for evento in candidatos[:4])
            return ResultadoAgendaChat(
                f"Encontrei mais de uma opcao para editar: {opcoes}. "
                "Me diga qual delas voce quer ajustar."
            )
        evento_base = candidatos[0]
        data_base = data_evento_google(evento_base)
        inicio_base = _parse_data_hora_google(evento_base.inicio, self.timezone)
        fim_base = _parse_data_hora_google(evento_base.fim, self.timezone)
        if data_base is None or inicio_base is None or fim_base is None:
            return ResultadoAgendaChat(
                "Encontrei o evento, mas faltaram dados suficientes para atualizar com seguranca."
            )
        duracao_base = max(15, int((fim_base - inicio_base).total_seconds() // 60) or 60)
        titulo = str(plano.get("titulo") or evento_base.titulo).strip() or evento_base.titulo
        data_alvo = _data_plano(plano.get("data")) or data_base
        horario = _horario_plano(plano.get("horario")) or inicio_base.time()
        local = str(plano.get("local") or evento_base.local).strip()
        duracao = _duracao_plano(plano.get("duracao_minutos")) or duracao_base
        inicio = datetime.combine(data_alvo, horario, tzinfo=ZoneInfo(self.timezone))
        if inicio < agora:
            return ResultadoAgendaChat(
                "Com esse ajuste o evento ficaria no passado. Me diga uma data ou hora futura."
            )
        novo_evento = NovoEventoGoogleAgenda(
            titulo=titulo,
            inicio=inicio,
            fim=inicio + timedelta(minutes=duracao),
            local=local,
            descricao=f"Ajustado pelo Gemini em {agora.isoformat(timespec='minutes')}.",
        )
        try:
            if hasattr(self.cliente_google, "atualizar_evento") and evento_base.id:
                atualizado = self.cliente_google.atualizar_evento(evento_base.id, novo_evento)
                evento_id = getattr(atualizado, "id", evento_base.id)
            else:
                criado = self.cliente_google.criar_evento(novo_evento)
                evento_id = getattr(criado, "id", evento_base.id)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        self.evento_em_andamento = EventoAgendaEmAndamento(
            id=evento_id,
            titulo=titulo,
            data_alvo=data_alvo,
            horario=horario,
            local=local,
            duracao_minutos=duracao,
        )
        data_formatada = inicio.strftime("%d/%m/%Y")
        hora_formatada = inicio.strftime("%H:%M")
        complemento = f" em {local}" if local else ""
        return ResultadoAgendaChat(
            mensagem_padrao
            or (
                f'Atualizei "{titulo}" para {data_formatada} as {hora_formatada}{complemento}, '
                f"com duracao de {_formatar_duracao(duracao)}."
            ),
            agenda_alterada=True,
            referencia=data_alvo,
        )

    def _buscar_candidatos_agenda(
        self,
        consulta: str,
        data_alvo: date | None,
        agora: datetime,
    ) -> list[EventoGoogleAgenda]:
        inicio_busca = agora.astimezone(UTC)
        fim_busca = inicio_busca + timedelta(days=self.janela_cancelamento_dias)
        try:
            resultado = self.cliente_google.obter_eventos_intervalo(
                inicio=inicio_busca,
                fim=fim_busca,
                limite=50,
            )
        except RuntimeError:
            return []
        if isinstance(resultado, ResultadoGoogleAgenda) and resultado.erro:
            return []
        eventos = resultado.eventos if isinstance(resultado, ResultadoGoogleAgenda) else []
        return _selecionar_candidatos(
            eventos,
            consulta=consulta,
            data_alvo=data_alvo,
            timezone=self.timezone,
            agora=agora,
        )

    def _cancelar(self, texto: str, agora: datetime) -> ResultadoAgendaChat:
        data_alvo = _extrair_data(texto, agora.date())
        consulta = _extrair_consulta_cancelamento(texto)
        if data_alvo is None and not consulta:
            return ResultadoAgendaChat(
                "Consigo desmarcar, mas preciso que voce me diga "
                "qual compromisso e por titulo ou data."
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
            return ResultadoAgendaChat(
                "Nao encontrei nenhum compromisso futuro com esses dados na sua agenda."
            )
        if len(candidatos) > 1:
            opcoes = "; ".join(_resumir_evento(evento, self.timezone) for evento in candidatos[:4])
            return ResultadoAgendaChat(
                f"Encontrei mais de uma opcao possivel: {opcoes}. "
                "Me diga o titulo ou o horario exato e eu desmarco o certo."
            )

        evento = candidatos[0]
        if not evento.id:
            return ResultadoAgendaChat(
                "Encontrei o compromisso, mas ele veio sem identificador valido do Google Agenda."
            )
        try:
            self.cliente_google.cancelar_evento(evento.id)
        except RuntimeError as exc:
            return ResultadoAgendaChat(str(exc))
        referencia = data_evento_google(evento) or data_alvo
        return ResultadoAgendaChat(
            f'Desmarquei "{evento.titulo}" de '
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
        re.search(r"\b(anote|anotar)\b", texto_normalizado) and "agenda" in texto_normalizado
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
                "proxima" in normalizado or "proximo" in normalizado or "que vem" in normalizado
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


def _extrair_duracao(texto: str) -> int | None:
    normalizado = _normalizar(texto)
    match = re.search(
        r"\b(?:por|duracao(?: de)?|dura(?:ndo)?)\s+(\d{1,3})\s*"
        r"(min|mins|minuto|minutos|h|hora|horas)\b",
        normalizado,
    )
    if not match:
        return None
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


def _resolver_titulo_pendente(texto: str, titulo_atual: str | None) -> str | None:
    candidato = _limpar_titulo_candidato(_extrair_titulo_criacao(texto))
    if not candidato:
        return titulo_atual
    if titulo_atual is None or _parece_correcao_titulo(texto):
        return candidato
    return titulo_atual


def _resolver_titulo_atualizacao(texto: str, titulo_atual: str) -> str:
    candidato = _limpar_titulo_candidato(_extrair_titulo_criacao(texto))
    if not candidato:
        return titulo_atual
    if _parece_correcao_titulo(texto):
        return candidato
    return titulo_atual


def _limpar_titulo_candidato(titulo: str) -> str:
    trabalho = re.sub(r"(?i),?\s*nao se confunda\b", "", titulo)
    trabalho = re.sub(r"(?i),?\s*nao confunda\b", "", trabalho)
    trabalho = re.sub(r"(?i),?\s*na verdade\b", "", trabalho)
    trabalho = trabalho.strip(" -:,.()")
    return _limpar_espacos(trabalho)


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
        evento for evento in eventos if evento_google_ainda_futuro(evento, timezone, agora=agora)
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
    if faltando_titulo:
        return "Qual compromisso voce quer que eu coloque na agenda?"
    if faltando_data:
        return "Para quando" + (" e em que horario?" if faltando_horario else "?")
    if faltando_horario:
        return "Que horario voce quer usar?"
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


def _parece_correcao_titulo(texto: str) -> bool:
    normalizado = _normalizar(texto)
    marcadores = (
        "nao se confunda",
        "nao confunda",
        "corrija",
        "corrige",
        "na verdade",
        "e nao",
    )
    return any(marcador in normalizado for marcador in marcadores)


def _parece_atualizacao_agenda(texto: str, titulo_atual: str) -> bool:
    if _extrair_horario(texto) is not None:
        return True
    if _extrair_duracao(texto) is not None:
        return True
    if _extrair_local(texto):
        return True
    if _parece_correcao_titulo(texto):
        return True
    return False


def _resumir_evento(evento: EventoGoogleAgenda, timezone: str) -> str:
    return f"{evento.titulo} ({formatar_data_hora_google(evento.inicio, timezone)})"


def _formatar_duracao(duracao_minutos: int) -> str:
    if duracao_minutos % 60 == 0:
        horas = duracao_minutos // 60
        return f"{horas} hora" + ("" if horas == 1 else "s")
    return f"{duracao_minutos} minutos"


def _data_plano(valor: object) -> date | None:
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _horario_plano(valor: object) -> time | None:
    texto = str(valor or "").strip()
    if not texto:
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})$", texto)
    if not match:
        return None
    hora = int(match.group(1))
    minuto = int(match.group(2))
    if 0 <= hora <= 23 and 0 <= minuto <= 59:
        return time(hour=hora, minute=minuto)
    return None


def _duracao_plano(valor: object) -> int | None:
    if valor in (None, ""):
        return None
    try:
        minutos = int(valor)
    except (TypeError, ValueError):
        return None
    return max(15, min(minutos, 720))


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
