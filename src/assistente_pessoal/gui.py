"""Dashboard grafico local baseado em NiceGUI."""

from __future__ import annotations

import socket

from nicegui import ui

from assistente_pessoal.clima import PrevisaoClima
from assistente_pessoal.config import AppConfig
from assistente_pessoal.logs import avisar
from assistente_pessoal.noticias import Noticia, texto_terminal_seguro
from assistente_pessoal.painel import DashboardService, DashboardSnapshot

GRUPOS_LABEL = {
    "the_news": "The News",
    "santa_maria": "Santa Maria",
    "tech": "Tech",
    "economia_global": "Economia Global",
}

GRUPOS_COR = {
    "the_news": "#1d4ed8",
    "santa_maria": "#0f766e",
    "tech": "#7c3aed",
    "economia_global": "#b45309",
}


def resolver_porta_dashboard(host: str, porta_preferida: int, tentativas: int = 20) -> int:
    """Escolhe uma porta livre para o dashboard a partir da preferida."""
    for porta in range(porta_preferida, porta_preferida + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, porta))
            except OSError:
                continue
            return porta
    ultima_porta = porta_preferida + tentativas - 1
    raise RuntimeError(f"Nao encontrei uma porta livre entre {porta_preferida} e {ultima_porta}.")


def iniciar_dashboard(
    config: AppConfig,
    host: str = "127.0.0.1",
    port: int = 8765,
    titulo: str = "Assistente Pessoal",
) -> None:
    """Inicializa e executa a GUI local no navegador."""
    servico = DashboardService(config)
    try:
        snapshot_inicial = servico.carregar()
    except Exception:
        snapshot_inicial = None
    ui.run(
        host=host,
        port=port,
        title=titulo,
        reload=False,
        show=False,
        root=lambda: construir_dashboard(servico, snapshot_inicial=snapshot_inicial),
    )


