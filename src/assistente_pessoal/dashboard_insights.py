"""Gera resumos inteligentes para a aba principal do dashboard."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from assistente_pessoal.agenda_google import EventoGoogleAgenda, formatar_data_hora_google
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
from assistente_pessoal.gemini import ClienteGemini
from assistente_pessoal.memoria import InteracaoNoticiaMemoria
from assistente_pessoal.noticias import Noticia, rotulo_tempo_publicacao


@dataclass(frozen=True)
class InsightCard:
    """Representa um card narrativo da aba principal."""

    titulo: str
    resumo: str
    bullets: list[str]


@dataclass(frozen=True)
class DashboardInsights:
    """Agrupa os tres resumos exibidos no topo do dashboard."""

    agenda: InsightCard
    noticias: InsightCard
    clima: InsightCard
    motor: str


class GeradorInsightsDashboard:
    """Produz insights locais e tenta refiná-los com Gemini quando disponível."""

    def __init__(self, config: AppConfig, cliente_gemini: ClienteGemini | None = None) -> None:
        self.config = config
        self.gemini = cliente_gemini or ClienteGemini(config.llm)
        self._cache_fingerprint: str | None = None
        self._cache_resultado: DashboardInsights | None = None

    def gerar(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        timezone: str,
        atualizado_em: str,
    ) -> DashboardInsights:
        """Monta insights com cache por conteudo para nao repetir chamadas ao Gemini."""
        fallback = self._fallback_local(
            agenda_google=agenda_google,
            noticias=noticias,
            noticias_por_grupo=noticias_por_grupo,
            previsao=previsao,
            clima_ontem=clima_ontem,
            perfil_pessoal=perfil_pessoal,
            interesses_usuario=interesses_usuario,
            noticias_relevantes=noticias_relevantes,
            timezone=timezone,
        )
        fingerprint = self._fingerprint(
            agenda_google=agenda_google,
            noticias=noticias,
            noticias_por_grupo=noticias_por_grupo,
            previsao=previsao,
            clima_ontem=clima_ontem,
            atualizado_em=atualizado_em,
        )
        if self._cache_fingerprint == fingerprint and self._cache_resultado is not None:
            return self._cache_resultado
        if not self.gemini.disponivel():
            self._cache_fingerprint = fingerprint
            self._cache_resultado = fallback
            return fallback
        try:
            resultado = self._via_gemini(
                agenda_google=agenda_google,
                noticias=noticias,
                noticias_por_grupo=noticias_por_grupo,
                previsao=previsao,
                clima_ontem=clima_ontem,
                perfil_pessoal=perfil_pessoal,
                interesses_usuario=interesses_usuario,
                noticias_relevantes=noticias_relevantes,
                timezone=timezone,
                fallback=fallback,
            )
        except Exception:
            resultado = fallback
        self._cache_fingerprint = fingerprint
        self._cache_resultado = resultado
        return resultado

    def _via_gemini(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        timezone: str,
        fallback: DashboardInsights,
    ) -> DashboardInsights:
        """Usa o Gemini para reescrever os resumos com leitura mais humana."""
        prompt = self._montar_prompt(
            agenda_google=agenda_google,
            noticias=noticias,
            noticias_por_grupo=noticias_por_grupo,
            previsao=previsao,
            clima_ontem=clima_ontem,
            perfil_pessoal=perfil_pessoal,
            interesses_usuario=interesses_usuario,
            noticias_relevantes=noticias_relevantes,
            timezone=timezone,
            fallback=fallback,
        )
        schema_hint = json.dumps(
            {
                "agenda": {"resumo": "texto", "bullets": ["texto", "texto"]},
                "noticias": {"resumo": "texto", "bullets": ["texto", "texto"]},
                "clima": {"resumo": "texto", "bullets": ["texto", "texto"]},
            },
            ensure_ascii=True,
        )
        dados = self.gemini.gerar_json(prompt, schema_hint=schema_hint)
        return DashboardInsights(
            agenda=_normalizar_card("Agenda do dia", dados.get("agenda"), fallback.agenda),
            noticias=_normalizar_card(
                "Panorama de noticias",
                dados.get("noticias"),
                fallback.noticias,
            ),
            clima=_normalizar_card("Leitura do clima", dados.get("clima"), fallback.clima),
            motor="Gemini",
        )

    def _fallback_local(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        timezone: str,
    ) -> DashboardInsights:
        """Gera um resumo local legivel para nao depender do LLM."""
        agora = datetime.now(ZoneInfo(timezone))
        eventos_futuros = [
            evento
            for evento in agenda_google
            if _evento_ainda_relevante(evento, timezone, agora)
        ]
        agenda = _montar_card_agenda(eventos_futuros, timezone)
        noticias_card = _montar_card_noticias(
            noticias,
            noticias_por_grupo,
            timezone,
            interesses_usuario,
            noticias_relevantes,
        )
        clima = _montar_card_clima(previsao, clima_ontem)
        return DashboardInsights(
            agenda=agenda,
            noticias=noticias_card,
            clima=clima,
            motor="Local",
        )

    def _montar_prompt(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        timezone: str,
        fallback: DashboardInsights,
    ) -> str:
        """Serializa o contexto em texto curto para o Gemini."""
        eventos = [
            {
                "titulo": evento.titulo,
                "inicio": formatar_data_hora_google(evento.inicio, timezone),
                "fim": formatar_data_hora_google(evento.fim, timezone),
                "local": evento.local,
            }
            for evento in agenda_google[:6]
        ]
        manchetes: dict[str, list[str]] = {}
        for noticia in noticias[:18]:
            manchetes.setdefault(noticia.grupo or "geral", []).append(noticia.titulo)
        noticias_memoria = [
            {
                "titulo": noticia.titulo,
                "grupo": noticia.grupo,
                "fonte": noticia.fonte,
                "origem": noticia.origem,
                "contexto": noticia.contexto,
                "registrado_em": noticia.registrado_em,
            }
            for noticia in noticias_relevantes[:12]
        ]
        clima_payload = {
            "cidade": previsao.cidade,
            "data": previsao.data_alvo.isoformat(),
            "temperatura": previsao.temperatura_referencia,
            "maxima": previsao.maxima,
            "minima": previsao.minima,
            "chuva": previsao.chuva,
            "uv_max": previsao.uv_max,
            "vento": previsao.vento,
            "comparacao_ontem": {
                "maxima": clima_ontem.maxima if clima_ontem else None,
                "minima": clima_ontem.minima if clima_ontem else None,
                "chuva": clima_ontem.chuva if clima_ontem else None,
            },
        }
        guia_local = {
            "agenda": {
                "resumo": fallback.agenda.resumo,
                "bullets": fallback.agenda.bullets,
            },
            "noticias": {
                "resumo": fallback.noticias.resumo,
                "bullets": fallback.noticias.bullets,
            },
            "clima": {
                "resumo": fallback.clima.resumo,
                "bullets": fallback.clima.bullets,
            },
        }
        return (
            "Voce resume um dashboard pessoal em portugues do Brasil. "
            "Seja concreto, util e curto. Nao invente fatos. "
            "Cada resumo deve ter no maximo 220 caracteres e cada bullet no maximo 120 caracteres. "
            "Foque em rotina, prioridades e orientacao pratica. "
            "Considere perfil, interesses salvos e noticias clicadas como sinais de relevancia.\n\n"
            f"Perfil pessoal persistido no banco: {perfil_pessoal or 'Nao informado.'}\n"
            f"Interesses salvos: {json.dumps(interesses_usuario, ensure_ascii=False)}\n"
            "Historico de noticias relevantes: "
            f"{json.dumps(noticias_memoria, ensure_ascii=False)}\n"
            f"Agenda: {json.dumps(eventos, ensure_ascii=False)}\n"
            f"Noticias por grupo: {json.dumps(noticias_por_grupo, ensure_ascii=False)}\n"
            f"Manchetes por grupo: {json.dumps(manchetes, ensure_ascii=False)}\n"
            f"Clima: {json.dumps(clima_payload, ensure_ascii=False)}\n"
            f"Fallback local: {json.dumps(guia_local, ensure_ascii=False)}"
        )

    def _fingerprint(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        atualizado_em: str,
    ) -> str:
        """Deriva um hash estavel dos dados relevantes para evitar recomputos."""
        payload = {
            "agenda": [
                {
                    "titulo": evento.titulo,
                    "inicio": evento.inicio,
                    "fim": evento.fim,
                    "local": evento.local,
                }
                for evento in agenda_google[:8]
            ],
            "noticias": [
                {
                    "titulo": noticia.titulo,
                    "grupo": noticia.grupo,
                    "fonte": noticia.fonte,
                }
                for noticia in noticias[:20]
            ],
            "noticias_por_grupo": noticias_por_grupo,
            "previsao": {
                "temperatura_referencia": previsao.temperatura_referencia,
                "maxima": previsao.maxima,
                "minima": previsao.minima,
                "chuva": previsao.chuva,
                "vento": previsao.vento,
            },
            "clima_ontem": (
                {
                    "maxima": clima_ontem.maxima,
                    "minima": clima_ontem.minima,
                    "chuva": clima_ontem.chuva,
                }
                if clima_ontem
                else None
            ),
            "atualizado_em": atualizado_em,
        }
        bruto = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def _normalizar_card(
    titulo_padrao: str,
    dados: object,
    fallback: InsightCard,
) -> InsightCard:
    """Aceita pequenos desvios do modelo sem quebrar a GUI."""
    if not isinstance(dados, dict):
        return fallback
    resumo = str(dados.get("resumo", "")).strip() or fallback.resumo
    bullets_brutos = dados.get("bullets")
    bullets: list[str] = []
    if isinstance(bullets_brutos, list):
        bullets = [str(item).strip() for item in bullets_brutos if str(item).strip()]
    if not bullets:
        bullets = fallback.bullets
    return InsightCard(titulo=titulo_padrao, resumo=resumo, bullets=bullets[:4])


def _montar_card_agenda(eventos: list[EventoGoogleAgenda], timezone: str) -> InsightCard:
    if not eventos:
        return InsightCard(
            titulo="Agenda do dia",
            resumo="Sua agenda futura esta livre por enquanto.",
            bullets=[
                "Sem compromissos futuros encontrados no Google Agenda.",
                "Bom momento para encaixar tarefas profundas ou descanso.",
            ],
        )
    primeiro = eventos[0]
    inicio = formatar_data_hora_google(primeiro.inicio, timezone)
    bullets = [
        f"Proximo compromisso: {primeiro.titulo} as {inicio}.",
        f"Ha {len(eventos)} evento(s) futuro(s) mapeado(s) no momento.",
    ]
    if primeiro.local:
        bullets.append(f"Primeiro evento em destaque: {primeiro.local}.")
    if len(eventos) > 1:
        bullets.append(f"O ultimo bloco do recorte atual termina com {eventos[-1].titulo}.")
    resumo = (
        f"Seu dia tem {len(eventos)} compromisso(s) futuro(s); "
        f"o primeiro bloco relevante comeca as {inicio}."
    )
    return InsightCard(titulo="Agenda do dia", resumo=resumo, bullets=bullets[:4])


def _montar_card_noticias(
    noticias: list[Noticia],
    noticias_por_grupo: dict[str, int],
    timezone: str,
    interesses_usuario: list[str],
    noticias_relevantes: list[InteracaoNoticiaMemoria],
) -> InsightCard:
    if not noticias:
        return InsightCard(
            titulo="Panorama de noticias",
            resumo="O feed esta vazio agora, entao nao ha sinal suficiente para resumir.",
            bullets=["Nenhuma noticia carregada no momento."],
        )
    total = len(noticias)
    grupos = []
    for grupo in ("the_news", "santa_maria", "interesses", "tech", "economia_global"):
        quantidade = noticias_por_grupo.get(grupo, 0)
        if quantidade:
            grupos.append(f"{_rotulo_grupo(grupo)}: {quantidade}")
    bullets = []
    for grupo in ("the_news", "santa_maria", "interesses"):
        titulo = next((n.titulo for n in noticias if n.grupo == grupo), "")
        if titulo:
            bullets.append(f"{_rotulo_grupo(grupo)}: {titulo}.")
    if interesses_usuario:
        bullets.append(f"Interesses salvos: {', '.join(interesses_usuario[:4])}.")
    if noticias_relevantes:
        ultima_relevante = noticias_relevantes[0]
        rotulo_relevante = _rotulo_grupo(ultima_relevante.grupo)
        bullets.append(
            f"Ultimo sinal forte: {ultima_relevante.titulo} ({rotulo_relevante})."
        )
    mais_recente = noticias[0]
    quando = rotulo_tempo_publicacao(mais_recente, timezone=timezone)
    resumo = (
        f"Ha {total} noticia(s) no feed, com foco em "
        f"{', '.join(grupos[:3]) if grupos else 'fontes gerais'}."
    )
    bullets.insert(
        0,
        f"Mais recente: {mais_recente.titulo} ({quando}) via {mais_recente.fonte}.",
    )
    return InsightCard(titulo="Panorama de noticias", resumo=resumo, bullets=bullets[:4])


def _montar_card_clima(previsao: PrevisaoClima, clima_ontem: ResumoClimaDia | None) -> InsightCard:
    comparacao = _comparacao_clima(previsao, clima_ontem)
    roupa = _recomendacao_roupa(previsao)
    chuva = _recomendacao_chuva(previsao.chuva)
    resumo = (
        f"{comparacao} Maxima de {_temperatura(previsao.maxima)} e minima de "
        f"{_temperatura(previsao.minima)}."
    )
    bullets = [
        f"Temperatura de referencia: {_temperatura(previsao.temperatura_referencia)}.",
        f"Roupas: {roupa}.",
        f"Chuva: {chuva}.",
    ]
    if previsao.vento is not None:
        bullets.append(f"Vento em torno de {previsao.vento:g} km/h.")
    return InsightCard(titulo="Leitura do clima", resumo=resumo, bullets=bullets[:4])


def _evento_ainda_relevante(
    evento: EventoGoogleAgenda,
    timezone: str,
    agora: datetime,
) -> bool:
    try:
        fim = datetime.fromisoformat(evento.fim.replace("Z", "+00:00"))
    except ValueError:
        return True
    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=ZoneInfo(timezone))
    return fim.astimezone(ZoneInfo(timezone)) >= agora


def _rotulo_grupo(grupo: str) -> str:
    rotulos = {
        "the_news": "The News",
        "santa_maria": "Santa Maria",
        "interesses": "Interesses",
        "tech": "Tech",
        "economia_global": "Economia global",
    }
    return rotulos.get(grupo, grupo.replace("_", " ").title())


def _comparacao_clima(previsao: PrevisaoClima, clima_ontem: ResumoClimaDia | None) -> str:
    if clima_ontem is None or previsao.maxima is None or clima_ontem.maxima is None:
        return "Hoje o clima pede atencao ao intervalo termico."
    diferenca = round(previsao.maxima - clima_ontem.maxima, 1)
    if diferenca >= 2:
        return f"Hoje deve esquentar cerca de {diferenca:g} C em relacao a ontem."
    if diferenca <= -2:
        return f"Hoje deve esfriar cerca de {abs(diferenca):g} C em relacao a ontem."
    return "Hoje deve seguir em faixa parecida com a de ontem."


def _recomendacao_roupa(previsao: PrevisaoClima) -> str:
    maxima = previsao.maxima
    minima = previsao.minima
    if maxima is None and minima is None:
        return "leve uma camada versatil"
    if maxima is not None and maxima >= 28:
        return "roupa leve e respiravel"
    if minima is not None and minima <= 10:
        return "casaco mais forte ou agasalho"
    if minima is not None and minima <= 16:
        return "camadas leves com casaco fino"
    return "roupa leve com uma camada extra opcional"


def _recomendacao_chuva(chuva: float | None) -> str:
    if chuva is None:
        return "sem leitura confiavel de chuva agora"
    if chuva >= 70:
        return "leve guarda-chuva e evite sair sem protecao"
    if chuva >= 40:
        return "vale levar guarda-chuva compacto"
    if chuva >= 20:
        return "chuva possivel, mas nao dominante"
    return "baixa chance de chuva"


def _temperatura(valor: float | None) -> str:
    if valor is None:
        return "--"
    return f"{valor:g} C"
