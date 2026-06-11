import re
from pathlib import Path

file_path = Path(r"d:\milla\OneDrive\Documentos\Assistente de IA pessoal\src\assistente_pessoal\gui.py")
content = file_path.read_text(encoding="utf-8")

# 1. Update CSS
css_replacements = [
    (r"font-size: 1.65rem;", r"font-size: 1.25rem;"),
    (r"font-size: 0.92rem;", r"font-size: 0.8rem;"),
    (r"font-size: 2rem;", r"font-size: 1.5rem;"),
    (r"--appa-card-pad: 16px;", r"--appa-card-pad: 10px;"),
    (r"--appa-row-gap: 14px;", r"--appa-row-gap: 10px;"),
    (r"min-height: 104px;", r"min-height: 80px;"),
    (r"font-size: 3.4rem;", r"font-size: 2.4rem;"),
    (r"padding: 14px 18px 22px;", r"padding: 8px 12px 14px;"),
    (r"body\.appa-dashboard \{", r"body.appa-dashboard {\n      font-size: 13px;"),
]
for old, new in css_replacements:
    content = content.replace(old, new)

# 2. Add EChart and AgGrid helper functions before construir_dashboard
helpers = """
def _criar_grafico_clima(resumo: list[ResumoClimaDia]):
    dias = [_rotulo_dia_curto(d) for d in resumo]
    maximas = [d.maxima for d in resumo]
    minimas = [d.minima for d in resumo]
    return ui.echart({
        'tooltip': {'trigger': 'axis'},
        'legend': {'data': ['Max', 'Min'], 'textStyle': {'color': '#9fb2c7'}},
        'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': True},
        'xAxis': {'type': 'category', 'data': dias, 'axisLabel': {'color': '#9fb2c7'}},
        'yAxis': {'type': 'value', 'axisLabel': {'color': '#9fb2c7'}, 'splitLine': {'lineStyle': {'color': '#1e293b'}}},
        'series': [
            {'name': 'Max', 'type': 'line', 'data': maximas, 'itemStyle': {'color': '#fbbf24'}, 'smooth': True},
            {'name': 'Min', 'type': 'line', 'data': minimas, 'itemStyle': {'color': '#60a5fa'}, 'smooth': True},
        ]
    }).classes('w-full h-64')

def _atualizar_grafico_clima(chart, resumo: list[ResumoClimaDia]):
    dias = [_rotulo_dia_curto(d) for d in resumo]
    maximas = [d.maxima for d in resumo]
    minimas = [d.minima for d in resumo]
    chart.options['xAxis']['data'] = dias
    chart.options['series'][0]['data'] = maximas
    chart.options['series'][1]['data'] = minimas
    chart.update()

def _criar_grafico_noticias(grupos: dict[str, int]):
    data = [{'value': v, 'name': GRUPOS_LABEL.get(k, k.title())} for k, v in grupos.items()]
    return ui.echart({
        'tooltip': {'trigger': 'item'},
        'legend': {'top': '5%', 'left': 'center', 'textStyle': {'color': '#9fb2c7'}},
        'series': [
            {
                'name': 'Notícias',
                'type': 'pie',
                'radius': ['40%', '70%'],
                'avoidLabelOverlap': False,
                'itemStyle': {'borderRadius': 5, 'borderColor': '#060914', 'borderWidth': 2},
                'label': {'show': False, 'position': 'center'},
                'emphasis': {'label': {'show': True, 'fontSize': 16, 'fontWeight': 'bold'}},
                'labelLine': {'show': False},
                'data': data
            }
        ]
    }).classes('w-full h-64')

def _atualizar_grafico_noticias(chart, grupos: dict[str, int]):
    data = [{'value': v, 'name': GRUPOS_LABEL.get(k, k.title())} for k, v in grupos.items()]
    chart.options['series'][0]['data'] = data
    chart.update()

def _linhas_noticias_aggrid(noticias: list[Noticia], timezone: str) -> list[dict]:
    return [
        {
            "grupo": GRUPOS_LABEL.get(n.grupo, n.grupo.title()),
            "fonte": texto_terminal_seguro(n.fonte),
            "titulo": texto_terminal_seguro(n.titulo),
            "publicado": texto_terminal_seguro(rotulo_tempo_publicacao(n, timezone=timezone)),
            "link": _link_seguro(n.link),
        }
        for n in noticias
    ]

"""

# Insert helpers just before construir_dashboard
content = content.replace("def construir_dashboard(", helpers + "def construir_dashboard(")


# 3. Replace construir_dashboard body
old_construir = re.search(r"def construir_dashboard\(.*?(?=def _cabecalho\()", content, re.DOTALL).group(0)

