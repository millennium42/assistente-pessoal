"""Testes leves do dashboard sem depender de navegador."""

import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from assistente_pessoal.agenda_google import EventoGoogleAgenda, ResultadoGoogleAgenda
from assistente_pessoal.cambio import CotacaoMoeda
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
from assistente_pessoal.gui import _criar_evento_google, _dashboard_js, construir_dashboard
from assistente_pessoal.memoria import Memoria
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

    def obter_resumo_historico(self, *_args, **_kwargs) -> ResumoClimaDia:
        """Oferece o recorte de ontem para os insights de clima."""
        return ResumoClimaDia(
            data=date(2026, 6, 7),
            maxima=18.0,
            minima=11.0,
            chuva=20.0,
            codigo_tempo=3,
        )


class ClimaContador(ClimaFake):
    """Conta quantas vezes o clima foi consultado para validar o cache."""

    def __init__(self) -> None:
        self.previsao_chamadas = 0
        self.resumo_chamadas = 0

    def obter_previsao(self, *_args, **_kwargs) -> PrevisaoClima:
        self.previsao_chamadas += 1
        return super().obter_previsao(*_args, **_kwargs)

    def obter_resumo_semana(self, *_args, **_kwargs) -> list[ResumoClimaDia]:
        self.resumo_chamadas += 1
        return super().obter_resumo_semana(*_args, **_kwargs)


class NoticiasFake:
    """Substitui RSS e fontes externas no teste do dashboard service."""

    def listar(self, *_args, **_kwargs) -> list:
        """Mantem o teste focado no painel, nao em parsing de noticias."""
        return []


class NoticiasFakeComPublicacao(NoticiasFake):
    """Entrega uma noticia completa para validar os insights do feed."""

    def listar(self, *_args, **_kwargs) -> list[Noticia]:
        return [
            Noticia(
                titulo="UFSM abre novo edital de pesquisa",
                link="https://noticias.test/ufsm-edital",
                fonte="Portal Teste",
                publicado="2026-06-08T12:00:00-03:00",
                publicado_em=datetime(2026, 6, 8, 12, 0),
                grupo="interesses",
            )
        ]


class NoticiasContador(NoticiasFake):
    """Conta consultas ao feed para validar o cache curto de noticias."""

    def __init__(self) -> None:
        self.chamadas = 0

    def listar(self, *_args, **_kwargs) -> list:
        self.chamadas += 1
        return super().listar(*_args, **_kwargs)


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


class CambioContador(CambioFake):
    """Conta leituras da cotacao para validar a janela curta do dolar."""

    def __init__(self) -> None:
        self.chamadas = 0

    def obter_dolar_real(self, *_args, **_kwargs) -> CotacaoMoeda:
        self.chamadas += 1
        return super().obter_dolar_real(*_args, **_kwargs)


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
        return ResultadoGoogleAgenda(
            eventos=[
                EventoGoogleAgenda(
                    titulo="Passado",
                    inicio="2026-06-08T08:00:00-03:00",
                    fim="2026-06-08T09:00:00-03:00",
                    link="",
                    local="",
                    origem="",
                ),
                EventoGoogleAgenda(
                    titulo="Futuro",
                    inicio="2099-06-08T11:00:00-03:00",
                    fim="2099-06-08T12:00:00-03:00",
                    link="",
                    local="",
                    origem="",
                ),
            ],
            mes_referencia=referencia,
        )


class GoogleAgendaContador(GoogleAgendaFake):
    """Conta leituras da agenda para validar o cache mais longo."""

    def __init__(self) -> None:
        super().__init__()
        self.chamadas = 0

    def obter_eventos_mes(self, referencia=None, *_args, **_kwargs) -> ResultadoGoogleAgenda:
        self.chamadas += 1
        return super().obter_eventos_mes(referencia, *_args, **_kwargs)


class GeminiIntencoesFake:
    """Classificador Gemini fake para validar o roteamento do chat."""

    def __init__(self, destinos: list[str]) -> None:
        self.destinos = destinos
        self.prompts: list[str] = []

    def disponivel(self) -> bool:
        return True

    def gerar_json(self, prompt: str, **_kwargs) -> dict:
        self.prompts.append(prompt)
        destino = self.destinos.pop(0) if self.destinos else "outro"
        return {"destino": destino, "motivo": "teste"}


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
    """Permite que GUI grave plano e agenda nos caminhos esperados do banco."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    caminho_agenda = servico.salvar_agenda_local("10h - monitoria")

    assert caminho_agenda == "61_agenda_local/agenda-local.md"
    snapshot = servico.carregar()
    assert snapshot.indicadores.eventos_google == 1
    assert len(snapshot.resumo_semana) == 7
    assert snapshot.cotacao_dolar.valor == 5.25
    assert snapshot.insights.motor == "Local"
    assert snapshot.clima_ontem is not None


def test_dashboard_service_conversa_operacional_marca_evento(tmp_path: Path) -> None:
    """Chat do painel usa o roteador operacional para criar eventos."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    resposta = servico.conversar("marque consulta em 2099-06-08 as 14h no consultorio")

    assert resposta.agenda_alterada is True
    assert servico.google_agenda.evento_criado is not None
    assert servico.google_agenda.evento_criado.titulo == "Consulta"


