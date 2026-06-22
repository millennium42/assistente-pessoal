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
from assistente_pessoal.gui import (
    _criar_evento_google,
    _dashboard_js,
    _salvar_noticia_observada,
    construir_dashboard,
)
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


class NoticiasMutaveis(NoticiasFake):
    """Entrega uma manchete diferente a cada consulta."""

    def __init__(self) -> None:
        self.chamadas = 0

    def listar(self, *_args, **_kwargs) -> list[Noticia]:
        self.chamadas += 1
        return [
            Noticia(
                titulo=f"Manchete mutavel {self.chamadas}",
                link=f"https://noticias.test/{self.chamadas}",
                fonte="Fonte Mutavel",
                publicado="2026-06-08T12:00:00-03:00",
                publicado_em=datetime(2026, 6, 8, 12, 0),
                grupo="tech",
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
        destino = self.destinos.pop(0) if self.destinos else "conversa"
        return {
            "acao": "criar" if destino != "conversa" else "responder",
            "destino": destino,
            "mensagem_ao_usuario": "Ok",
            "conteudo": "teste",
            "precisa_confirmacao": False,
        }


class GeminiInsightsContador:
    """Conta chamadas usadas para gerar os insights do dashboard."""

    def __init__(self) -> None:
        self.chamadas = 0

    def disponivel(self) -> bool:
        return True

    def gerar_json(self, *_args, **_kwargs) -> dict:
        self.chamadas += 1
        return {
            "agenda": {"resumo": f"Agenda {self.chamadas}", "bullets": []},
            "noticias": {"resumo": f"Noticias {self.chamadas}", "bullets": []},
            "clima": {"resumo": f"Clima {self.chamadas}", "bullets": []},
            "assistente": {"resumo": f"Assistente {self.chamadas}", "bullets": []},
        }


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


def test_dashboard_service_conversa_operacional_marca_evento(tmp_path: Path) -> None:
    """Chat do painel usa o roteador operacional para criar eventos."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    servico.gemini_intencoes = GeminiIntencoesFake(["agenda_google"])

    resposta = servico.conversar("marque consulta em 2099-06-08 as 14h no consultorio")

    assert resposta.agenda_alterada is True
    assert servico.google_agenda.evento_criado is not None
    assert servico.google_agenda.evento_criado.titulo == "Consulta"


def test_dashboard_service_usa_gemini_para_anotacoes_em_turnos(tmp_path: Path) -> None:
    """Gemini decide que o pedido vai para o card de anotacoes."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    gemini = GeminiIntencoesFake(["anotacoes"])
    servico.gemini_intencoes = gemini

    primeira = servico.conversar("Appa anote que eu preciso passar no mercado pegar frutas")

    assert primeira.anotacoes_alteradas is True
    assert primeira.texto == "Ok"
    assert gemini.prompts


def test_dashboard_service_usa_gemini_para_agenda_em_turnos(tmp_path: Path) -> None:
    """Gemini decide que o pedido vai para agenda e o rascunho e completado depois."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    servico.gemini_intencoes = GeminiIntencoesFake(["agenda_google", "agenda_google"])

    pergunta = servico.conversar("Appa anote na minha agenda psicologo amanha")
    resposta = servico.conversar("15h30 no Henrique Ballen, na vitta ceter")

    assert pergunta.texto == "Que horario voce quer usar?"
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


def test_dashboard_service_exibe_bloqueio_sem_gemini(tmp_path: Path) -> None:
    """O dashboard mostra estado bloqueado caso o Gemini nao esteja configurado."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    snapshot = servico.carregar()

    assert snapshot.insights.motor == "Bloqueado"
    assert snapshot.insights.agenda.titulo == "Aguardando IA"
    assert snapshot.insights.noticias.titulo == "Aguardando IA"
    assert snapshot.insights.clima.titulo == "Aguardando IA"
    assert snapshot.insights.assistente.titulo == "Sistema bloqueado"
    assert "Gemini" in snapshot.insights.assistente.resumo


def test_dashboard_service_omite_erro_http_cru_do_gemini(tmp_path: Path) -> None:
    """Falhas 5xx devem virar bloqueio limpo, sem vazar a excecao bruta na GUI."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(servico.gerador_insights.gemini, "disponivel", lambda: True)
    monkeypatch.setattr(
        servico.gerador_insights.gemini,
        "gerar_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Server error 503")),
    )

    try:
        snapshot = servico.carregar()
    finally:
        monkeypatch.undo()

    assert snapshot.insights.motor == "Bloqueado"
    assert snapshot.insights.assistente.titulo == "Sistema bloqueado"
    assert "ficou indisponivel" in snapshot.insights.assistente.resumo.lower()
    assert "503" not in snapshot.insights.assistente.resumo


def test_dashboard_service_nao_confunde_eventos_da_semana_com_hoje(tmp_path: Path) -> None:
    """Se hoje nao tiver compromissos, o contexto factual de hoje deve ir vazio ao Gemini."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    capturado: dict[str, str] = {}
    monkeypatch = pytest.MonkeyPatch()

    class GoogleAgendaSoFuturo(GoogleAgendaFake):
        def obter_eventos_mes(self, referencia=None, *_args, **_kwargs) -> ResultadoGoogleAgenda:
            return ResultadoGoogleAgenda(
                eventos=[
                    EventoGoogleAgenda(
                        titulo="Reuniao da semana",
                        inicio="2099-06-09T11:00:00-03:00",
                        fim="2099-06-09T12:00:00-03:00",
                        link="",
                        local="",
                        origem="",
                    )
                ],
                mes_referencia=referencia,
            )

    class DateTimeHojeFixo(datetime):
        @classmethod
        def now(cls, tz=None):
            base = cls(2099, 6, 8, 9, 0, 0)
            return base if tz is None else base.astimezone(tz)

    servico.google_agenda = GoogleAgendaSoFuturo()
    monkeypatch.setattr("assistente_pessoal.painel.datetime", DateTimeHojeFixo)
    monkeypatch.setattr(servico.gerador_insights.gemini, "disponivel", lambda: True)

    def fake_gerar_json(prompt: str, **_kwargs) -> dict:
        capturado["prompt"] = prompt
        return {
            "agenda": {"resumo": "Sem compromissos hoje", "bullets": []},
            "noticias": {"resumo": "Feed sob controle", "bullets": []},
            "clima": {"resumo": "Clima estavel", "bullets": []},
            "assistente": {"resumo": "Dia sem agenda hoje", "bullets": []},
        }

    monkeypatch.setattr(servico.gerador_insights.gemini, "gerar_json", fake_gerar_json)

    try:
        snapshot = servico.carregar()
    finally:
        monkeypatch.undo()

    assert snapshot.insights.agenda.resumo == "Sem compromissos hoje"
    assert '"Agenda de Hoje: []"' not in capturado["prompt"]
    assert "Agenda de Hoje: []" in capturado["prompt"]
    assert "Reuniao da semana" in capturado["prompt"]


def test_dashboard_service_leva_comportamento_recorrente_para_os_insights(tmp_path: Path) -> None:
    """Comportamentos persistidos precisam voltar como contexto factual para o Gemini."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    servico.memoria.registrar_comportamento(
        "habito",
        "Costuma concentrar tarefas profundas pela manha.",
        "alto",
    )
    capturado: dict[str, str] = {}
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(servico.gerador_insights.gemini, "disponivel", lambda: True)

    def fake_gerar_json(prompt: str, **_kwargs) -> dict:
        capturado["prompt"] = prompt
        return {
            "agenda": {"resumo": "Dia organizado", "bullets": []},
            "noticias": {"resumo": "Feed sob controle", "bullets": []},
            "clima": {"resumo": "Clima estavel", "bullets": []},
            "assistente": {"resumo": "Mantive seu habito da manha em mente.", "bullets": []},
        }

    monkeypatch.setattr(servico.gerador_insights.gemini, "gerar_json", fake_gerar_json)

    try:
        snapshot = servico.carregar()
    finally:
        monkeypatch.undo()

    assert snapshot.insights.assistente.resumo == "Mantive seu habito da manha em mente."
    assert "Costuma concentrar tarefas profundas pela manha." in capturado["prompt"]


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
                    "Hoje fica mais frio que ontem, mas amanha a temperatura tende a recuperar."
                ),
                "bullets": [
                    ("Hoje fica mais frio que ontem, mas amanha a temperatura tende a recuperar."),
                    ("Hoje fica mais frio que ontem, mas amanha a temperatura tende a recuperar."),
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

    assert snapshot.insights.motor == "Gemini 3.1 Flash-Lite"
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


def test_dashboard_service_reaproveita_insights_dentro_do_ttl(tmp_path: Path) -> None:
    """Refresh automatico nao deve chamar Gemini de novo antes do TTL de insights."""
    config = AppConfig(db_path=tmp_path / "banco")
    config.dashboard.ttl_insights_segundos = 900
    servico = _servico_sem_rede(config)
    servico.noticias = NoticiasMutaveis()
    gemini = GeminiInsightsContador()
    servico.gerador_insights.gemini = gemini

    primeiro = servico.carregar()
    servico._cache_noticias = (datetime.now() - timedelta(seconds=120), [])
    segundo = servico.carregar()

    assert gemini.chamadas == 1
    assert primeiro.insights.assistente.resumo == segundo.insights.assistente.resumo
    assert servico.noticias.chamadas == 2


def test_dashboard_service_invalida_insights_ao_salvar_perfil(tmp_path: Path) -> None:
    """Mudanca local importante deve furar o TTL para atualizar contexto pessoal."""
    config = AppConfig(db_path=tmp_path / "banco")
    config.dashboard.ttl_insights_segundos = 900
    servico = _servico_sem_rede(config)
    gemini = GeminiInsightsContador()
    servico.gerador_insights.gemini = gemini

    servico.carregar()
    servico.salvar_perfil_pessoal("Novo perfil pessoal.")
    servico.carregar()

    assert gemini.chamadas == 2


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


def test_salvar_noticia_observada_usa_mensagem_da_memoria_appa(tmp_path: Path) -> None:
    """A GUI nao deve sugerir caminho markdown ao confirmar noticia salva."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)
    status = LabelFake()
    avisos: list[tuple[str, str | None]] = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "assistente_pessoal.gui.ui.notify",
        lambda texto, type=None: avisos.append((texto, type)),
    )

    try:
        _salvar_noticia_observada(
            servico,
            Noticia(
                titulo="Carga especial chama atencao",
                link="https://noticias.test/carga",
                fonte="Fonte",
                publicado="",
                grupo="santa_maria",
            ),
            status,
        )
    finally:
        monkeypatch.undo()

    assert status.text == "Noticia salva na memoria da APPA."
    assert avisos == [("Noticia salva na memoria da APPA.", "positive")]


def test_construir_dashboard_sem_subir_servidor(tmp_path: Path) -> None:
    """Constroi a arvore principal da GUI para capturar erros imediatos de import/layout."""
    config = AppConfig(db_path=tmp_path / "banco")
    config.fontes.noticias.interesses_busca = ["ia", "economia"]
    Memoria(config.db_path).salvar_nota("Teste", "Conteudo")

    construir_dashboard(_servico_sem_rede(config))


def test_construir_dashboard_reaproveita_estado_do_chat(tmp_path: Path) -> None:
    """O refresh da pagina nao deve reiniciar a conversa nem duplicar a saudacao."""
    config = AppConfig(db_path=tmp_path / "banco")
    servico = _servico_sem_rede(config)

    construir_dashboard(servico)
    primeira_rodada = list(servico.chat_historico)
    servico.chat_rascunho = "rascunho em andamento"
    construir_dashboard(servico)

    assert len(primeira_rodada) == 1
    assert servico.chat_historico == primeira_rodada
    assert servico.chat_rascunho == "rascunho em andamento"


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
    servico.gemini_intencoes = GeminiIntencoesFake(["agenda_google"])
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
    servico.gemini_intencoes = GeminiIntencoesFake(["agenda_google"])
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
