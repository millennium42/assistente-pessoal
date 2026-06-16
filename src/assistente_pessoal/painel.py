"""Casos de uso reutilizaveis pelo dashboard grafico."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from assistente_pessoal.agenda_chat import AssistenteAgendaChat
from assistente_pessoal.agenda_google import (
    ClienteGoogleAgenda,
    EventoGoogleAgenda,
    ResultadoGoogleAgenda,
    evento_google_ainda_futuro,
)
from assistente_pessoal.cambio import ClienteCambio, CotacaoMoeda
from assistente_pessoal.clima import ClienteClima, PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig, renderizar_toml
from assistente_pessoal.dashboard_insights import (
    DashboardInsights,
    GeradorInsightsDashboard,
    resumo_clima_amanha,
)
from assistente_pessoal.gemini import ClienteGemini
from assistente_pessoal.memoria import Memoria
from assistente_pessoal.noticias import (
    LIMITE_PADRAO_NOTICIAS,
    ClienteNoticias,
    Noticia,
)
from assistente_pessoal.roteador import RespostaRoteador, RoteadorComandos


@dataclass(frozen=True)
class IndicadoresDashboard:
    """Numeros de topo usados como KPIs do painel."""

    total_noticias: int
    noticias_the_news: int
    noticias_santa_maria: int
    notas_recentes: int
    eventos_google: int


@dataclass(frozen=True)
class DashboardSnapshot:
    """Estado consolidado renderizado pela GUI."""

    previsao: PrevisaoClima
    resumo_semana: list[ResumoClimaDia]
    cotacao_dolar: CotacaoMoeda
    noticias: list[Noticia]
    santa_maria_em_foco: list[Noticia]
    notas_recentes: list[str]
    agenda_local: str
    perfil_pessoal: str
    agenda_google: list[EventoGoogleAgenda]
    agenda_google_resultado: ResultadoGoogleAgenda
    indicadores: IndicadoresDashboard
    noticias_por_grupo: dict[str, int]
    clima_ontem: ResumoClimaDia | None
    insights: DashboardInsights
    atualizado_em: str


class DashboardService:
    """Centraliza a leitura dos dados exibidos no dashboard."""

    def __init__(self, config: AppConfig) -> None:
        """Instancia os servicos de dominio usados pela GUI."""
        self.config = config
        self.memoria = Memoria(config.db_path, config.localizacao.timezone)
        self.noticias = ClienteNoticias()
        self.clima = ClienteClima()
        self.cambio = ClienteCambio()
        self.google_agenda = ClienteGoogleAgenda(config.google_agenda)
        self.gemini_intencoes = ClienteGemini(config.llm)
        self.gerador_insights = GeradorInsightsDashboard(config)
        self._cache_clima: tuple[datetime, PrevisaoClima] | None = None
        self._cache_resumo_semana: tuple[datetime, list[ResumoClimaDia]] | None = None
        self._cache_cotacao_dolar: tuple[datetime, CotacaoMoeda] | None = None
        self._cache_noticias: tuple[datetime, list[Noticia]] | None = None
        self._cache_agenda_google: tuple[datetime, ResultadoGoogleAgenda] | None = None
        self._cache_clima_ontem: tuple[datetime, ResumoClimaDia | None] | None = None
        self._agenda_chat: AssistenteAgendaChat | None = None
        self.anotacoes_chat: list[str] = []
        self._anotacao_em_andamento = False

    def carregar(
        self,
        dia_clima: str | None = None,
        limite_noticias: int = LIMITE_PADRAO_NOTICIAS,
    ) -> DashboardSnapshot:
        """Monta um snapshot unico para reduzir chamadas espalhadas na interface."""
        previsao = self._carregar_previsao(dia_clima)
        resumo_semana = self._carregar_resumo_semana()
        cotacao_dolar = self._carregar_cotacao_dolar()
        noticias = self._carregar_noticias(limite_noticias)
        santa_maria_em_foco = self._carregar_santa_maria_em_foco(noticias)
        notas = [
            self.memoria.caminho_relativo(caminho) for caminho in self.memoria.listar_recentes()
        ]
        agenda_local = self.memoria.ler_documento_fixo("61_agenda_local", "agenda-local.md")
        perfil_pessoal = self.memoria.obter_perfil_pessoal()
        interesses_usuario = self.memoria.listar_interesses()
        noticias_relevantes = self.memoria.listar_interacoes_noticias(limite=12)
        agenda_google_resultado = self._carregar_agenda_google()
        agenda_google = agenda_google_resultado.eventos
        agenda_google_futuros = [
            evento
            for evento in agenda_google
            if evento_google_ainda_futuro(evento, self.config.localizacao.timezone)
        ]
        contagem_grupos = Counter(noticia.grupo for noticia in noticias)
        clima_ontem = self._carregar_clima_ontem()
        clima_amanha = resumo_clima_amanha(resumo_semana, previsao.data_alvo)
        atualizado_em = datetime.now().strftime("%H:%M:%S")
        insights = self.gerador_insights.gerar(
            agenda_google=agenda_google_futuros,
            noticias=noticias,
            noticias_por_grupo=dict(contagem_grupos),
            previsao=previsao,
            clima_ontem=clima_ontem,
            clima_amanha=clima_amanha,
            perfil_pessoal=perfil_pessoal,
            interesses_usuario=interesses_usuario,
            noticias_relevantes=noticias_relevantes,
            timezone=self.config.localizacao.timezone,
            atualizado_em=atualizado_em,
        )
        return DashboardSnapshot(
            previsao=previsao,
            resumo_semana=resumo_semana,
            cotacao_dolar=cotacao_dolar,
            noticias=noticias,
            santa_maria_em_foco=santa_maria_em_foco,
            notas_recentes=notas,
            agenda_local=agenda_local,
            perfil_pessoal=perfil_pessoal,
            agenda_google=agenda_google,
            agenda_google_resultado=agenda_google_resultado,
            indicadores=IndicadoresDashboard(
                total_noticias=len(noticias),
                noticias_the_news=contagem_grupos.get("the_news", 0),
                noticias_santa_maria=contagem_grupos.get("santa_maria", 0),
                notas_recentes=len(notas),
                eventos_google=len(agenda_google_futuros),
            ),
            noticias_por_grupo=dict(contagem_grupos),
            clima_ontem=clima_ontem,
            insights=insights,
            atualizado_em=atualizado_em,
        )

    def _carregar_previsao(self, dia_clima: str | None) -> PrevisaoClima:
        """Mantem a previsao em cache para evitar chamadas repetidas a cada refresh da GUI."""
        ttl = self.config.dashboard.ttl_clima_segundos
        if (
            dia_clima is None
            and self._cache_clima
            and self._cache_valido(self._cache_clima[0], ttl)
        ):
            return self._cache_clima[1]
        previsao = self.clima.obter_previsao(self.config.localizacao, dia=dia_clima)
        if dia_clima is None:
            self._cache_clima = (datetime.now(), previsao)
        return previsao

    def _carregar_resumo_semana(self) -> list[ResumoClimaDia]:
        """Busca a faixa semanal de clima sem derrubar o painel em falha secundaria."""
        ttl = self.config.dashboard.ttl_clima_segundos
        if self._cache_resumo_semana and self._cache_valido(self._cache_resumo_semana[0], ttl):
            return self._cache_resumo_semana[1]
        try:
            resumo = self.clima.obter_resumo_semana(self.config.localizacao, dias=7)
        except Exception:
            return []
        self._cache_resumo_semana = (datetime.now(), resumo)
        return resumo

    def _carregar_cotacao_dolar(self) -> CotacaoMoeda:
        """Busca USD/BRL sem deixar uma falha externa derrubar o dashboard."""
        ttl = self.config.dashboard.ttl_dolar_segundos
        if self._cache_cotacao_dolar and self._cache_valido(self._cache_cotacao_dolar[0], ttl):
            return self._cache_cotacao_dolar[1]
        try:
            cotacao = self.cambio.obter_dolar_real(self.config.localizacao.timezone)
        except Exception as exc:
            cotacao = CotacaoMoeda(
                base="USD",
                destino="BRL",
                valor=None,
                variacao_percentual=None,
                maximo=None,
                minimo=None,
                horario=None,
                fonte="AwesomeAPI",
                erro=str(exc),
            )
        self._cache_cotacao_dolar = (datetime.now(), cotacao)
        return cotacao

    def _carregar_noticias(self, limite_noticias: int) -> list[Noticia]:
        """Agrupa o feed em cache curto para nao reprocessar noticias a cada poucos segundos."""
        ttl = self.config.dashboard.ttl_noticias_segundos
        if self._cache_noticias and self._cache_valido(self._cache_noticias[0], ttl):
            return self._cache_noticias[1][:limite_noticias]
        noticias = self.noticias.listar(self.config.fontes.noticias, limite=limite_noticias)
        self._cache_noticias = (datetime.now(), noticias)
        return noticias

    def _carregar_agenda_google(self) -> ResultadoGoogleAgenda:
        """Mantem a agenda em cache mais longo porque o conteudo muda com menos frequencia."""
        ttl = self.config.dashboard.ttl_agenda_segundos
        if self._cache_agenda_google and self._cache_valido(self._cache_agenda_google[0], ttl):
            return self._cache_agenda_google[1]
        resultado = self.google_agenda.obter_eventos_mes()
        self._cache_agenda_google = (datetime.now(), resultado)
        return resultado

    def _carregar_clima_ontem(self) -> ResumoClimaDia | None:
        """Busca um ponto de comparacao para os insights do tempo."""
        ttl = self.config.dashboard.ttl_clima_segundos
        if self._cache_clima_ontem and self._cache_valido(self._cache_clima_ontem[0], ttl):
            return self._cache_clima_ontem[1]
        metodo = getattr(self.clima, "obter_resumo_historico", None)
        if metodo is None:
            return None
        try:
            resumo = metodo(self.config.localizacao, dias_atras=1)
        except Exception:
            resumo = None
        self._cache_clima_ontem = (datetime.now(), resumo)
        return resumo

    def _cache_valido(self, atualizado_em: datetime, ttl_segundos: int) -> bool:
        """Indica se um bloco ainda pode ser reutilizado sem nova chamada externa."""
        return datetime.now() - atualizado_em < timedelta(seconds=ttl_segundos)

    def _carregar_santa_maria_em_foco(self, noticias: list[Noticia]) -> list[Noticia]:
        """Mantem o bloco local restrito ao recorte atual de Santa Maria."""
        locais_hoje = [noticia for noticia in noticias if noticia.grupo == "santa_maria"]
        return locais_hoje[:6]

    def salvar_nota_rapida(self, titulo: str, conteudo: str) -> str:
        """Cria uma nota curta no banco e devolve o caminho relativo gerado."""
        caminho = self.memoria.salvar_nota(titulo=titulo, conteudo=conteudo, pasta="10_memoria")
        return self.memoria.caminho_relativo(caminho)

    def adicionar_interesses(self, texto: str) -> list[str]:
        """Adiciona termos de interesse, persiste no config e organiza no banco de dados."""
        novos = normalizar_lista_interesses(texto)
        existentes = list(self.config.fontes.noticias.interesses_busca)
        existentes_casefold = {item.casefold() for item in existentes}
        for interesse in novos:
            if interesse.casefold() not in existentes_casefold:
                existentes.append(interesse)
                existentes_casefold.add(interesse.casefold())
        self.config.fontes.noticias.interesses_busca = existentes
        self._persistir_config()
        self.memoria.substituir_interesses(existentes)
        return existentes

    def remover_interesse(self, interesse: str) -> list[str]:
        """Remove um termo de interesse e sincroniza config e banco de dados."""
        termo = interesse.strip()
        if not termo:
            return list(self.config.fontes.noticias.interesses_busca)

        existentes = [
            item
            for item in self.config.fontes.noticias.interesses_busca
            if item.casefold() != termo.casefold()
        ]
        self.config.fontes.noticias.interesses_busca = existentes
        self._persistir_config()
        self.memoria.substituir_interesses(existentes)
        return existentes

    def salvar_noticia_relevante(self, noticia: Noticia | dict, origem: str = "clique") -> str:
        """Guarda uma noticia relevante em SQLite para orientar o que a APPA deve priorizar."""
        item = _normalizar_noticia_para_memoria(noticia)
        conteudo = "\n".join(
            [
                f"- Fonte: {item['fonte']}",
                f"- Grupo: {item['grupo']}",
                f"- Link: {item['link']}",
                f"- Origem: {origem}",
                f"- Registrada em: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "## Resumo manual",
                "",
                "Adicione aqui observacoes depois da leitura.",
            ]
        )
        tags = ["noticia", "banco", _slug_tag(item["grupo"])]
        if origem:
            tags.append(_slug_tag(origem))
        self.memoria.registrar_interacao_noticia(
            titulo=item["titulo"],
            link=item["link"],
            fonte=item["fonte"],
            grupo=item["grupo"],
            origem=origem,
            contexto="clique do usuario",
        )
        caminho = self.memoria.salvar_nota(
            titulo=item["titulo"],
            conteudo=conteudo,
            pasta="40_noticias",
            tags=tags,
        )
        return self.memoria.caminho_relativo(caminho)

    def registrar_consulta_noticias(self, consulta: str, noticias: list[Noticia]) -> str:
        """Salva no banco de dados o conjunto de noticias retornado para uma pergunta."""
        linhas = [f"Pergunta: {consulta}", "", "## Noticias retornadas", ""]
        for noticia in noticias:
            linhas.append(f"- [{noticia.titulo}]({noticia.link})")
            linhas.append(f"  - Fonte: {noticia.fonte}")
            linhas.append(f"  - Grupo: {noticia.grupo}")
            self.memoria.registrar_interacao_noticia(
                titulo=noticia.titulo,
                link=noticia.link,
                fonte=noticia.fonte,
                grupo=noticia.grupo,
                origem="consulta",
                contexto=consulta,
            )
        caminho = self.memoria.salvar_nota(
            titulo="Consulta de noticias",
            conteudo="\n".join(linhas),
            pasta="40_noticias",
            tags=["noticias", "consulta", "banco"],
        )
        return self.memoria.caminho_relativo(caminho)

    def salvar_agenda_local(self, conteudo: str) -> str:
        """Atualiza o documento canonico de agenda local."""
        caminho = self.memoria.salvar_documento_fixo(
            nome_arquivo="agenda-local.md",
            conteudo=conteudo,
            pasta="61_agenda_local",
            titulo="Agenda local",
            tags=["agenda", "planejamento"],
        )
        return self.memoria.caminho_relativo(caminho)

    def conversar(self, mensagem: str) -> RespostaRoteador:
        """Processa uma mensagem da APPA, incluindo comandos operacionais de agenda."""
        if self._agenda_chat is None or self._agenda_chat.cliente_google is not self.google_agenda:
            self._agenda_chat = AssistenteAgendaChat(
                self.google_agenda,
                self.config.localizacao.timezone,
            )
        destino = self._classificar_destino_chat(mensagem)
        if self._agenda_chat.pedido_pendente is None and destino != "agenda":
            resposta_anotacao = self._tentar_anotacao_chat(mensagem)
            if resposta_anotacao is not None:
                return resposta_anotacao
        resposta = RoteadorComandos(
            self.config,
            memoria=self.memoria,
            google_agenda=self.google_agenda,
            agenda_chat=self._agenda_chat,
        ).executar_interacao(mensagem)
        if resposta.agenda_alterada:
            self._cache_agenda_google = None
        return resposta

    def _classificar_destino_chat(self, mensagem: str) -> str:
        if self._agenda_chat is not None and self._agenda_chat.pedido_pendente is not None:
            return "agenda"
        normalizado = _normalizar_chat(mensagem)
        if self._anotacao_em_andamento and not _parece_pedido_agenda(normalizado):
            return "anotacao"
        if self.gemini_intencoes.disponivel():
            try:
                dados = self.gemini_intencoes.gerar_json(
                    _prompt_classificacao_chat(mensagem),
                    temperature=0.0,
                    schema_hint=(
                        '{"destino":"agenda|anotacao|outro",'
                        '"motivo":"justificativa curta"}'
                    ),
                )
            except Exception:
                return _classificar_destino_local(mensagem)
            destino = str(dados.get("destino", "")).strip().lower()
            if destino in {"agenda", "anotacao", "outro"}:
                return destino
        return _classificar_destino_local(mensagem)

    def _tentar_anotacao_chat(self, mensagem: str) -> RespostaRoteador | None:
        normalizado = _normalizar_chat(mensagem)
        if self._anotacao_em_andamento:
            if _confirma_fim_anotacao(normalizado):
                self._anotacao_em_andamento = False
                return RespostaRoteador("Combinado. Fechei essa anotacao por enquanto.")
            if _parece_pedido_agenda(normalizado):
                return None
            conteudo_extra = _limpar_texto_anotacao(mensagem)
            if conteudo_extra:
                self.anotacoes_chat.append(conteudo_extra)
                return RespostaRoteador(
                    "Anotei tambem. Seria apenas isso?",
                    anotacoes_alteradas=True,
                )
            return RespostaRoteador("Nao peguei o complemento. Pode repetir?")

        conteudo = _extrair_inicio_anotacao(mensagem)
        if not conteudo:
            return None
        self.anotacoes_chat.append(conteudo)
        self._anotacao_em_andamento = True
        return RespostaRoteador("Anotei. Mais alguma coisa?", anotacoes_alteradas=True)

    def salvar_perfil_pessoal(self, conteudo: str) -> str:
        """Mantem um resumo pessoal canonico para personalizar o assistente."""
        self.memoria.salvar_perfil_pessoal(conteudo)
        return "sqlite://perfil_pessoal"

    def _persistir_config(self) -> None:
        caminho = self.config.config_path
        if caminho is None:
            return
        caminho.write_text(renderizar_toml(self.config), encoding="utf-8")


def normalizar_lista_interesses(texto: str) -> list[str]:
    """Separa tags digitadas em linhas, virgulas ou ponto-e-virgula."""
    partes = texto.replace(";", ",").replace("\n", ",").split(",")
    interesses: list[str] = []
    interesses_casefold: set[str] = set()
    for parte in partes:
        interesse = " ".join(parte.strip().split())
        if interesse and interesse.casefold() not in interesses_casefold:
            interesses.append(interesse)
            interesses_casefold.add(interesse.casefold())
    return interesses


def _prompt_classificacao_chat(mensagem: str) -> str:
    return (
        "Voce classifica mensagens para uma secretaria virtual pessoal em pt-BR.\n"
        "Escolha exatamente um destino:\n"
        "- agenda: compromissos, consultas, reunioes, eventos, cancelar ou alterar calendario.\n"
        "- anotacao: listas, lembretes soltos, compras, ideias ou informacoes sem data/hora.\n"
        "- outro: conversa geral, clima, noticias, busca ou comandos que nao criam dado novo.\n"
        "Se a pessoa disser 'anote na minha agenda', use agenda. "
        "Se disser apenas 'anote que...', use anotacao, exceto quando houver compromisso "
        "com data ou horario.\n\n"
        f"Mensagem: {mensagem!r}\n"
        'Responda somente JSON como {"destino":"agenda","motivo":"..."}'
    )


def _classificar_destino_local(mensagem: str) -> str:
    normalizado = _normalizar_chat(mensagem)
    if _parece_pedido_agenda(normalizado):
        return "agenda"
    if _extrair_inicio_anotacao(mensagem):
        return "anotacao"
    return "outro"


def _extrair_inicio_anotacao(mensagem: str) -> str:
    normalizado = _normalizar_chat(mensagem)
    if "agenda" in normalizado:
        return ""
    match = re.search(
        r"(?i)\b(?:appa\s+)?anote(?:\s+que|:)?\s+(.+)$",
        mensagem.strip(),
    )
    if not match:
        return ""
    return _limpar_texto_anotacao(match.group(1))


def _limpar_texto_anotacao(texto: str) -> str:
    limpo = re.sub(r"(?i)\b(?:tamb[eé]m|por favor|favor)\b", " ", texto)
    limpo = re.sub(r"(?i)^\s*que\s+", " ", limpo)
    limpo = " ".join(limpo.strip(" -:,.").split())
    if not limpo:
        return ""
    return limpo[:1].upper() + limpo[1:]


def _normalizar_chat(texto: str) -> str:
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caractere) != "Mn"
    )
    return " ".join(sem_acentos.split())


def _confirma_fim_anotacao(texto_normalizado: str) -> bool:
    return texto_normalizado in {
        "sim",
        "s",
        "isso",
        "apenas isso",
        "so isso",
        "seria isso",
        "e isso",
    }


def _parece_pedido_agenda(texto_normalizado: str) -> bool:
    if "agenda" in texto_normalizado:
        return True
    return bool(
        re.search(
            r"\b(marque|marcar|agende|agendar|desmarque|desmarcar|cancele|cancelar)\b",
            texto_normalizado,
        )
    )


def _normalizar_noticia_para_memoria(noticia: Noticia | dict) -> dict[str, str]:
    if isinstance(noticia, Noticia):
        return {
            "titulo": noticia.titulo,
            "link": noticia.link,
            "fonte": noticia.fonte,
            "grupo": noticia.grupo,
        }
    return {
        "titulo": str(noticia.get("titulo") or "Noticia sem titulo"),
        "link": str(noticia.get("link") or ""),
        "fonte": str(noticia.get("fonte") or ""),
        "grupo": str(noticia.get("grupo") or ""),
    }


def _slug_tag(valor: str) -> str:
    return (
        valor.lower().replace(" ", "-").replace("_", "-").replace("/", "-").strip("-") or "noticia"
    )