def test_dashboard_service_usa_gemini_para_anotacoes_em_turnos(tmp_path: Path) -> None:
    """Gemini decide que o pedido vai para o card de anotacoes."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    gemini = GeminiIntencoesFake(["anotacao"])
    servico.gemini_intencoes = gemini

    primeira = servico.conversar("Appa anote que eu preciso passar no mercado pegar frutas")
    segunda = servico.conversar("Sabonete também por favor")
    final = servico.conversar("Sim")

    assert primeira.anotacoes_alteradas is True
    assert primeira.texto == "Anotei. Mais alguma coisa?"
    assert segunda.anotacoes_alteradas is True
    assert segunda.texto == "Anotei tambem. Seria apenas isso?"
    assert final.texto == "Combinado. Fechei essa anotacao por enquanto."
    assert servico.anotacoes_chat == [
        "Eu preciso passar no mercado pegar frutas",
        "Sabonete",
    ]
    assert gemini.prompts


def test_dashboard_service_usa_gemini_para_agenda_em_turnos(tmp_path: Path) -> None:
    """Gemini decide que o pedido vai para agenda e o rascunho e completado depois."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    servico.gemini_intencoes = GeminiIntencoesFake(["agenda"])

    pergunta = servico.conversar("Appa anote na minha agenda psicologo amanha")
    resposta = servico.conversar("15h30 no Henrique Ballen, na vitta ceter")

    assert pergunta.texto == "Que horas e onde?"
    assert resposta.agenda_alterada is True
    assert servico.google_agenda.evento_criado is not None
    assert servico.google_agenda.evento_criado.titulo == "Psicologo"
    assert servico.google_agenda.evento_criado.local == "Henrique Ballen, na vitta ceter"


def test_dashboard_service_salva_perfil_pessoal(tmp_path: Path) -> None:
    """Usa um documento canonico de perfil para orientar os insights."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    caminho = servico.salvar_perfil_pessoal("Sou professor, gosto de foco pela manhã.")
    snapshot = servico.carregar()

    assert caminho == "sqlite://perfil_pessoal"
    assert "professor" in snapshot.perfil_pessoal
    assert snapshot.insights.agenda.resumo
    assert snapshot.insights.noticias.resumo
    assert snapshot.insights.clima.resumo
    assert snapshot.insights.assistente.resumo


def test_dashboard_service_gera_bullet_de_noticia_mais_recente(tmp_path: Path) -> None:
    """Mantem o card de noticias como resumo, sem reciclar manchetes em destaque."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    servico.noticias = NoticiasFakeComPublicacao()

    snapshot = servico.carregar()

    assert snapshot.insights.noticias.resumo
    assert snapshot.insights.noticias.bullets
    assert snapshot.insights.noticias.titulo == "Resumo das noticias"
    assert "UFSM abre novo edital de pesquisa" not in snapshot.insights.noticias.bullets[0]
    assert "feed" in snapshot.insights.noticias.bullets[0].lower()