new_construir = """def construir_dashboard(
    servico: DashboardService,
    snapshot_inicial: DashboardSnapshot | None = None,
) -> None:
    \"\"\"Constroi um dashboard denso, visual e voltado a acompanhamento diario.\"\"\"
    _registrar_assets_dashboard()
    ui.run_javascript("document.documentElement.dataset.density = 'compact';")
    with ui.column().classes("dashboard-shell gap-3 w-full max-w-[1600px]"):
        _cabecalho(snapshot_inicial)
        with ui.row().classes("commandbar items-end gap-3 w-full"):
            limite_noticias = ui.number(
                label="Noticias",
                value=LIMITE_PADRAO_NOTICIAS,
                min=8,
                max=LIMITE_PADRAO_NOTICIAS,
                step=1,
                format="%.0f",
            ).classes("w-32")
            atualizacao_auto = ui.switch("Atualizacao automatica", value=True).classes(
                "control-switch"
            )
            ui.html(
                '''
                <div class="theme-toggle" aria-label="Tema do painel">
                  <button type="button" data-theme-choice="dark">Dark</button>
                  <button type="button" data-theme-choice="light">Light</button>
                </div>
                '''
            )
            ui.html(
                '''
                <div class="commandbar-note">
                  <span class="status-dot"></span>
                  <span>Atualizacao local ativa</span>
                </div>
                '''
            )
            ui.button(
                "Atualizar",
                icon="refresh",
                on_click=lambda: atualizar(),
            ).classes("refresh-button")
            status = ui.label("Painel pronto.").classes("dashboard-status ml-auto")

        with ui.tabs().classes('w-full') as tabs:
            tab_visao_geral = ui.tab('Visão Geral', icon='dashboard')
            tab_noticias = ui.tab('Explorador de Notícias', icon='analytics')
            tab_agenda = ui.tab('Agenda e Eventos', icon='calendar_month')
            tab_interesses = ui.tab('Configurações', icon='settings')
            
        with ui.tab_panels(tabs, value=tab_visao_geral).classes('w-full bg-transparent p-0'):
            with ui.tab_panel(tab_visao_geral).classes('p-0 gap-3 flex flex-col'):
                kpi_cards = _criar_kpis(snapshot_inicial)
                with ui.grid(columns=6).classes("kpi-grid w-full gap-3"):
                    for card in kpi_cards:
                        with ui.element("div").classes("kpi"):
                            ui.label(card["label"]).classes("kpi-label")
                            valor = ui.label(card["value"]).classes("kpi-value")
                            detalhe = ui.label(card["detail"]).classes("text-xs text-slate-500")
                            card["widgets"] = (valor, detalhe)

                with ui.grid(columns=2).classes('w-full gap-3'):
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Previsão da Semana').classes('section-title mb-2')
                        grafico_clima = _criar_grafico_clima(snapshot_inicial.resumo_semana if snapshot_inicial else [])
                    
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Distribuição de Notícias').classes('section-title mb-2')
                        grafico_noticias = _criar_grafico_noticias(snapshot_inicial.noticias_por_grupo if snapshot_inicial else {})

                with ui.grid(columns=2).classes('w-full gap-3'):
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Santa Maria em Foco').classes('section-title mb-2')
                        santa_maria_cards = ui.column().classes("w-full gap-2")
                        _popular_santa_maria_em_foco(
                            santa_maria_cards,
                            snapshot_inicial.santa_maria_em_foco if snapshot_inicial else [],
                            servico.config.localizacao.timezone,
                            servico,
                            status,
                        )
                    
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Clima Atual').classes('section-title mb-2')
                        clima_resumo = _render_clima_resumo(snapshot_inicial)

            with ui.tab_panel(tab_noticias).classes('p-0 gap-3 flex flex-col'):
                with ui.element('div').classes('expansion-shell p-3 w-full h-[600px] flex flex-col'):
                    with ui.row().classes("w-full items-center justify-between mb-2"):
                        ui.label('Explorador de Notícias').classes('section-title')
                        noticias_total = ui.label("").classes("news-live-count text-sm")
                    
                    tabela_noticias = ui.aggrid({
                        'columnDefs': [
                            {'headerName': 'Grupo', 'field': 'grupo', 'sortable': True, 'filter': True, 'width': 130},
                            {'headerName': 'Fonte', 'field': 'fonte', 'sortable': True, 'filter': True, 'width': 130},
                            {'headerName': 'Título', 'field': 'titulo', 'sortable': True, 'filter': True, 'flex': 1},
                            {'headerName': 'Publicado', 'field': 'publicado', 'sortable': True, 'filter': True, 'width': 150},
                            {'headerName': 'Link', 'field': 'link', 'cellRenderer': '''(params) => `<a href="${params.value}" target="_blank" style="color: #22d3ee; text-decoration: underline;">Abrir</a>`''', 'width': 90}
                        ],
                        'rowData': _linhas_noticias_aggrid(_noticias_sem_santa_maria(snapshot_inicial.noticias) if snapshot_inicial else [], servico.config.localizacao.timezone),
                        'rowSelection': 'single',
                        'defaultColDef': {'resizable': True},
                    }).classes('w-full flex-grow ag-theme-balham-dark')

            with ui.tab_panel(tab_agenda).classes('p-0 gap-3 flex flex-col'):
                with ui.element("div").classes("agenda-layout w-full"):
                    with ui.element("div").classes("agenda-calendar-pane"):
                        agenda_mes_titulo = ui.label("").classes("section-title")
                        agenda_erro = ui.html("").classes("w-full")
                        calendario_google = ui.column().classes("w-full gap-2")
                    google_lista = ui.column().classes("agenda-side-pane")
                _popular_agenda_google(
                    calendario_google,
                    google_lista,
                    agenda_erro,
                    agenda_mes_titulo,
                    snapshot_inicial.agenda_google_resultado if snapshot_inicial else None,
                    servico.config.localizacao.timezone,
                )
                with ui.element("div").classes("agenda-form-shell mt-3"):
                    ui.label("Adicionar evento").classes("section-title")
                    evento_titulo = ui.input("Titulo").classes("w-full")
                    with ui.element("div").classes("agenda-form-grid"):
                        evento_data = ui.input("Data (AAAA-MM-DD)").classes("w-full")
                        evento_hora = ui.input("Hora (HH:MM)").classes("w-full")
                        duracao_minutos = ui.number(
                            label="Duracao (minutos)",
                            value=60,
                            min=15,
                            max=720,
                            step=15,
                            format="%.0f",
                        ).classes("w-full")
                        evento_local = ui.input("Local").classes("w-full")
                    evento_descricao = ui.textarea("Descricao").classes("w-full")
                    evento_descricao.props("rows=3")
                    agenda_status = ui.label("").classes("text-sm text-slate-500")
                    ui.button(
                        "Criar evento no Google Agenda",
                        on_click=lambda: _criar_evento_google(
                            servico,
                            evento_titulo.value,
                            evento_data.value,
                            evento_hora.value,
                            duracao_minutos.value,
                            evento_local.value,
                            evento_descricao.value,
                            agenda_status,
                            status,
                            calendario_google,
                            google_lista,
                            agenda_erro,
                            agenda_mes_titulo,
                        ),
                    ).classes("w-full")

            with ui.tab_panel(tab_interesses).classes('p-0 gap-3 flex flex-col'):
                with ui.element('div').classes('expansion-shell p-3'):
                    ui.label('Interesses de Pesquisa').classes('section-title mb-2')
                    interesses_container = ui.element("div").classes("interest-list")
                    _popular_interesses(
                        interesses_container,
                        servico.config.fontes.noticias.interesses_busca,
                    )
                    interesse_texto = ui.textarea("Adicionar interesses").classes("w-full mt-3")
                    interesse_texto.props("rows=3")
                    interesses_status = ui.label("").classes("text-sm text-slate-500")
                    ui.button(
                        "Salvar interesses",
                        icon="save",
                        on_click=lambda: _adicionar_interesses_gui(
                            servico,
                            interesse_texto,
                            interesses_container,
                            interesses_status,
                            status,
                        )
                        and atualizar(),
                    ).classes("w-full mt-2")

        def atualizar() -> None:
            try:
                snapshot = servico.carregar(
                    limite_noticias=int(limite_noticias.value or LIMITE_PADRAO_NOTICIAS),
                )
            except Exception as exc:
                status.text = f"Falha ao carregar painel: {exc}"
                return

            _atualizar_kpis(kpi_cards, snapshot)
            _atualizar_clima_resumo(clima_resumo, snapshot)
            _atualizar_grafico_clima(grafico_clima, snapshot.resumo_semana)
            _atualizar_grafico_noticias(grafico_noticias, snapshot.noticias_por_grupo)
            
            _popular_santa_maria_em_foco(
                santa_maria_cards,
                snapshot.santa_maria_em_foco,
                servico.config.localizacao.timezone,
                servico,
                status,
            )
            
            novas_noticias = _noticias_sem_santa_maria(snapshot.noticias)
            tabela_noticias.options['rowData'] = _linhas_noticias_aggrid(novas_noticias, servico.config.localizacao.timezone)
            tabela_noticias.update()
            
            noticias_total.text = (
                f"{_resumo_feed_noticias(novas_noticias)} "
                f"| atualizado "
                f"{snapshot.atualizado_em}"
            )
            _popular_agenda_google(
                calendario_google,
                google_lista,
                agenda_erro,
                agenda_mes_titulo,
                snapshot.agenda_google_resultado,
                servico.config.localizacao.timezone,
            )
            ui.run_javascript(
                "const alvo = document.querySelector('[data-appa-updated]');"
                f"if (alvo) alvo.textContent = '{snapshot.atualizado_em}';"
            )
            status.text = f"Painel atualizado as {snapshot.atualizado_em}."

        noticias_total.text = _resumo_feed_noticias(
            _noticias_sem_santa_maria(snapshot_inicial.noticias if snapshot_inicial else [])
        )
        cliente_dashboard = ui.context.client

        def atualizar_automaticamente() -> None:
            if not atualizacao_auto.value or not cliente_dashboard.has_socket_connection:
                return
            with cliente_dashboard:
                atualizar()

        timer_atualizacao = app.timer(
            float(servico.config.dashboard.intervalo_atualizacao_segundos),
            atualizar_automaticamente,
            immediate=False,
        )
        cliente_dashboard.on_delete(
            lambda *_args: timer_atualizacao.cancel(with_current_invocation=True)
        )

"""

