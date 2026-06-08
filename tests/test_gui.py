"""Testes leves do dashboard sem depender de navegador."""

from datetime import date, timedelta
from pathlib import Path

from assistente_pessoal.agenda_google import ResultadoGoogleAgenda
from assistente_pessoal.cambio import CotacaoMoeda
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
from assistente_pessoal.gui import _criar_evento_google, construir_dashboard
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.noticias import Noticia
from assistente_pessoal.painel import DashboardService


class ClimaFake:
    """Substitui a Open-Meteo nos testes do painel."""

    def obter_previsao(self, *_args, **_kwargs) -> PrevisaoClima:
        """Devolve uma previsao estavel para o snapshot."""
        return PrevisaoClima(
            cidade="Santa Maria, RS",
            data_alvo=date(2026, 6, 8),
            e_hoje=True,
            temperatura_referencia=19.1,
            sensacao=18.8,
            vento=12.0,
            maxima=21.0,
            minima=13.0,
            chuva=40.0,
            codigo_tempo=3,
        )

    def obter_resumo_semana(self, *_args, **_kwargs) -> list[ResumoClimaDia]:
        """Devolve sete dias para validar a faixa semanal sem rede."""
        return [
            ResumoClimaDia(
                data=date(2026, 6, dia),
                maxima=20.0 + indice,
                minima=12.0 + indice,
                chuva=10.0,
                codigo_tempo=3,
            )
            for indice, dia in enumerate(range(8, 15))
        ]


class NoticiasFake:
    """Substitui RSS e fontes externas no teste do dashboard service."""

    def listar(self, *_args, **_kwargs) -> list:
        """Mantem o teste focado no painel, nao em parsing de noticias."""
        return []


class CambioFake:
    """Substitui a API de cambio nos testes do painel."""

    def obter_dolar_real(self, *_args, **_kwargs) -> CotacaoMoeda:
        """Devolve uma cotacao estavel e sem rede."""
        return CotacaoMoeda(
            base="USD",
            destino="BRL",
            valor=5.25,
            variacao_percentual=0.4,
            maximo=5.3,
            minimo=5.2,
            horario=None,
            fonte="Teste",
        )


class GoogleAgendaFake:
    """Substitui chamadas ao Google Agenda no teste do dashboard service."""

    def __init__(self) -> None:
        """Guarda chamadas feitas pela GUI para assercoes."""
        self.evento_criado = None
        self.referencia = None

    def criar_evento(self, evento) -> None:
        """Registra o evento sem chamar a API real."""
        self.evento_criado = evento

    def obter_eventos_mes(self, referencia=None, *_args, **_kwargs) -> ResultadoGoogleAgenda:
        """Devolve calendario vazio e sem erro."""
        self.referencia = referencia
        return ResultadoGoogleAgenda(eventos=[], mes_referencia=referencia)


class LabelFake:
    """Objeto minimo com atributo text, como os labels da NiceGUI."""

    text = ""


def _servico_sem_rede(config: AppConfig) -> DashboardService:
    """Monta o service com fakes para evitar dependencia externa nos testes de GUI."""
    servico = DashboardService(config)
    servico.clima = ClimaFake()
    servico.noticias = NoticiasFake()
    servico.cambio = CambioFake()
    servico.google_agenda = GoogleAgendaFake()
    return servico


def test_dashboard_service_salva_documentos_fixos(tmp_path: Path) -> None:
    """Permite que GUI grave plano e agenda nos caminhos esperados do vault."""
    config = AppConfig(vault_path=tmp_path / "vault")
    servico = _servico_sem_rede(config)

    caminho_plano = servico.salvar_plano_estudos("Revisar algebra na segunda.")
    caminho_agenda = servico.salvar_agenda_local("10h - monitoria")

    assert caminho_plano == "60_planejamento/plano-estudos.md"
    assert caminho_agenda == "61_agenda_local/agenda-local.md"
    snapshot = servico.carregar()
    assert snapshot.indicadores.eventos_google == 0
    assert len(snapshot.resumo_semana) == 7
    assert snapshot.cotacao_dolar.valor == 5.25


def test_dashboard_service_salva_interesses_e_noticias(tmp_path: Path) -> None:
    """Organiza interesses e noticias relevantes no vault Obsidian."""
    config = AppConfig(vault_path=tmp_path / "vault")
    servico = _servico_sem_rede(config)

    interesses = servico.adicionar_interesses("ia, economia; IA")
    caminho_noticia = servico.salvar_noticia_obsidian(
        Noticia(
            titulo="IA chega ao mercado",
            link="https://noticias.test/ia",
            fonte="Fonte",
            publicado="",
            grupo="tech",
        )
    )

    assert interesses == ["ia", "economia"]
    assert caminho_noticia.startswith("40_noticias/")
    assert (tmp_path / "vault" / "10_memoria" / "interesses-de-pesquisa.md").exists()
    assert list((tmp_path / "vault" / "40_noticias").glob("*.md"))


def test_construir_dashboard_sem_subir_servidor(tmp_path: Path) -> None:
    """Constroi a arvore principal da GUI para capturar erros imediatos de import/layout."""
    config = AppConfig(vault_path=tmp_path / "vault")
    MemoriaObsidian(config.vault_path).salvar_nota("Teste", "Conteudo")

    construir_dashboard(DashboardService(config))


def test_criar_evento_google_na_gui_usa_servico_sem_api_real(monkeypatch, tmp_path: Path) -> None:
    """Valida o fluxo do botao de agenda sem criar evento real."""
    config = AppConfig(vault_path=tmp_path / "vault")
    servico = _servico_sem_rede(config)
    atualizacoes = []

    def popular_fake(*args) -> None:
        """Captura a atualizacao do calendario."""
        atualizacoes.append(args)

    monkeypatch.setattr("assistente_pessoal.gui._popular_agenda_google", popular_fake)
    status = LabelFake()
    painel_status = LabelFake()

    _criar_evento_google(
        servico,
        "Consulta",
        "2026-06-09",
        "14:30",
        45,
        "Sala 2",
        "Levar exames.",
        status,
        painel_status,
        object(),
        object(),
        object(),
        object(),
    )

    assert servico.google_agenda.evento_criado is not None
    assert servico.google_agenda.evento_criado.titulo == "Consulta"
    assert servico.google_agenda.evento_criado.local == "Sala 2"
    assert servico.google_agenda.evento_criado.descricao == "Levar exames."
    assert servico.google_agenda.evento_criado.fim - servico.google_agenda.evento_criado.inicio == (
        timedelta(minutes=45)
    )
    assert servico.google_agenda.referencia == date(2026, 6, 9)
    assert atualizacoes
    assert status.text == "Evento criado no Google Agenda."
    assert painel_status.text == "Google Agenda atualizada com sucesso."


def test_criar_evento_google_na_gui_valida_data_hora(tmp_path: Path) -> None:
    """Impede chamada ao Google quando a data ou hora esta em formato invalido."""
    config = AppConfig(vault_path=tmp_path / "vault")
    servico = _servico_sem_rede(config)
    status = LabelFake()

    _criar_evento_google(
        servico,
        "Consulta",
        "09/06/2026",
        "14:30",
        45,
        "",
        "",
        status,
        LabelFake(),
        object(),
        object(),
        object(),
        object(),
    )

    assert servico.google_agenda.evento_criado is None
    assert status.text == "Use data no formato AAAA-MM-DD e hora no formato HH:MM."
