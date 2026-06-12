import re
from pathlib import Path

gui_path = Path("d:/milla/OneDrive/Documentos/Assistente de IA pessoal/src/assistente_pessoal/gui.py")
content = gui_path.read_text(encoding="utf-8")

# 1. Update the commandbar
old_commandbar = r"""        with ui\.row\(\)\.classes\("commandbar items-end gap-3 w-full"\):
            limite_noticias = ui\.number\(
                label="Noticias",
                value=LIMITE_PADRAO_NOTICIAS,
                min=8,
                max=LIMITE_PADRAO_NOTICIAS,
                step=1,
                format="%\.0f",
            \)\.classes\("w-32"\)
            atualizacao_auto = ui\.switch\("Atualizacao automatica", value=True\)\.classes\(
                "control-switch"
            \)
            ui\.html\(
                '''
                <div class="theme-toggle" aria-label="Tema do painel">
                  <button type="button" data-theme-choice="dark">Dark</button>
                  <button type="button" data-theme-choice="light">Light</button>
                </div>
                '''
            \)
            ui\.html\(
                '''
                <div class="commandbar-note">
                  <span class="status-dot"></span>
                  <span>Atualizacao local ativa</span>
                </div>
                '''
            \)
            ui\.button\(
                "Atualizar",
                icon="refresh",
                on_click=lambda: atualizar\(\),
            \)\.classes\("refresh-button"\)
            status = ui\.label\("Painel pronto\."\)\.classes\("dashboard-status ml-auto"\)"""

new_commandbar = """        with ui.row().classes("commandbar items-center gap-3 w-full"):
            ui.html(
                '''
                <div class="commandbar-note">
                  <span class="status-dot"></span>
                  <span>Atualização local ativa</span>
                </div>
                '''
            )
            ui.button(
                "Atualizar Painel",
                icon="refresh",
                on_click=lambda: atualizar(),
            ).classes("refresh-button")
            status = ui.label("Painel pronto.").classes("dashboard-status ml-auto")"""

content = re.sub(old_commandbar, new_commandbar, content, flags=re.DOTALL)

# 2. Update tab_interesses
old_tab_interesses = r"""            with ui\.tab_panel\(tab_interesses\)\.classes\('p-0 gap-3 flex flex-col'\):
                with ui\.element\('div'\)\.classes\('expansion-shell p-3'\):
                    ui\.label\('Interesses de Pesquisa'\)\.classes\('section-title mb-2'\)
                    interesses_container = ui\.element\("div"\)\.classes\("interest-list"\)
                    _popular_interesses\(
                        interesses_container,
                        servico\.config\.fontes\.noticias\.interesses_busca,
                    \)
                    interesse_texto = ui\.textarea\("Adicionar interesses"\)\.classes\("w-full mt-3"\)
                    interesse_texto\.props\("rows=3"\)
                    interesses_status = ui\.label\(""\)\.classes\("text-sm text-slate-500"\)
                    ui\.button\(
                        "Salvar interesses",
                        icon="save",
                        on_click=lambda: _adicionar_interesses_gui\(
                            servico,
                            interesse_texto,
                            interesses_container,
                            interesses_status,
                            status,
                        \)
                        and atualizar\(\),
                    \)\.classes\("w-full mt-2"\)"""

new_tab_interesses = """            with ui.tab_panel(tab_interesses).classes('p-0 gap-3 flex flex-col'):
                with ui.grid(columns=2).classes('w-full gap-3'):
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Aparência e Comportamento').classes('section-title mb-2')
                        limite_noticias = ui.number(
                            label="Limite de Notícias no Dashboard",
                            value=LIMITE_PADRAO_NOTICIAS,
                            min=8,
                            max=LIMITE_PADRAO_NOTICIAS,
                            step=1,
                            format="%.0f",
                        ).classes("w-full mb-3")
                        atualizacao_auto = ui.switch("Atualização automática", value=True).classes(
                            "control-switch mb-3"
                        )
                        ui.label('Tema do Painel').classes('text-xs font-semibold text-slate-500 mb-1')
                        ui.html(
                            '''
                            <div class="theme-toggle" aria-label="Tema do painel">
                              <button type="button" data-theme-choice="dark">Dark</button>
                              <button type="button" data-theme-choice="light">Light</button>
                            </div>
                            '''
                        )
                        
                    with ui.element('div').classes('expansion-shell p-3'):
                        ui.label('Interesses de Pesquisa').classes('section-title mb-2')
                        interesses_container = ui.element("div").classes("interest-list")
                        _popular_interesses(
                            interesses_container,
                            servico.config.fontes.noticias.interesses_busca,
                        )
                        interesse_texto = ui.textarea("Adicionar interesses (vírgula)").classes("w-full mt-3")
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
                        ).classes("w-full mt-2")"""

content = re.sub(old_tab_interesses, new_tab_interesses, content, flags=re.DOTALL)

gui_path.write_text(content, encoding="utf-8")
print("gui.py updated")