def construir_dashboard(
    servico: DashboardService,
    snapshot_inicial: DashboardSnapshot | None = None,
) -> None:
    """Constroi um dashboard denso, visual e voltado a acompanhamento diario."""
    ui.add_head_html(
        """
        <style>
        body { background: #edf2f7; color: #0f172a; }
        .shell { max-width: 1520px; margin: 0 auto; padding: 20px 24px 28px; }
        .hero {
          background: linear-gradient(135deg, #0f172a 0%, #1e293b 70%, #334155 100%);
          color: white;
          border-radius: 8px;
          padding: 20px 24px;
        }
        .hero-kicker {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: rgba(255,255,255,0.72);
        }
        .toolbar {
          background: rgba(255,255,255,0.82);
          border: 1px solid #dbe4f0;
          border-radius: 8px;
          padding: 12px 14px;
        }
        .kpi {
          background: white;
          border: 1px solid #dbe4f0;
          border-radius: 8px;
          padding: 14px;
          min-height: 110px;
        }
        .kpi-label { font-size: 0.82rem; color: #64748b; }
        .kpi-value {
          font-size: 2rem;
          font-weight: 700;
          line-height: 1.1;
          margin-top: 10px;
        }
        .section {
          background: white;
          border: 1px solid #dbe4f0;
          border-radius: 8px;
          padding: 16px;
        }
        .section-title { font-size: 1rem; font-weight: 700; color: #0f172a; }
        .section-subtitle { font-size: 0.84rem; color: #64748b; }
        .stat-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 10px;
        }
        .stat-box {
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 10px 12px;
          background: #f8fafc;
        }
        .surface { background: transparent; }
        </style>
        """
    )
    with ui.column().classes("shell gap-4"):
        _cabecalho(snapshot_inicial)
        with ui.row().classes("toolbar items-end gap-3 w-full"):
            seletor_dia = ui.toggle(
                {
                    "hoje": "Hoje",
                    "amanha": "Amanha",
                    "segunda": "Seg",
                    "terca": "Ter",
                    "quarta": "Qua",
                    "quinta": "Qui",
                    "sexta": "Sex",
                },
                value="hoje",
            ).props("unelevated")
            limite_noticias = ui.number(
                label="Noticias",
                value=8,
                min=4,
                max=20,
                step=1,
                format="%.0f",
            ).classes("w-32")
            atualizacao_auto = ui.switch("Atualizacao automatica", value=False)
            status = ui.label("Painel pronto.").classes("text-sm text-slate-500 ml-auto")

        kpi_cards = _criar_kpis(snapshot_inicial)
        with ui.grid(columns=4).classes("w-full gap-3"):
            for card in kpi_cards:
                with ui.element("div").classes("kpi"):
                    ui.label(card["label"]).classes("kpi-label")
                    valor = ui.label(card["value"]).classes("kpi-value")
                    detalhe = ui.label(card["detail"]).classes("text-sm text-slate-500")
                    card["widgets"] = (valor, detalhe)

        with ui.grid(columns=3).classes("w-full gap-4"):
            with ui.column().classes("col-span-2 gap-4"):
                with ui.element("section").classes("section gap-3"):
                    ui.label("Radar do Dia").classes("section-title")
                    ui.label("Clima alvo, distribuicao das fontes e noticias priorizadas.").classes(
                        "section-subtitle"
                    )
                    with ui.grid(columns=2).classes("w-full gap-4"):
                        clima_resumo = _render_clima_resumo(snapshot_inicial)
                        contagens = snapshot_inicial.noticias_por_grupo if snapshot_inicial else {}
                        grafico_grupos = ui.echart(_opcoes_grafico(contagens)).classes(
                            "w-full h-72"
                        )

                with ui.element("section").classes("section gap-3"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("Feed Priorizado").classes("section-title")
                        noticias_total = ui.label("").classes("text-sm text-slate-500")

                    linhas_iniciais = _linhas_noticias(
                        snapshot_inicial.noticias if snapshot_inicial else []
                    )
                    tabela_noticias = ui.table(
                        columns=[
                            {
                                "name": "prioridade",
                                "label": "Prioridade",
                                "field": "prioridade",
                            },
                            {"name": "grupo", "label": "Grupo", "field": "grupo"},
                            {"name": "fonte", "label": "Fonte", "field": "fonte"},
                            {"name": "titulo", "label": "Titulo", "field": "titulo"},
                            {"name": "publicado", "label": "Publicado", "field": "publicado"},
                        ],
                        rows=linhas_iniciais,
                        row_key="id",
                        pagination=8,
                    ).classes("w-full")
                    tabela_noticias.add_slot(
                        "body-cell-titulo",
                        """
                        <q-td :props="props">
                          <a
                            :href="props.row.link"
                            target="_blank"
                            style="color:#0f172a;text-decoration:none;font-weight:600;"
                          >
                            {{ props.row.titulo }}
                          </a>
                        </q-td>
                        """,
                    )
                    tabela_noticias.add_slot(
                        "body-cell-grupo",
                        """
                        <q-td :props="props">
                          <span
                            :style="`
                              background:${props.row.cor};
                              color:white;
                              padding:4px 10px;
                              border-radius:999px;
                              font-size:12px;
                              font-weight:600;
                              display:inline-flex;
                            `"
                          >
                            {{ props.row.grupo }}
                          </span>
                        </q-td>
                        """,
                    )

            with ui.column().classes("gap-4"):
                with ui.element("section").classes("section gap-3"):
                    ui.label("Trabalho no Vault").classes("section-title")
                    notas_recentes = ui.column().classes("gap-2")
                    if snapshot_inicial:
                        _popular_notas_recentes(notas_recentes, snapshot_inicial.notas_recentes)
                    else:
                        _popular_notas_recentes(notas_recentes, [])

                with ui.element("section").classes("section gap-3"):
                    ui.label("Planejamento").classes("section-title")
                    with ui.tabs().classes("w-full") as abas:
                        aba_nota = ui.tab("Nota rapida")
                        aba_plano = ui.tab("Plano de estudos")
                        aba_agenda = ui.tab("Agenda local")

                    with ui.tab_panels(abas, value=aba_nota).classes("w-full"):
                        with ui.tab_panel(aba_nota).classes("surface"):
                            titulo_nota = ui.input("Titulo da nota").classes("w-full")
                            conteudo_nota = ui.textarea("Conteudo").classes("w-full")
                            conteudo_nota.props("rows=8")
                            caminho_nota = ui.label("").classes("text-sm text-slate-500")
                            ui.button(
                                "Salvar nota",
                                on_click=lambda: _salvar_nota(
                                    servico,
                                    titulo_nota.value,
                                    conteudo_nota.value,
                                    caminho_nota,
                                    status,
                                    notas_recentes,
                                ),
                            ).classes("w-full")

                        with ui.tab_panel(aba_plano).classes("surface"):
                            plano_texto = ui.textarea("Plano de estudos").classes("w-full")
                            plano_texto.props("rows=12")
                            plano_texto.value = (
                                snapshot_inicial.plano_estudos if snapshot_inicial else ""
                            )
                            plano_status = ui.label("").classes("text-sm text-slate-500")
                            ui.button(
                                "Salvar plano",
                                on_click=lambda: _salvar_documento(
                                    servico.salvar_plano_estudos,
                                    plano_texto.value,
                                    plano_status,
                                    status,
                                ),
                            ).classes("w-full")

                        with ui.tab_panel(aba_agenda).classes("surface"):
                            agenda_texto = ui.textarea("Agenda local").classes("w-full")
                            agenda_texto.props("rows=12")
                            agenda_texto.value = (
                                snapshot_inicial.agenda_local if snapshot_inicial else ""
                            )
                            agenda_status = ui.label("").classes("text-sm text-slate-500")
                            ui.button(
                                "Salvar agenda",
                                on_click=lambda: _salvar_documento(
                                    servico.salvar_agenda_local,
                                    agenda_texto.value,
                                    agenda_status,
                                    status,
                                ),
                            ).classes("w-full")

        def atualizar() -> None:
            """Recarrega os dados dinamicos sem reconstruir a pagina inteira."""
            try:
                snapshot = servico.carregar(
                    dia_clima=str(seletor_dia.value or "hoje"),
                    limite_noticias=int(limite_noticias.value or 8),
                )
            except Exception as exc:  # pragma: no cover
                avisar(str(exc))
                status.text = f"Falha ao carregar painel: {exc}"
                return

            _atualizar_kpis(kpi_cards, snapshot)
            _atualizar_clima_resumo(clima_resumo, snapshot.previsao)
            grafico_grupos.options.clear()
            grafico_grupos.options.update(_opcoes_grafico(snapshot.noticias_por_grupo))
            grafico_grupos.update()
            tabela_noticias.rows = _linhas_noticias(snapshot.noticias)
            tabela_noticias.update()
            noticias_total.text = (
                f"{snapshot.indicadores.total_noticias} itens | atualizado {snapshot.atualizado_em}"
            )
            plano_texto.value = snapshot.plano_estudos
            agenda_texto.value = snapshot.agenda_local
            _popular_notas_recentes(notas_recentes, snapshot.notas_recentes)
            status.text = f"Painel atualizado as {snapshot.atualizado_em}."

        noticias_total.text = (
            f"{snapshot_inicial.indicadores.total_noticias if snapshot_inicial else 0} itens"
        )
        ui.button("Atualizar dashboard", on_click=atualizar).classes("w-56")
        ui.timer(90.0, lambda: atualizar() if atualizacao_auto.value else None)


def _cabecalho(snapshot: DashboardSnapshot | None) -> None:
    """Renderiza a faixa superior com contexto operacional do painel."""
    with ui.element("section").classes("hero w-full gap-2"):
        ui.label("Dashboard operacional").classes("hero-kicker")
        ui.label("Assistente pessoal").classes("text-3xl font-semibold")
        ui.label(
            "Visao diaria de noticias, clima e organizacao pessoal com memoria em Obsidian."
        ).classes("text-base text-slate-200")
        atualizado = snapshot.atualizado_em if snapshot else "--:--:--"
        ui.label(f"Ultima leitura consolidada: {atualizado}").classes("text-sm text-slate-300")


def _criar_kpis(snapshot: DashboardSnapshot | None) -> list[dict]:
    """Define o conjunto fixo de cards de indicadores do topo."""
    if snapshot:
        previsao = snapshot.previsao
        return [
            {
                "label": "Noticias no radar",
                "value": str(snapshot.indicadores.total_noticias),
                "detail": "Itens do dia atual carregados no painel",
            },
            {
                "label": "The News em destaque",
                "value": str(snapshot.indicadores.noticias_the_news),
                "detail": "Artigos do grupo prioritario",
            },
            {
                "label": "Santa Maria hoje",
                "value": str(snapshot.indicadores.noticias_santa_maria),
                "detail": "Cobertura local disponivel hoje",
            },
            {
                "label": "Temperatura alvo",
                "value": f"{previsao.maxima or '--'} C",
                "detail": (f"Minima {previsao.minima or '--'} C | Chuva {previsao.chuva or '--'}%"),
            },
        ]
    return [
        {"label": "Noticias no radar", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "The News em destaque", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "Santa Maria hoje", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "Temperatura alvo", "value": "--", "detail": "Sem dados iniciais"},
    ]


def _atualizar_kpis(kpis: list[dict], snapshot: DashboardSnapshot) -> None:
    """Atualiza os cards de topo sem recriar seus elementos."""
    novos = _criar_kpis(snapshot)
    for card, novo in zip(kpis, novos, strict=False):
        valor, detalhe = card["widgets"]
        valor.text = novo["value"]
        detalhe.text = novo["detail"]


def _render_clima_resumo(snapshot: DashboardSnapshot | None) -> dict[str, ui.element]:
    """Constroi o resumo visual de clima em estilo dashboard."""
    with ui.column().classes("gap-3"):
        cidade = ui.label(snapshot.previsao.cidade if snapshot else "Sem dados").classes(
            "text-lg font-semibold"
        )
        data = ui.label(snapshot.previsao.data_alvo.isoformat() if snapshot else "--").classes(
            "text-sm text-slate-500"
        )
        temperatura = ui.label(
            f"{snapshot.previsao.temperatura_atual} C" if snapshot else "--"
        ).classes("text-5xl font-bold")
        with ui.element("div").classes("stat-grid"):
            maxima = _stat_box("Maxima", f"{snapshot.previsao.maxima} C" if snapshot else "--")
            minima = _stat_box("Minima", f"{snapshot.previsao.minima} C" if snapshot else "--")
            chuva = _stat_box("Chuva", f"{snapshot.previsao.chuva}%" if snapshot else "--")
        contexto = ui.label(
            f"Sensacao {snapshot.previsao.sensacao} C | Vento {snapshot.previsao.vento} km/h"
            if snapshot
            else "Sem leitura de clima ainda."
        ).classes("text-sm text-slate-500")
    return {
        "cidade": cidade,
        "data": data,
        "temperatura": temperatura,
        "maxima": maxima,
        "minima": minima,
        "chuva": chuva,
        "contexto": contexto,
    }


def _atualizar_clima_resumo(widgets: dict[str, ui.element], previsao: PrevisaoClima) -> None:
    """Atualiza o bloco principal de clima."""
    widgets["cidade"].text = previsao.cidade
    widgets["data"].text = previsao.data_alvo.isoformat()
    widgets["temperatura"].text = f"{previsao.temperatura_atual} C"
    widgets["maxima"].text = f"{previsao.maxima} C"
    widgets["minima"].text = f"{previsao.minima} C"
    widgets["chuva"].text = f"{previsao.chuva}%"
    widgets["contexto"].text = f"Sensacao {previsao.sensacao} C | Vento {previsao.vento} km/h"


def _stat_box(rotulo: str, valor: str) -> ui.label:
    """Cria uma mini caixa numerica para os blocos de clima."""
    with ui.element("div").classes("stat-box"):
        ui.label(rotulo).classes("text-xs text-slate-500")
        texto = ui.label(valor).classes("text-lg font-semibold")
    return texto


def _opcoes_grafico(contagens: dict[str, int]) -> dict:
    """Monta um grafico de barras compacto com a distribuicao das noticias."""
    grupos = list(GRUPOS_LABEL)
    return {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 45, "right": 20, "top": 30, "bottom": 40},
        "xAxis": {
            "type": "category",
            "axisLabel": {"interval": 0, "fontSize": 11},
            "data": [GRUPOS_LABEL[grupo] for grupo in grupos],
        },
        "yAxis": {"type": "value", "minInterval": 1},
        "series": [
            {
                "type": "bar",
                "barWidth": "48%",
                "data": [
                    {
                        "value": contagens.get(grupo, 0),
                        "itemStyle": {"color": GRUPOS_COR[grupo]},
                    }
                    for grupo in grupos
                ],
            }
        ],
    }


