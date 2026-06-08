"""Casos de uso reutilizaveis pelo dashboard grafico."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from assistente_pessoal.agenda_google import ClienteGoogleAgenda, EventoGoogleAgenda
from assistente_pessoal.clima import ClienteClima, PrevisaoClima
from assistente_pessoal.config import AppConfig
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.noticias import ClienteNoticias, Noticia


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
    noticias: list[Noticia]
    notas_recentes: list[str]
    plano_estudos: str
    agenda_local: str
    agenda_google: list[EventoGoogleAgenda]
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
        self.google_agenda = ClienteGoogleAgenda(config.google_agenda)

    def carregar(self, dia_clima: str | None = None, limite_noticias: int = 8) -> DashboardSnapshot:
        """Monta um snapshot unico para reduzir chamadas espalhadas na interface."""
        previsao = self.clima.obter_previsao(self.config.localizacao, dia=dia_clima)
        noticias = self.noticias.listar(self.config.fontes.noticias, limite=limite_noticias)
        notas = [
            self.memoria.caminho_relativo(caminho) for caminho in self.memoria.listar_recentes()
        ]
        plano_estudos = self.memoria.ler_documento_fixo("60_planejamento", "plano-estudos.md")
        agenda_local = self.memoria.ler_documento_fixo("61_agenda_local", "agenda-local.md")
        agenda_google = self.google_agenda.listar_eventos()
        contagem_grupos = Counter(noticia.grupo for noticia in noticias)
        return DashboardSnapshot(
            previsao=previsao,
            noticias=noticias,
            notas_recentes=notas,
            plano_estudos=plano_estudos,
            agenda_local=agenda_local,
            agenda_google=agenda_google,
            indicadores=IndicadoresDashboard(
                total_noticias=len(noticias),
                noticias_the_news=contagem_grupos.get("the_news", 0),
                noticias_santa_maria=contagem_grupos.get("santa_maria", 0),
                notas_recentes=len(notas),
                eventos_google=len(agenda_google),
            ),
            noticias_por_grupo=dict(contagem_grupos),
            atualizado_em=datetime.now().strftime("%H:%M:%S"),
        )

    def salvar_nota_rapida(self, titulo: str, conteudo: str) -> str:
        """Cria uma nota curta no vault e devolve o caminho relativo gerado."""
        caminho = self.memoria.salvar_nota(titulo=titulo, conteudo=conteudo, pasta="10_memoria")
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
