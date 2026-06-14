"""Casos de uso reutilizaveis pelo dashboard grafico."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

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
from assistente_pessoal.memoria import Memoria
from assistente_pessoal.noticias import (
    LIMITE_PADRAO_NOTICIAS,
    ClienteNoticias,
    Noticia,
)


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
        self.gerador_insights = GeradorInsightsDashboard(config)
        self._cache_clima: tuple[datetime, PrevisaoClima] | None = None
        self._cache_resumo_semana: tuple[datetime, list[ResumoClimaDia]] | None = None
        self._cache_cotacao_dolar: tuple[datetime, CotacaoMoeda] | None = None
        self._cache_noticias: tuple[datetime, list[Noticia]] | None = None
        self._cache_agenda_google: tuple[datetime, ResultadoGoogleAgenda] | None = None
        self._cache_clima_ontem: tuple[datetime, ResumoClimaDia | None] | None = None

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