def _linhas_noticias(noticias: list[Noticia]) -> list[dict]:
    """Converte as noticias para um formato mais adequado a tabela analitica."""
    linhas: list[dict] = []
    for indice, noticia in enumerate(noticias, start=1):
        linhas.append(
            {
                "id": indice,
                "prioridade": indice,
                "grupo": GRUPOS_LABEL.get(
                    noticia.grupo,
                    noticia.grupo.replace("_", " ").title(),
                ),
                "fonte": texto_terminal_seguro(noticia.fonte),
                "titulo": texto_terminal_seguro(noticia.titulo),
                "publicado": texto_terminal_seguro(noticia.publicado),
                "link": noticia.link,
                "cor": GRUPOS_COR.get(noticia.grupo, "#475569"),
            }
        )
    return linhas


def _popular_notas_recentes(container: ui.column, notas: list[str]) -> None:
    """Atualiza a lista curta de artefatos recentes do vault."""
    container.clear()
    if not notas:
        with container:
            ui.label("Nenhuma nota recente encontrada.").classes("text-sm text-slate-500")
        return
    with container:
        for nota in notas[:6]:
            with ui.element("div").classes("stat-box"):
                ui.label("Vault").classes("text-[11px] uppercase text-slate-400")
                ui.label(nota).classes("text-sm font-medium text-slate-700")


def _salvar_nota(
    servico: DashboardService,
    titulo: str,
    conteudo: str,
    caminho_label,
    status_label,
    notas_recentes,
) -> None:
    """Valida e salva uma nota curta a partir do dashboard."""
    if not titulo.strip() or not conteudo.strip():
        status_label.text = "Preencha titulo e conteudo antes de salvar."
        return
    caminho = servico.salvar_nota_rapida(titulo.strip(), conteudo.strip())
    caminho_label.text = f"Nota salva em {caminho}"
    notas = [
        servico.memoria.caminho_relativo(caminho_item)
        for caminho_item in servico.memoria.listar_recentes()
    ]
    _popular_notas_recentes(notas_recentes, notas)
    status_label.text = "Nota criada no vault."


def _salvar_documento(funcao_salvar, conteudo: str, caminho_label, status_label) -> None:
    """Persiste um documento fixo da GUI e atualiza os avisos ao usuario."""
    caminho = funcao_salvar(conteudo.strip())
    caminho_label.text = f"Arquivo salvo em {caminho}"
    status_label.text = "Documento salvo no vault."
