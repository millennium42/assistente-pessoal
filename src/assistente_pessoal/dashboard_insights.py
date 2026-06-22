"""Gera resumos inteligentes para a aba principal do dashboard."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from assistente_pessoal.agenda_google import EventoGoogleAgenda, formatar_data_hora_google
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
from assistente_pessoal.gemini import ClienteGemini
from assistente_pessoal.memoria import InteracaoNoticiaMemoria
from assistente_pessoal.noticias import Noticia, rotulo_tempo_publicacao

DASHBOARD_GEMINI_TIMEOUT = 12.0
MAX_MANCHETES_PROMPT = 12
MAX_NOTICIAS_MEMORIA_PROMPT = 8
MAX_COMPORTAMENTOS_PROMPT = 8
MAX_TEXTO_CURTO_PROMPT = 180
MAX_TEXTO_MEDIO_PROMPT = 360
MAX_PERFIL_PROMPT = 900


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
    assistente: InsightCard
    motor: str


class GeradorInsightsDashboard:
    """Produz insights locais e tenta refiná-los com Gemini quando disponível."""

    def __init__(self, config: AppConfig, cliente_gemini: ClienteGemini | None = None) -> None:
        self.config = config
        self.gemini = cliente_gemini or ClienteGemini(config.llm, timeout=DASHBOARD_GEMINI_TIMEOUT)
        self._cache_fingerprint: str | None = None
        self._cache_resultado: DashboardInsights | None = None
        self._cache_criado_em: datetime | None = None

    def invalidar_cache(self) -> None:
        """Forca a proxima geracao a consultar o Gemini novamente."""
        self._cache_fingerprint = None
        self._cache_resultado = None
        self._cache_criado_em = None

    def gerar(
        self,
        *,
        eventos_hoje: list[EventoGoogleAgenda],
        eventos_futuros: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        clima_amanha: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        comportamentos: list[dict],
        timezone: str,
        atualizado_em: str,
    ) -> DashboardInsights:
        """Monta insights com cache por conteudo para nao repetir chamadas ao Gemini."""
        fingerprint = self._fingerprint(
            agenda_google=eventos_hoje + eventos_futuros,
            noticias=noticias,
            noticias_por_grupo=noticias_por_grupo,
            previsao=previsao,
            clima_ontem=clima_ontem,
            clima_amanha=clima_amanha,
            perfil_pessoal=perfil_pessoal,
            interesses_usuario=interesses_usuario,
            noticias_relevantes=noticias_relevantes,
            comportamentos=comportamentos,
        )
        if self._cache_fingerprint == fingerprint and self._cache_resultado is not None:
            return self._cache_resultado
        if self._cache_resultado is not None and self._cache_dentro_ttl():
            return self._cache_resultado
        if not self.gemini.disponivel():
            resultado_lock = DashboardInsights(
                agenda=InsightCard(
                    "Aguardando IA",
                    "A APPA requer o Gemini configurado para analisar sua agenda.",
                    [],
                ),
                noticias=InsightCard(
                    "Aguardando IA",
                    "Configure o modelo gemini-3.1-flash-lite para resumir o feed.",
                    [],
                ),
                clima=InsightCard(
                    "Aguardando IA",
                    "Insights do clima pausados sem a IA.",
                    [],
                ),
                assistente=InsightCard(
                    "Sistema bloqueado",
                    "O APPA 0.3.2 requer o Gemini para processar memoria adaptativa e insights. "
                    "Adicione a chave GEMINI_API_KEY no arquivo de configuração ou no ambiente.",
                    [],
                ),
                motor="Bloqueado",
            )
            self._cache_fingerprint = fingerprint
            self._cache_resultado = resultado_lock
            self._cache_criado_em = datetime.now()
            return resultado_lock

        try:
            resultado = self._via_gemini(
                eventos_hoje=eventos_hoje,
                eventos_futuros=eventos_futuros,
                noticias=noticias,
                noticias_por_grupo=noticias_por_grupo,
                previsao=previsao,
                clima_ontem=clima_ontem,
                clima_amanha=clima_amanha,
                perfil_pessoal=perfil_pessoal,
                interesses_usuario=interesses_usuario,
                noticias_relevantes=noticias_relevantes,
                comportamentos=comportamentos,
                timezone=timezone,
            )
        except Exception:
            return self._cache_resultado or DashboardInsights(
                InsightCard(
                    "Aguardando IA",
                    "A APPA requer o Gemini para analisar sua agenda.",
                    [],
                ),
                InsightCard(
                    "Aguardando IA",
                    "A APPA requer o Gemini para resumir o feed.",
                    [],
                ),
                InsightCard(
                    "Aguardando IA",
                    "A APPA requer o Gemini para interpretar o clima.",
                    [],
                ),
                InsightCard(
                    "Sistema bloqueado",
                    (
                        "O Gemini ficou indisponivel agora. "
                        "A APPA entrou em modo bloqueado e volta a operar quando a API responder."
                    ),
                    [],
                ),
                "Bloqueado",
            )
        self._cache_fingerprint = fingerprint
        self._cache_resultado = resultado
        self._cache_criado_em = datetime.now()
        return resultado

    def _cache_dentro_ttl(self) -> bool:
        """Evita gastar tokens enquanto o painel apenas refresca em segundo plano."""
        if self._cache_criado_em is None:
            return False
        ttl = self.config.dashboard.ttl_insights_segundos
        return datetime.now() - self._cache_criado_em < timedelta(seconds=ttl)

    def _via_gemini(
        self,
        *,
        eventos_hoje: list[EventoGoogleAgenda],
        eventos_futuros: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        clima_amanha: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        comportamentos: list[dict],
        timezone: str,
    ) -> DashboardInsights:
        """Usa o Gemini para reescrever os resumos com leitura mais humana."""
        prompt = self._montar_prompt(
            eventos_hoje=eventos_hoje,
            eventos_futuros=eventos_futuros,
            noticias=noticias,
            noticias_por_grupo=noticias_por_grupo,
            previsao=previsao,
            clima_ontem=clima_ontem,
            clima_amanha=clima_amanha,
            perfil_pessoal=perfil_pessoal,
            interesses_usuario=interesses_usuario,
            noticias_relevantes=noticias_relevantes,
            comportamentos=comportamentos,
            timezone=timezone,
        )
        schema_hint = json.dumps(
            {
                "agenda": {"resumo": "texto", "bullets": ["texto", "texto"]},
                "noticias": {"resumo": "texto", "bullets": ["texto", "texto"]},
                "clima": {"resumo": "texto", "bullets": ["texto", "texto"]},
                "assistente": {
                    "resumo": "texto longo e conversacional",
                    "bullets": ["texto", "texto", "texto", "texto", "texto"],
                },
            },
            ensure_ascii=True,
        )
        dados = self.gemini.gerar_json(prompt, schema_hint=schema_hint)
        fallback_vazio = InsightCard("", "", [])
        return DashboardInsights(
            agenda=_normalizar_card("Agenda de hoje", dados.get("agenda"), fallback_vazio),
            noticias=_normalizar_card(
                "Resumo das noticias",
                dados.get("noticias"),
                fallback_vazio,
            ),
            clima=_normalizar_card("Comparativo do clima", dados.get("clima"), fallback_vazio),
            assistente=_normalizar_card(
                "Sua secretaria virtual",
                dados.get("assistente"),
                fallback_vazio,
                max_bullets=7,
            ),
            motor="Gemini 3.1 Flash-Lite",
        )

    def _montar_prompt(
        self,
        *,
        eventos_hoje: list[EventoGoogleAgenda],
        eventos_futuros: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        clima_amanha: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        comportamentos: list[dict],
        timezone: str,
    ) -> str:
        """Serializa o contexto em texto curto para o Gemini."""
        hoje_json = [
            {
                "titulo": evento.titulo,
                "inicio": formatar_data_hora_google(evento.inicio, timezone),
                "fim": formatar_data_hora_google(evento.fim, timezone),
                "local": evento.local,
            }
            for evento in eventos_hoje
        ]
        futuros_json = [
            {
                "titulo": e.titulo,
                "inicio": formatar_data_hora_google(e.inicio, timezone),
                "local": e.local,
            }
            for e in eventos_futuros[:4]
        ]

        manchetes: dict[str, list[str]] = {}
        for noticia in noticias[:MAX_MANCHETES_PROMPT]:
            manchetes.setdefault(noticia.grupo or "geral", []).append(
                _limitar_texto(noticia.titulo, MAX_TEXTO_CURTO_PROMPT)
            )
        noticias_memoria = [
            {
                "titulo": _limitar_texto(noticia.titulo, MAX_TEXTO_CURTO_PROMPT),
                "grupo": noticia.grupo,
                "fonte": noticia.fonte,
                "origem": noticia.origem,
                "contexto": _limitar_texto(noticia.contexto, MAX_TEXTO_MEDIO_PROMPT),
                "registrado_em": noticia.registrado_em,
            }
            for noticia in noticias_relevantes[:MAX_NOTICIAS_MEMORIA_PROMPT]
        ]
        comportamentos_prompt = [
            {
                "tipo": str(comportamento.get("tipo") or ""),
                "conteudo": _limitar_texto(
                    str(comportamento.get("conteudo") or ""),
                    MAX_TEXTO_MEDIO_PROMPT,
                ),
                "nivel_confianca": str(comportamento.get("nivel_confianca") or ""),
            }
            for comportamento in comportamentos[:MAX_COMPORTAMENTOS_PROMPT]
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
            "comparacao_amanha": {
                "data": clima_amanha.data.isoformat() if clima_amanha else None,
                "maxima": clima_amanha.maxima if clima_amanha else None,
                "minima": clima_amanha.minima if clima_amanha else None,
                "chuva": clima_amanha.chuva if clima_amanha else None,
            },
        }
        return (
            "Voce resume um dashboard pessoal em portugues do Brasil. "
            "Seja concreto, util e curto. Nao invente fatos. "
            "Os tres cards menores devem ter no maximo 220 caracteres no resumo. "
            "O card amplo do assistente pode ter ate 1600 caracteres no resumo. "
            "Cada bullet do card amplo pode ter ate 260 caracteres. "
            "Foque em rotina, prioridades e orientacao pratica. "
            "Considere perfil, interesses salvos e noticias clicadas como sinais de relevancia. "
            "No card de noticias, resuma temas e prioridades do feed sem listar manchetes. "
            "No card de clima, mantenha o titulo diferente do resumo e foque em comparacoes. "
            "No card amplo da secretaria, entregue leitura util do dia baseada ESTRITAMENTE "
            "em eventos_hoje. "
            "oportunidades e proximos passos simples. "
            "Escreva esse card como uma secretaria eletronica cuidadosa, humana e conversacional. "
            "Fale diretamente com a pessoa, como quem organiza o dia e antecipa o que vale saber. "
            "Esse card deve soar como uma assistente pessoal calorosa, inteligente, "
            "proativa e clara. "
            "Conecte agenda, clima, noticias relevantes e interesses pessoais "
            "em uma leitura unica. "
            "Aponte o que merece atencao primeiro, o que pode esperar, "
            "o que combina com os interesses "
            "da pessoa e quais sinais do dia podem afetar sua rotina. "
            "Se houver noticias relevantes, traga-as como curadoria explicada, "
            "nao como lista fria. "
            "Esse card e o unico visivel na aba Insights, entao ele precisa ser "
            "completo e sustentar "
            "sozinho a leitura do dia. "
            "Dedique espaco real para noticias relevantes, explicando por que elas "
            "importam para a pessoa. "
            "Nao se limite a mencionar que ha noticias: conecte o tema ao momento do usuario. "
            "Se houver poucos dados, ainda assim fale como assistente e nao como sistema tecnico. "
            "Nao repita no resumo a mesma frase usada nos bullets. "
            "Use os bullets para complementar com faixa termica, roupas, chuva ou impacto pratico. "
            "Evite bullets mecanicos como 'Hoje vs ontem' e 'Amanha vs hoje'.\n\n"
            "Perfil pessoal persistido no banco: "
            f"{_limitar_texto(perfil_pessoal, MAX_PERFIL_PROMPT) or 'Nao informado.'}\n"
            f"Interesses salvos: {json.dumps(interesses_usuario[:8], ensure_ascii=False)}\n"
            "Historico de noticias relevantes: "
            f"{json.dumps(noticias_memoria, ensure_ascii=False)}\n"
            "Comportamentos adaptativos observados: "
            f"{json.dumps(comportamentos_prompt, ensure_ascii=False)}\n"
            f"Agenda de Hoje: {json.dumps(hoje_json, ensure_ascii=False)}\n"
            f"Agenda Futura Próxima: {json.dumps(futuros_json, ensure_ascii=False)}\n"
            f"Noticias por grupo: {json.dumps(noticias_por_grupo, ensure_ascii=False)}\n"
            f"Manchetes por grupo: {json.dumps(manchetes, ensure_ascii=False)}\n"
            f"Clima: {json.dumps(clima_payload, ensure_ascii=False)}\n"
        )

    def _fingerprint(
        self,
        *,
        agenda_google: list[EventoGoogleAgenda],
        noticias: list[Noticia],
        noticias_por_grupo: dict[str, int],
        previsao: PrevisaoClima,
        clima_ontem: ResumoClimaDia | None,
        clima_amanha: ResumoClimaDia | None,
        perfil_pessoal: str,
        interesses_usuario: list[str],
        noticias_relevantes: list[InteracaoNoticiaMemoria],
        comportamentos: list[dict],
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
            "clima_amanha": (
                {
                    "data": clima_amanha.data.isoformat(),
                    "maxima": clima_amanha.maxima,
                    "minima": clima_amanha.minima,
                    "chuva": clima_amanha.chuva,
                }
                if clima_amanha
                else None
            ),
            "perfil_pessoal": perfil_pessoal[:300],
            "interesses_usuario": interesses_usuario[:8],
            "noticias_relevantes": [
                {
                    "titulo": noticia.titulo,
                    "grupo": noticia.grupo,
                    "origem": noticia.origem,
                    "contexto": noticia.contexto[:160],
                }
                for noticia in noticias_relevantes[:MAX_NOTICIAS_MEMORIA_PROMPT]
            ],
            "comportamentos": [
                {
                    "tipo": str(comportamento.get("tipo") or ""),
                    "conteudo": str(comportamento.get("conteudo") or "")[:180],
                    "nivel_confianca": str(comportamento.get("nivel_confianca") or ""),
                }
                for comportamento in comportamentos[:MAX_COMPORTAMENTOS_PROMPT]
            ],
        }
        bruto = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def _normalizar_card(
    titulo_padrao: str,
    dados: object,
    fallback: InsightCard,
    *,
    max_bullets: int = 4,
) -> InsightCard:
    """Aceita pequenos desvios do modelo sem quebrar a GUI."""
    if not isinstance(dados, dict):
        return fallback
    resumo = str(dados.get("resumo", "")).strip() or fallback.resumo
    bullets_brutos = dados.get("bullets")
    bullets = _filtrar_bullets_distintos(
        resumo,
        bullets_brutos if isinstance(bullets_brutos, list) else [],
    )
    if not bullets:
        bullets = _filtrar_bullets_distintos(fallback.resumo, fallback.bullets)
    resumo = _evitar_resumo_igual_a_bullet(resumo, bullets, fallback.resumo)
    return InsightCard(titulo=titulo_padrao, resumo=resumo, bullets=bullets[:max_bullets])


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
            titulo="Resumo das noticias",
            resumo="O feed esta vazio agora, entao nao ha sinal suficiente para resumir.",
            bullets=["Nenhuma noticia carregada no momento."],
        )
    total = len(noticias)
    grupos = []
    for grupo in ("the_news", "santa_maria", "interesses", "tech", "economia_global"):
        quantidade = noticias_por_grupo.get(grupo, 0)
        if quantidade:
            grupos.append(f"{_rotulo_grupo(grupo)}: {quantidade}")
    grupos_presentes = [
        grupo
        for grupo in ("the_news", "santa_maria", "interesses", "tech")
        if noticias_por_grupo.get(grupo, 0)
    ]
    destaques = ", ".join(_rotulo_grupo(grupo) for grupo in grupos_presentes[:3]) or "fontes gerais"
    bullets = [
        f"O feed esta distribuido entre {destaques}.",
        f"Volume atual: {total} item(ns), com {_resumo_grupos_noticias(noticias_por_grupo)}.",
    ]
    if interesses_usuario:
        bullets.append(
            f"Seus interesses ativos puxam leitura em {', '.join(interesses_usuario[:3])}."
        )
    if noticias_relevantes:
        ultima_relevante = noticias_relevantes[0]
        rotulo_relevante = _rotulo_grupo(ultima_relevante.grupo)
        bullets.append(f"Historico recente reforca atencao em {rotulo_relevante.lower()}.")
    mais_recente = noticias[0]
    quando = rotulo_tempo_publicacao(mais_recente, timezone=timezone)
    resumo = (
        f"Ha {total} noticia(s) no radar agora, com maior peso em "
        f"{', '.join(grupos[:3]) if grupos else 'fontes gerais'}, "
        f"e atualizacao mais recente {quando}."
    )
    return InsightCard(titulo="Resumo das noticias", resumo=resumo, bullets=bullets[:4])


def _montar_card_clima(
    previsao: PrevisaoClima,
    clima_ontem: ResumoClimaDia | None,
    clima_amanha: ResumoClimaDia | None,
) -> InsightCard:
    comparacao_hoje = _comparacao_hoje_ontem(previsao, clima_ontem)
    comparacao_amanha = _comparacao_amanha_hoje(previsao, clima_amanha)
    roupa = _recomendacao_roupa(previsao)
    chuva = _recomendacao_chuva(previsao.chuva)
    faixa_termica = (
        f"Maxima de {_temperatura(previsao.maxima)} e minima de {_temperatura(previsao.minima)}."
    )
    resumo = " ".join(
        parte
        for parte in (
            _resumo_clima_narrativo(comparacao_hoje, comparacao_amanha),
            f"Dia para {roupa}, com {chuva}.",
        )
        if parte
    )
    bullets = [
        comparacao_hoje,
        comparacao_amanha,
        faixa_termica,
        f"Vale sair com {roupa}; {chuva}.",
    ]
    if previsao.vento is not None:
        bullets.append(f"Vento em torno de {previsao.vento:g} km/h.")
    return InsightCard(titulo="Comparativo do clima", resumo=resumo, bullets=bullets[:4])


def _montar_card_assistente(
    *,
    agenda: InsightCard,
    noticias: InsightCard,
    clima: InsightCard,
    perfil_pessoal: str,
    interesses_usuario: list[str],
    noticias_relevantes: list[InteracaoNoticiaMemoria],
) -> InsightCard:
    perfil_curto = perfil_pessoal.strip() or "Sem perfil pessoal detalhado salvo ainda."
    interesses_texto = ", ".join(interesses_usuario[:3]) if interesses_usuario else None
    origem_relevante = _rotulo_grupo(noticias_relevantes[0].grupo) if noticias_relevantes else None
    nome_foco_noticias = _extrair_foco_noticias(noticias.resumo)
    abertura = (
        "Revisei seu dia como uma assistente que tenta poupar a sua energia mental: organizei "
        "o que pede acao, o que funciona como contexto e o que vale acompanhar sem deixar o "
        "noticiario disputar espaco com o que realmente importa."
    )
    foco_agenda = _frase_curta(agenda.resumo)
    foco_clima = _frase_curta(clima.resumo)
    foco_noticias = _frase_curta(noticias.resumo)
    leitura_noticias = (
        f"No bloco de noticias, o sinal mais forte agora parece estar em {nome_foco_noticias}. "
        "Meu papel aqui nao e despejar manchetes, e sim te entregar um filtro do que pode ser "
        "relevante para suas decisoes, conversas e curiosidade de hoje."
    )
    leitura_interesses = (
        f"Seus interesses ativos hoje puxam relevancia para {interesses_texto}."
        if interesses_texto
        else None
    )
    leitura_historico = (
        f"Pelo seu historico recente, eu manteria atencao extra em {origem_relevante.lower()}."
        if origem_relevante
        else None
    )
    resumo = " ".join(
        parte
        for parte in [
            abertura,
            f"O primeiro eixo pratico do seu dia e este: {foco_agenda}",
            f"No pano de fundo, {foco_clima.lower()}",
            (
                "E no noticiario, o que mais parece conversar com a sua rotina "
                f"agora e isto: {foco_noticias}"
            ),
            leitura_noticias,
            leitura_interesses or leitura_historico,
            (
                "Se eu resumisse a intencao deste painel em uma frase, seria esta: "
                "te ajudar a entrar no dia com menos ruido e mais criterio sobre onde colocar "
                "atencao, tempo e curiosidade."
            ),
        ]
        if parte
    )
    bullets = [
        f"Se eu tivesse que te orientar agora, eu começaria por isto: {foco_agenda}",
        f"Na leitura do tempo, o ajuste mais importante para sua rotina e este: {foco_clima}",
        f"Na curadoria de noticias, o que parece mais util para voce agora e isto: {foco_noticias}",
        (
            f"Meu destaque editorial do momento vai para {nome_foco_noticias}, "
            "porque esse parece ser o assunto com mais chance de gerar contexto util para voce."
        ),
    ]
    if interesses_texto:
        bullets.append(
            f"Seu radar pessoal segue inclinado para estes temas: {interesses_texto}. "
            "Isso ajuda a separar informacao util de barulho."
        )
    elif origem_relevante:
        bullets.append(
            f"Seu historico recente indica que {origem_relevante.lower()} merece um olhar extra, "
            "entao eu trataria esse tema como prioridade secundaria."
        )
    else:
        bullets.append(
            "Estou usando este contexto pessoal para calibrar meu jeito de te orientar: "
            f"{perfil_curto[:170]}."
        )
    bullets.append(
        "Se o seu foco de hoje mudou, vale atualizar perfil ou interesses: quanto melhor eu "
        "entender o seu momento, mais eu consigo agir como uma assistente de verdade."
    )
    bullets.append(
        "Use este card como uma triagem executiva do dia: ele junta o essencial, reduz dispersao "
        "e tenta te mostrar primeiro o que tem impacto real."
    )
    return InsightCard(titulo="Sua secretaria virtual", resumo=resumo, bullets=bullets[:8])


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


def _comparacao_hoje_ontem(previsao: PrevisaoClima, clima_ontem: ResumoClimaDia | None) -> str:
    if not clima_ontem:
        return "Sem dados de ontem para comparar."
    if previsao.maxima > clima_ontem.maxima + 2:
        return "Hoje fica mais quente que ontem."
    if previsao.maxima < clima_ontem.maxima - 2:
        return "Hoje fica mais frio que ontem."
    return "Hoje a temperatura fica na mesma faixa de ontem."


def _comparacao_amanha_hoje(previsao: PrevisaoClima, clima_amanha: ResumoClimaDia | None) -> str:
    if not clima_amanha:
        return "Sem previsao confiavel para amanha."
    if clima_amanha.maxima > previsao.maxima + 2:
        return "Amanha a temperatura tende a subir."
    if clima_amanha.maxima < previsao.maxima - 2:
        return "Amanha a temperatura tende a cair."
    return "Amanha a temperatura tende a se manter."


def _recomendacao_roupa(previsao: PrevisaoClima) -> str:
    if previsao.minima < 12:
        return "casaco pesado"
    if previsao.minima < 19:
        return "camadas leves com casaco fino"
    if previsao.maxima > 28:
        return "roupas frescas"
    return "roupas confortaveis"


def _recomendacao_chuva(chuva: float) -> str:
    if chuva > 10.0:
        return "vale levar guarda-chuva"
    if chuva > 0.0:
        return "vale levar guarda-chuva compacto"
    return "sem indicacao de chuva"


def _temperatura(valor: float) -> str:
    return f"{valor:.0f} C"


def _resumo_clima_narrativo(comparacao_hoje: str, comparacao_amanha: str) -> str:
    return f"{comparacao_hoje.rstrip('.')}, mas {comparacao_amanha.lower()}"


def _resumo_grupos_noticias(noticias_por_grupo: dict[str, int]) -> str:
    partes = []
    for grupo, qtd in noticias_por_grupo.items():
        if qtd > 0:
            partes.append(f"{qtd} de {_rotulo_grupo(grupo).lower()}")
    if not partes:
        return "sem noticias"
    return " e ".join(partes)


def _extrair_foco_noticias(resumo: str) -> str:
    return "acontecimentos mais lidos"


def _frase_curta(texto: str) -> str:
    partes = texto.split(".")
    return f"{partes[0]}." if partes else texto


def _limitar_texto(texto: str, limite: int) -> str:
    """Corta contexto antes de enviar ao modelo para conter custo de tokens."""
    limpo = " ".join(str(texto or "").split())
    if len(limpo) <= limite:
        return limpo
    return limpo[: limite - 1].rstrip() + "..."


def _filtrar_bullets_distintos(resumo: str, bullets: list[str]) -> list[str]:
    resultado: list[str] = []
    for bullet in bullets:
        limpo = bullet.strip()
        if limpo and limpo not in resultado and limpo != resumo:
            resultado.append(limpo)
    return resultado


def _evitar_resumo_igual_a_bullet(resumo: str, bullets: list[str], resumo_fallback: str) -> str:
    if resumo in bullets:
        return resumo_fallback
    return resumo


def resumo_clima_amanha(
    resumo_semana: list[ResumoClimaDia],
    hoje: date,
) -> ResumoClimaDia | None:
    amanha = hoje + timedelta(days=1)
    for dia in resumo_semana:
        if dia.data == amanha:
            return dia
    return None
