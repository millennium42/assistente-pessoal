"""Casos de uso reutilizaveis pelo dashboard grafico."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from assistente_pessoal.agenda_google import (
    ClienteGoogleAgenda,
    EventoGoogleAgenda,
    ResultadoGoogleAgenda,
    evento_google_ainda_futuro,
)
from assistente_pessoal.cambio import ClienteCambio, CotacaoMoeda
from assistente_pessoal.clima import ClienteClima, PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig, renderizar_toml
from assistente_pessoal.memoria import MemoriaObsidian
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
    plano_estudos: str
    agenda_local: str
    agenda_google: list[EventoGoogleAgenda]
    agenda_google_resultado: ResultadoGoogleAgenda
    indicadores: IndicadoresDashboard
    noticias_por_grupo: dict[str, int]
    atualizado_em: str


class DashboardService:
    """Centraliza a leitura dos dados exibidos no dashboard."""

    def __init__(self, config: AppConfig) -> None:
        """Instancia os servicos de dominio usados pela GUI."""
        self.config = config
        self.memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
        self.noticias = ClienteNoticias()
        self.clima = ClienteClima()
        self.cambio = ClienteCambio()
        self.google_agenda = ClienteGoogleAgenda(config.google_agenda)

    def carregar(
        self,
        dia_clima: str | None = None,
        limite_noticias: int = LIMITE_PADRAO_NOTICIAS,
    ) -> DashboardSnapshot:
        """Monta um snapshot unico para reduzir chamadas espalhadas na interface."""
        previsao = self.clima.obter_previsao(self.config.localizacao, dia=dia_clima)
        resumo_semana = self._carregar_resumo_semana()
        cotacao_dolar = self._carregar_cotacao_dolar()
        noticias = self.noticias.listar(self.config.fontes.noticias, limite=limite_noticias)
        santa_maria_em_foco = self._carregar_santa_maria_em_foco(noticias)
        notas = [
            self.memoria.caminho_relativo(caminho) for caminho in self.memoria.listar_recentes()
        ]
        plano_estudos = self.memoria.ler_documento_fixo("60_planejamento", "plano-estudos.md")
        agenda_local = self.memoria.ler_documento_fixo("61_agenda_local", "agenda-local.md")
        agenda_google_resultado = self.google_agenda.obter_eventos_mes()
        agenda_google = agenda_google_resultado.eventos
        agenda_google_futuros = [
            evento
            for evento in agenda_google
            if evento_google_ainda_futuro(evento, self.config.localizacao.timezone)
        ]
        contagem_grupos = Counter(noticia.grupo for noticia in noticias)
        return DashboardSnapshot(
            previsao=previsao,
            resumo_semana=resumo_semana,
            cotacao_dolar=cotacao_dolar,
            noticias=noticias,
            santa_maria_em_foco=santa_maria_em_foco,
            notas_recentes=notas,
            plano_estudos=plano_estudos,
            agenda_local=agenda_local,
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
            atualizado_em=datetime.now().strftime("%H:%M:%S"),
        )

    def _carregar_resumo_semana(self) -> list[ResumoClimaDia]:
        """Busca a faixa semanal de clima sem derrubar o painel em falha secundaria."""
        try:
            return self.clima.obter_resumo_semana(self.config.localizacao, dias=7)
        except Exception:
            return []

    def _carregar_cotacao_dolar(self) -> CotacaoMoeda:
        """Busca USD/BRL sem deixar uma falha externa derrubar o dashboard."""
        try:
            return self.cambio.obter_dolar_real(self.config.localizacao.timezone)
        except Exception as exc:
            return CotacaoMoeda(
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

    def _carregar_santa_maria_em_foco(self, noticias: list[Noticia]) -> list[Noticia]:
        """Mantem o bloco local restrito ao recorte atual de Santa Maria."""
        locais_hoje = [noticia for noticia in noticias if noticia.grupo == "santa_maria"]
        return locais_hoje[:6]

    def salvar_nota_rapida(self, titulo: str, conteudo: str) -> str:
        """Cria uma nota curta no vault e devolve o caminho relativo gerado."""
        caminho = self.memoria.salvar_nota(titulo=titulo, conteudo=conteudo, pasta="10_memoria")
        return self.memoria.caminho_relativo(caminho)

    def adicionar_interesses(self, texto: str) -> list[str]:
        """Adiciona termos de interesse, persiste no config e organiza no Obsidian."""
        novos = normalizar_lista_interesses(texto)
        existentes = list(self.config.fontes.noticias.interesses_busca)
        existentes_casefold = {item.casefold() for item in existentes}
        for interesse in novos:
            if interesse.casefold() not in existentes_casefold:
                existentes.append(interesse)
                existentes_casefold.add(interesse.casefold())
        self.config.fontes.noticias.interesses_busca = existentes
        self._persistir_config()
        self._salvar_documento_interesses()
        return existentes

    def salvar_noticia_obsidian(self, noticia: Noticia | dict, origem: str = "clique") -> str:
        """Guarda uma noticia relevante no Obsidian para leitura e busca futuras."""
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
        tags = ["noticia", "obsidian", _slug_tag(item["grupo"])]
        if origem:
            tags.append(_slug_tag(origem))
        caminho = self.memoria.salvar_nota(
            titulo=item["titulo"],
            conteudo=conteudo,
            pasta="40_noticias",
            tags=tags,
        )
        return self.memoria.caminho_relativo(caminho)

    def registrar_consulta_noticias(self, consulta: str, noticias: list[Noticia]) -> str:
        """Salva no Obsidian o conjunto de noticias retornado para uma pergunta."""
        linhas = [f"Pergunta: {consulta}", "", "## Noticias retornadas", ""]
        for noticia in noticias:
            linhas.append(f"- [{noticia.titulo}]({noticia.link})")
            linhas.append(f"  - Fonte: {noticia.fonte}")
            linhas.append(f"  - Grupo: {noticia.grupo}")
        caminho = self.memoria.salvar_nota(
            titulo="Consulta de noticias",
            conteudo="\n".join(linhas),
            pasta="40_noticias",
            tags=["noticias", "consulta", "obsidian"],
        )
        return self.memoria.caminho_relativo(caminho)

    def salvar_plano_estudos(self, conteudo: str) -> str:
        """Atualiza o documento canonico de planejamento de estudos."""
        caminho = self.memoria.salvar_documento_fixo(
            nome_arquivo="plano-estudos.md",
            conteudo=conteudo,
            pasta="60_planejamento",
            titulo="Plano de estudos",
            tags=["planejamento", "estudos"],
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

    def _salvar_documento_interesses(self) -> str:
        interesses = self.config.fontes.noticias.interesses_busca
        conteudo = "\n".join(f"- {interesse}" for interesse in interesses)
        caminho = self.memoria.salvar_documento_fixo(
            nome_arquivo="interesses-de-pesquisa.md",
            conteudo=conteudo or "- Nenhum interesse cadastrado ainda.",
            pasta="10_memoria",
            titulo="Interesses de pesquisa",
            tags=["perfil", "interesses", "busca"],
        )
        return self.memoria.caminho_relativo(caminho)

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
