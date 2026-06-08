"""Dashboard grafico local baseado em NiceGUI."""

from __future__ import annotations

import socket

from nicegui import ui

from assistente_pessoal.clima import formatar_previsao
from assistente_pessoal.config import AppConfig
from assistente_pessoal.logs import avisar
from assistente_pessoal.noticias import texto_terminal_seguro
from assistente_pessoal.painel import DashboardService, DashboardSnapshot


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
    """Constroi o layout principal do dashboard sem iniciar o servidor."""
    ui.add_head_html(
        """
        <style>
        body { background: #f5f7fb; }
        .painel {
          background: white;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
        }
        .titulo-painel { font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }
        </style>
        """
    )
    with ui.column().classes("w-full max-w-7xl mx-auto gap-4 p-4"):
        ui.label("Assistente pessoal").classes("text-3xl font-semibold")
        ui.label(
            "Clima, noticias e espacos do seu vault para estudo, memoria e agenda local."
        ).classes("text-base text-slate-600")

        with ui.row().classes("w-full items-end gap-3"):
            seletor_dia = ui.select(
                [
                    "hoje",
                    "amanha",
                    "segunda",
                    "terca",
                    "quarta",
                    "quinta",
                    "sexta",
                    "sabado",
                    "domingo",
                ],
                value="hoje",
                label="Dia do clima",
            ).classes("w-48")
            limite_noticias = ui.number(
                label="Limite de noticias", value=8, min=1, max=20, step=1
            ).classes("w-40")
            status = ui.label("").classes("text-sm text-slate-500")

        clima_card = _card("Clima")
        noticias_card = _card("Noticias")
        notas_card = _card("Notas rapidas")
        plano_card = _card("Plano de estudos")
        agenda_card = _card("Agenda local")

        with ui.grid(columns=2).classes("w-full gap-4"):
            with clima_card:
                clima_texto = ui.markdown(
                    formatar_previsao(snapshot_inicial.previsao)
                    if snapshot_inicial
                    else "Clique em atualizar dashboard para carregar o clima."
                )
            with noticias_card:
                noticias_lista = ui.column().classes("w-full gap-2")
                if snapshot_inicial and snapshot_inicial.noticias:
                    with noticias_lista:
                        for item in snapshot_inicial.noticias:
                            with ui.link(target=item.link).classes("block text-sm no-underline"):
                                ui.label(texto_terminal_seguro(item.titulo)).classes("font-medium")
                                ui.label(
                                    f"{texto_terminal_seguro(item.fonte)} | "
                                    f"{item.grupo.replace('_', ' ')}"
                                ).classes("text-xs text-slate-500")
                else:
                    with noticias_lista:
                        ui.label("Clique em atualizar dashboard para carregar noticias.")
        with ui.grid(columns=3).classes("w-full gap-4"):
            with notas_card:
                titulo_nota = ui.input("Titulo").classes("w-full")
                conteudo_nota = ui.textarea("Conteudo").classes("w-full").props("rows=8")
                caminho_nota = ui.label("").classes("text-sm text-slate-500")
                ui.button(
                    "Salvar nota",
                    on_click=lambda: _salvar_nota(
                        servico,
                        titulo_nota.value,
                        conteudo_nota.value,
                        caminho_nota,
                        status,
                    ),
                ).classes("w-full")
            with plano_card:
                plano_texto = ui.textarea("Plano de estudos").classes("w-full").props("rows=12")
                plano_texto.value = snapshot_inicial.plano_estudos if snapshot_inicial else ""
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
            with agenda_card:
                agenda_texto = ui.textarea("Agenda local").classes("w-full").props("rows=12")
                agenda_texto.value = snapshot_inicial.agenda_local if snapshot_inicial else ""
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
            """Recarrega os dados dinâmicos sem reconstruir a pagina inteira."""
            try:
                snapshot = servico.carregar(
                    dia_clima=str(seletor_dia.value or "hoje"),
                    limite_noticias=int(limite_noticias.value or 8),
                )
            except Exception as exc:  # pragma: no cover - GUI so aparece em execucao real
                avisar(str(exc))
                status.text = f"Falha ao carregar painel: {exc}"
                return
            clima_texto.content = formatar_previsao(snapshot.previsao)
            noticias_lista.clear()
            if snapshot.noticias:
                with noticias_lista:
                    for item in snapshot.noticias:
                        with ui.link(target=item.link).classes("block text-sm no-underline"):
                            ui.label(texto_terminal_seguro(item.titulo)).classes("font-medium")
                            ui.label(
                                f"{texto_terminal_seguro(item.fonte)} | "
                                f"{item.grupo.replace('_', ' ')}"
                            ).classes("text-xs text-slate-500")
            else:
                with noticias_lista:
                    ui.label("Nenhuma noticia encontrada para o dia atual.")
            plano_texto.value = snapshot.plano_estudos
            agenda_texto.value = snapshot.agenda_local
            status.text = "Painel atualizado."

        ui.button("Atualizar dashboard", on_click=atualizar).classes("w-56")


def _card(titulo: str) -> ui.element:
    """Cria um container consistente para as secoes do dashboard."""
    with ui.card().classes("painel w-full gap-3") as card:
        ui.label(titulo).classes("titulo-painel")
    return card


def _salvar_nota(
    servico: DashboardService,
    titulo: str,
    conteudo: str,
    caminho_label,
    status_label,
) -> None:
    """Valida e salva uma nota curta a partir do dashboard."""
    if not titulo.strip() or not conteudo.strip():
        status_label.text = "Preencha titulo e conteudo antes de salvar."
        return
    caminho = servico.salvar_nota_rapida(titulo.strip(), conteudo.strip())
    caminho_label.text = f"Nota salva em {caminho}"
    status_label.text = "Nota criada no vault."


def _salvar_documento(funcao_salvar, conteudo: str, caminho_label, status_label) -> None:
    """Persiste um documento fixo da GUI e atualiza os avisos ao usuario."""
    caminho = funcao_salvar(conteudo.strip())
    caminho_label.text = f"Arquivo salvo em {caminho}"
    status_label.text = "Documento salvo no vault."