content = content.replace(old_construir, new_construir)

# 4. Modify _render_clima_resumo to remove weather-week
old_clima = re.search(r"def _render_clima_resumo.*?return \{[^\}]+\}", content, re.DOTALL).group(0)

new_clima = """def _render_clima_resumo(snapshot: DashboardSnapshot | None) -> dict[str, ui.element]:
    \"\"\"Constroi o resumo visual de clima em estilo dashboard.\"\"\"
    with ui.element("div").classes("weather-now w-full h-full flex flex-col justify-center"):
        cidade = ui.label(snapshot.previsao.cidade if snapshot else "Sem dados").classes(
            "text-lg font-semibold"
        )
        data = ui.label(snapshot.previsao.data_alvo.isoformat() if snapshot else "--").classes(
            "text-sm text-slate-500"
        )
        referencia = ui.label(
            _rotulo_referencia_clima(snapshot.previsao) if snapshot else "Sem referencia"
        ).classes("text-xs uppercase text-slate-400")
        temperatura = ui.label(
            _formatar_grau(snapshot.previsao.temperatura_referencia) if snapshot else "--"
        ).classes("weather-temp")
        with ui.element("div").classes("stat-grid mt-4"):
            maxima = _stat_box(
                "Maxima",
                _formatar_grau(snapshot.previsao.maxima) if snapshot else "--",
            )
            minima = _stat_box(
                "Minima",
                _formatar_grau(snapshot.previsao.minima) if snapshot else "--",
            )
            chuva = _stat_box(
                "Chuva",
                _formatar_chuva(snapshot.previsao.chuva) if snapshot else "--",
            )
        contexto = ui.label(
            _texto_contexto_clima(snapshot.previsao)
            if snapshot
            else "Sem leitura de clima ainda."
        ).classes("text-sm text-slate-500 mt-3")
        
    return {
        "cidade": cidade,
        "data": data,
        "referencia": referencia,
        "temperatura": temperatura,
        "maxima": maxima,
        "minima": minima,
        "chuva": chuva,
        "contexto": contexto,
    }"""