def test_dashboard_service_compara_clima_hoje_ontem_e_amanha(tmp_path: Path) -> None:
    """Resume o clima comparando hoje com ontem e amanha com hoje."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    snapshot = servico.carregar()

    assert snapshot.insights.clima.titulo == "Comparativo do clima"
    assert "ontem" in snapshot.insights.clima.resumo.lower()
    assert "amanha" in snapshot.insights.clima.resumo.lower()
    assert not snapshot.insights.clima.bullets[0].startswith("Hoje vs ontem:")
    assert not snapshot.insights.clima.bullets[1].startswith("Amanha vs hoje:")
    assert any("Maxima de" in bullet for bullet in snapshot.insights.clima.bullets)
    assert snapshot.insights.assistente.titulo == "Sua secretaria virtual"
    assert len(snapshot.insights.assistente.bullets) >= 4
    assert "orientar" in snapshot.insights.assistente.bullets[0].lower()
    assert "noticiario" in snapshot.insights.assistente.resumo.lower()
    assert "triagem executiva" in snapshot.insights.assistente.bullets[-1].lower()


def test_dashboard_service_remove_repeticao_do_clima_via_gemini(tmp_path: Path) -> None:
    """Evita que o resumo e os bullets de clima repitam exatamente a mesma ideia."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        servico.gerador_insights.gemini,
        "disponivel",
        lambda: True,
    )
    monkeypatch.setattr(
        servico.gerador_insights.gemini,
        "gerar_json",
        lambda *args, **kwargs: {
            "agenda": {"resumo": "Dia tranquilo", "bullets": ["Primeiro bloco livre"]},
            "noticias": {"resumo": "Feed equilibrado", "bullets": ["Mais peso em Santa Maria"]},
            "clima": {
                "resumo": (
                    "Hoje fica mais frio que ontem, mas amanha a temperatura tende a "
                    "recuperar."
                ),
                "bullets": [
                    (
                        "Hoje fica mais frio que ontem, mas amanha a temperatura tende a "
                        "recuperar."
                    ),
                    (
                        "Hoje fica mais frio que ontem, mas amanha a temperatura tende a "
                        "recuperar."
                    ),
                    "Maxima de 21 C e minima de 13 C.",
                    (
                        "Vale sair com camadas leves com casaco fino; vale levar "
                        "guarda-chuva compacto."
                    ),
                ],
            },
            "assistente": {
                "resumo": (
                    "Dia bom para priorizar compromissos, observar o clima e filtrar o feed "
                    "com mais calma para focar no que realmente importa."
                ),
                "bullets": [
                    "Comece pelo compromisso mais cedo e ajuste a saida por causa do frio.",
                    "O feed sugere menos volume e mais seletividade nas leituras de hoje.",
                    "Se sobrar energia, vale revisar os temas que combinam com seus interesses.",
                    "Mantenha atencao extra ao que pode influenciar sua rotina pratica hoje.",
                    "Use este card como sintese do que merece mais energia ao longo do dia.",
                ],
            },
        },
    )

    try:
        snapshot = servico.carregar()
    finally:
        monkeypatch.undo()

    assert snapshot.insights.motor == "Gemini"
    assert snapshot.insights.clima.resumo
    assert snapshot.insights.clima.bullets
    assert len(snapshot.insights.clima.bullets) == len(set(snapshot.insights.clima.bullets))
    assert snapshot.insights.clima.resumo not in snapshot.insights.clima.bullets
    assert snapshot.insights.assistente.resumo.startswith("Dia bom para priorizar")
    assert len(snapshot.insights.assistente.bullets) >= 5


def test_dashboard_service_reaproveita_cache_externo_entre_refreshes(tmp_path: Path) -> None:
    """Evita repetir chamadas externas quando a GUI refresca antes do TTL expirar."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = DashboardService(config)
    servico.clima = ClimaContador()
    servico.noticias = NoticiasContador()
    servico.cambio = CambioContador()
    servico.google_agenda = GoogleAgendaContador()

    servico.carregar()
    servico.carregar()

    assert servico.clima.previsao_chamadas == 1
    assert servico.clima.resumo_chamadas == 1
    assert servico.noticias.chamadas == 1
    assert servico.cambio.chamadas == 1
    assert servico.google_agenda.chamadas == 1


def test_dashboard_service_salva_interesses_e_noticias(tmp_path: Path) -> None:
    """Organiza interesses e noticias relevantes no banco SQLite."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    interesses = servico.adicionar_interesses("ia, economia; IA")
    caminho_noticia = servico.salvar_noticia_relevante(
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
    assert servico.memoria.listar_interesses() == ["ia", "economia"]
    assert servico.memoria.listar_interacoes_noticias(limite=1)[0].titulo == "IA chega ao mercado"
    assert servico.memoria.buscar("IA chega ao mercado")

    interesses = servico.remover_interesse("IA")

    assert interesses == ["economia"]
    assert servico.config.fontes.noticias.interesses_busca == ["economia"]
    assert servico.memoria.listar_interesses() == ["economia"]


def test_construir_dashboard_sem_subir_servidor(tmp_path: Path) -> None:
    """Constroi a arvore principal da GUI para capturar erros imediatos de import/layout."""
    config = AppConfig(db_path=tmp_path / "banco")
    config.fontes.noticias.interesses_busca = ["ia", "economia"]
    Memoria(config.db_path).salvar_nota("Teste", "Conteudo")

    construir_dashboard(_servico_sem_rede(config))


def test_dashboard_js_do_tema_e_sintaticamente_valido() -> None:
    """Captura regressao em que o tema nao inicializa por JS invalido."""
    node_path = shutil.which("node")
    if node_path is None:
        pytest.skip("Node.js indisponivel para validar JS do dashboard")

    result = subprocess.run(
        [node_path, "--check", "-"],
        input=_dashboard_js(),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "appa-dashboard-theme" in _dashboard_js()
    assert "themeClickHandler" in _dashboard_js()


def test_criar_evento_google_na_gui_usa_servico_sem_api_real(monkeypatch, tmp_path: Path) -> None:
    """Valida o fluxo do botao de agenda sem criar evento real."""
    config = AppConfig(db_path=tmp_path / "banco")
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
    config = AppConfig(db_path=tmp_path / "banco")
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