content = content.replace(old_clima, new_clima)

# 5. Modify _atualizar_clima_resumo to match removed semana
old_atualizar_clima = re.search(r"def _atualizar_clima_resumo.*?_popular_semana_clima\(widgets\[\"semana\"\], snapshot\.resumo_semana\)", content, re.DOTALL).group(0)
new_atualizar_clima = """def _atualizar_clima_resumo(widgets: dict[str, ui.element], snapshot: DashboardSnapshot) -> None:
    \"\"\"Atualiza o bloco principal de clima.\"\"\"
    previsao = snapshot.previsao
    widgets["cidade"].text = previsao.cidade
    widgets["data"].text = previsao.data_alvo.isoformat()
    widgets["referencia"].text = _rotulo_referencia_clima(previsao)
    widgets["temperatura"].text = _formatar_grau(previsao.temperatura_referencia)
    widgets["maxima"].text = _formatar_grau(previsao.maxima)
    widgets["minima"].text = _formatar_grau(previsao.minima)
    widgets["chuva"].text = _formatar_chuva(previsao.chuva)
    widgets["contexto"].text = _texto_contexto_clima(previsao)"""

content = content.replace(old_atualizar_clima, new_atualizar_clima)

file_path.write_text(content, encoding="utf-8")
print("gui.py updated successfully.")
