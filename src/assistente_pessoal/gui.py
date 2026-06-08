"""Dashboard grafico local baseado em NiceGUI."""

from __future__ import annotations

import calendar
import socket
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from nicegui import app, ui

from assistente_pessoal.agenda_google import (
    EventoGoogleAgenda,
    NovoEventoGoogleAgenda,
    ResultadoGoogleAgenda,
    data_evento_google,
    formatar_data_hora_google,
)
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
from assistente_pessoal.logs import avisar
from assistente_pessoal.noticias import (
    LIMITE_PADRAO_NOTICIAS,
    Noticia,
    rotulo_tempo_publicacao,
    texto_terminal_seguro,
)
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

LOGO_APPA_FILE = Path(__file__).resolve().parents[2] / "assets" / "appa-logo-minimal.png"
ASSETS_ROUTE = "/appa-assets"
_ASSETS_ESTATICOS_REGISTRADOS = False


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
    titulo: str = "APPA",
) -> None:
    """Inicializa e executa a GUI local no navegador."""
    _registrar_arquivos_estaticos()
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


def _registrar_assets_dashboard() -> None:
    """Registra HTML, CSS e JS especificos do painel sem misturar com regras de negocio."""
    _registrar_arquivos_estaticos()
    ui.add_head_html(f"<style>{_dashboard_css()}</style>")
    ui.add_body_html(
        "<script>"
        + _dashboard_js()
        + "</script>"
        + """
          <script>
            if (window.APPA_DASHBOARD) {
              window.APPA_DASHBOARD.boot();
            }
          </script>
          """
    )


def _registrar_arquivos_estaticos() -> None:
    """Expoe assets locais por rota controlada do NiceGUI."""
    global _ASSETS_ESTATICOS_REGISTRADOS
    if _ASSETS_ESTATICOS_REGISTRADOS or not LOGO_APPA_FILE.exists():
        return
    app.add_static_files(ASSETS_ROUTE, str(LOGO_APPA_FILE.parent))
    _ASSETS_ESTATICOS_REGISTRADOS = True


def _logo_appa_src() -> str:
    """Retorna a URL servida pelo dashboard para o logo minimalista."""
    if not LOGO_APPA_FILE.exists():
        return ""
    return f"{ASSETS_ROUTE}/{LOGO_APPA_FILE.name}"


def _dashboard_css() -> str:
    """Mantem o tema visual centralizado para facilitar futuras iteracoes de produto."""
    return """
    :root {
      --appa-bg: #f3f5f7;
      --appa-panel: #ffffff;
      --appa-panel-soft: #f8fafc;
      --appa-ink: #17202a;
      --appa-muted: #65758b;
      --appa-line: #d9e2ec;
      --appa-accent: #0f766e;
      --appa-blue: #2563eb;
      --appa-amber: #b45309;
      --appa-rose: #be123c;
      --appa-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }

    html[data-density="compact"] {
      --appa-card-pad: 12px;
      --appa-row-gap: 10px;
    }

    html[data-density="comfortable"] {
      --appa-card-pad: 16px;
      --appa-row-gap: 14px;
    }

    body.appa-dashboard {
      background:
        linear-gradient(180deg, rgba(15, 118, 110, 0.05), rgba(243, 245, 247, 0) 260px),
        var(--appa-bg);
      color: var(--appa-ink);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .dashboard-shell {
      max-width: 1560px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }

    .appa-top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: stretch;
      background: var(--appa-panel);
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      box-shadow: var(--appa-shadow);
      overflow: hidden;
    }

    .appa-brand {
      display: flex;
      gap: 16px;
      align-items: center;
      padding: 18px 20px;
      border-left: 5px solid var(--appa-accent);
    }

    .appa-logo {
      width: 58px;
      height: 58px;
      border-radius: 8px;
      object-fit: cover;
      border: 1px solid #c8d4e0;
      background: #eef6f5;
    }

    .appa-kicker {
      margin: 0 0 3px;
      color: var(--appa-muted);
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
    }

    .appa-title {
      margin: 0;
      font-size: 1.65rem;
      line-height: 1.1;
      font-weight: 800;
      color: var(--appa-ink);
    }

    .appa-subtitle {
      margin: 5px 0 0;
      color: var(--appa-muted);
      font-size: 0.92rem;
    }

    .appa-summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      min-width: 380px;
      background: var(--appa-line);
      border-left: 1px solid var(--appa-line);
    }

    .summary-cell {
      background: #fbfdff;
      padding: 15px 18px;
    }

    .summary-cell span {
      display: block;
      color: var(--appa-muted);
      font-size: 0.73rem;
      font-weight: 700;
      text-transform: uppercase;
    }

    .summary-cell strong {
      display: block;
      margin-top: 4px;
      font-size: 1.08rem;
      color: var(--appa-ink);
    }

    .commandbar {
      position: sticky;
      top: 0;
      z-index: 8;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(10px);
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      padding: 12px 14px;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
    }

    .commandbar-note,
    .dashboard-status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--appa-muted);
      font-size: 0.82rem;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #22c55e;
      box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.14);
    }

    .density-toggle {
      display: inline-flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      background: var(--appa-panel-soft);
    }

    .density-toggle button {
      border: 0;
      border-radius: 6px;
      padding: 7px 10px;
      color: var(--appa-muted);
      background: transparent;
      font-weight: 700;
      font-size: 0.78rem;
      cursor: pointer;
    }

    .density-toggle button.is-active {
      color: var(--appa-ink);
      background: var(--appa-panel);
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
    }

    .kpi-grid {
      grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
    }

    .kpi {
      position: relative;
      background: var(--appa-panel);
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      padding: var(--appa-card-pad, 16px);
      min-height: 104px;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.045);
      overflow: hidden;
    }

    .kpi::before {
      content: "";
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 4px;
      background: var(--appa-blue);
    }

    .kpi:nth-child(2)::before { background: var(--appa-accent); }
    .kpi:nth-child(3)::before { background: var(--appa-amber); }
    .kpi:nth-child(4)::before { background: var(--appa-rose); }
    .kpi:nth-child(5)::before { background: #475569; }
    .kpi:nth-child(6)::before { background: #047857; }

    .kpi-label {
      color: var(--appa-muted);
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
    }

    .kpi-value {
      margin-top: 9px;
      color: var(--appa-ink);
      font-size: 2rem;
      font-weight: 800;
      line-height: 1;
    }

    .expansion-shell {
      background: var(--appa-panel);
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.045);
    }

    .expansion-shell .q-expansion-item__container > .q-item {
      min-height: 58px;
      padding: 13px 16px;
      background: #fbfdff;
      border-bottom: 1px solid var(--appa-line);
    }

    .expansion-shell .q-item__label {
      color: var(--appa-ink);
      font-weight: 800;
    }

    .expansion-shell .q-item__label--caption {
      color: var(--appa-muted);
      font-weight: 500;
    }

    .expansion-shell .q-expansion-item__content > div {
      padding: 16px;
      background: var(--appa-panel);
    }

    .section-title {
      color: var(--appa-ink);
      font-size: 0.98rem;
      font-weight: 800;
    }

    .section-subtitle {
      color: var(--appa-muted);
      font-size: 0.84rem;
    }

    .stat-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .stat-box {
      border: 1px solid #e1e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--appa-panel-soft);
    }

    .weather-panel {
      display: grid;
      grid-template-columns: minmax(260px, 0.9fr) minmax(0, 1.1fr);
      gap: 16px;
      align-items: stretch;
    }

    .weather-now {
      border: 1px solid #d5e4e2;
      border-radius: 8px;
      padding: 16px;
      background: linear-gradient(180deg, #f5fbfa, #ffffff);
    }

    .weather-temp {
      color: var(--appa-ink);
      font-size: 3.4rem;
      font-weight: 850;
      line-height: 1;
    }

    .weather-week {
      display: grid;
      grid-template-columns: repeat(7, minmax(72px, 1fr));
      gap: 8px;
      height: 100%;
    }

    .weather-day {
      min-height: 150px;
      border: 1px solid #e1e8f0;
      border-radius: 8px;
      padding: 10px;
      background: #ffffff;
    }

    .weather-day.is-empty {
      grid-column: 1 / -1;
      min-height: 92px;
      display: grid;
      align-content: center;
    }

    .weather-day strong,
    .weather-day span {
      display: block;
    }

    .weather-day .day-name {
      color: var(--appa-ink);
      font-size: 0.82rem;
      font-weight: 800;
    }

    .weather-day .day-date {
      color: var(--appa-muted);
      font-size: 0.74rem;
      margin-top: 2px;
    }

    .weather-range {
      margin-top: 12px;
      display: grid;
      gap: 6px;
    }

    .range-line {
      height: 7px;
      border-radius: 999px;
      background: linear-gradient(90deg, #60a5fa, #f59e0b);
    }

    .headline-card {
      border: 1px solid #e1e8f0;
      border-left: 4px solid var(--appa-accent);
      border-radius: 8px;
      padding: 12px 14px;
      background: #ffffff;
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }

    .headline-card:hover {
      transform: translateY(-1px);
      border-color: #b7c6d5;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
    }

    .headline-link {
      color: var(--appa-ink);
      text-decoration: none;
      font-weight: 750;
      line-height: 1.35;
    }

    .headline-meta {
      color: var(--appa-muted);
      font-size: 0.78rem;
      margin-top: 6px;
    }

    .q-table__container {
      border: 1px solid var(--appa-line);
      border-radius: 8px;
      box-shadow: none;
    }

    .q-table thead th {
      color: var(--appa-muted);
      background: #f8fafc;
      font-size: 0.76rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .q-table tbody td {
      color: var(--appa-ink);
      border-color: #edf2f7;
    }

    .q-table tbody tr:hover {
      background: #f8fbff;
    }

    .calendar-grid {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 7px;
    }

    .calendar-head {
      padding: 0 4px 5px;
      color: var(--appa-muted);
      font-size: 0.71rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .calendar-cell {
      min-height: 116px;
      border: 1px solid #dfe7ef;
      border-radius: 8px;
      padding: 8px;
      background: #fff;
    }

    .calendar-muted {
      background: #f8fafc;
      color: #94a3b8;
    }

    .calendar-day {
      margin-bottom: 8px;
      color: var(--appa-ink);
      font-size: 0.82rem;
      font-weight: 800;
    }

    .calendar-event {
      display: block;
      margin-bottom: 6px;
      border-radius: 6px;
      padding: 5px 6px;
      color: #123047;
      background: #e0f2fe;
      text-decoration: none;
      font-size: 0.74rem;
      line-height: 1.25;
    }

    .calendar-error {
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 10px 12px;
      color: #9f1239;
      background: #fff1f2;
      font-size: 0.85rem;
    }

    .q-field--outlined .q-field__control {
      border-radius: 8px;
    }

    .q-btn {
      border-radius: 8px;
      font-weight: 700;
      text-transform: none;
    }

    .refresh-button {
      background: var(--appa-ink) !important;
      color: #ffffff !important;
      padding-left: 14px;
      padding-right: 14px;
    }

    .interest-list {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .interest-chip {
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      padding: 5px 9px;
      background: #f8fafc;
      color: var(--appa-ink);
      font-size: 0.78rem;
      font-weight: 700;
    }

    .news-action-button {
      min-width: 34px;
      min-height: 30px;
    }

    html[data-density="compact"] .dashboard-shell {
      padding: 10px 14px 18px;
    }

    html[data-density="compact"] .appa-brand {
      padding: 12px 14px;
      gap: 10px;
    }

    html[data-density="compact"] .appa-logo {
      width: 42px;
      height: 42px;
    }

    html[data-density="compact"] .appa-title {
      font-size: 1.3rem;
    }

    html[data-density="compact"] .appa-subtitle,
    html[data-density="compact"] .appa-kicker {
      display: none;
    }

    html[data-density="compact"] .summary-cell {
      padding: 9px 12px;
    }

    html[data-density="compact"] .commandbar {
      padding: 8px 10px;
    }

    html[data-density="compact"] .kpi {
      min-height: 82px;
      padding: 11px 12px;
    }

    html[data-density="compact"] .kpi-value {
      margin-top: 6px;
      font-size: 1.45rem;
    }

    html[data-density="compact"] .expansion-shell .q-expansion-item__container > .q-item {
      min-height: 44px;
      padding: 8px 12px;
    }

    html[data-density="compact"] .expansion-shell .q-expansion-item__content > div {
      padding: 10px 12px;
    }

    html[data-density="compact"] .weather-temp {
      font-size: 2.45rem;
    }

    html[data-density="compact"] .weather-day {
      min-height: 128px;
      padding: 8px;
    }

    html[data-density="compact"] .calendar-cell {
      min-height: 96px;
    }

    html[data-density="compact"] .q-table th,
    html[data-density="compact"] .q-table td {
      padding: 6px 8px;
    }

    @media (max-width: 1180px) {
      .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      }

      .weather-panel,
      .appa-top {
        grid-template-columns: 1fr;
      }

      .appa-summary {
        min-width: 0;
      }
    }

    @media (max-width: 780px) {
      .dashboard-shell {
        padding: 12px;
      }

      .appa-brand,
      .summary-cell {
        padding: 14px;
      }

      .appa-summary,
      .weather-week,
      .stat-grid {
        grid-template-columns: 1fr;
      }

      .calendar-grid {
        overflow-x: auto;
        grid-template-columns: repeat(7, minmax(120px, 1fr));
      }
    }
    """


def _dashboard_js() -> str:
    """Fornece microinteracoes visuais sem controlar dados de negocio no navegador."""
    return """
    (function () {
      const appa = window.APPA_DASHBOARD = window.APPA_DASHBOARD || {};
      appa.currentDensity = appa.currentDensity || 'comfortable';

      appa.applyDensityControls = function () {
        document.querySelectorAll('[data-density-choice]').forEach(function (button) {
          const active = button.dataset.densityChoice === appa.currentDensity;
          button.classList.toggle('is-active', active);
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
      };

      appa.setDensity = function (mode) {
        const chosen = mode === 'compact' ? 'compact' : 'comfortable';
        appa.currentDensity = chosen;
        document.documentElement.dataset.density = chosen;
        try { localStorage.setItem('appa-dashboard-density', chosen); } catch (error) {}
        appa.applyDensityControls();
      };

      if (!appa.densityClickHandler) {
        appa.densityClickHandler = function (event) {
          const button = event.target.closest('[data-density-choice]');
          if (!button) return;
          appa.setDensity(button.dataset.densityChoice);
        };
        document.addEventListener('click', appa.densityClickHandler);
      }

      appa.tick = function () {
        const now = new Date();
        const time = new Intl.DateTimeFormat('pt-BR', {
          hour: '2-digit',
          minute: '2-digit'
        }).format(now);
        const date = new Intl.DateTimeFormat('pt-BR', {
          weekday: 'long',
          day: '2-digit',
          month: 'short'
        }).format(now);
        document.querySelectorAll('[data-appa-clock]').forEach(function (node) {
          node.textContent = time;
        });
        document.querySelectorAll('[data-appa-date]').forEach(function (node) {
          node.textContent = date;
        });
      };

      appa.boot = function () {
        document.body.classList.add('appa-dashboard');
        let stored = document.documentElement.dataset.density || 'comfortable';
        try { stored = localStorage.getItem('appa-dashboard-density') || stored; }
        catch (error) {}
        appa.setDensity(stored);
        appa.tick();
        if (!appa.clockTimer) {
          appa.clockTimer = window.setInterval(appa.tick, 30000);
        }
        if (!appa.observer && document.body) {
          appa.observer = new MutationObserver(function () {
            window.requestAnimationFrame(function () {
              appa.applyDensityControls();
              appa.tick();
            });
          });
          appa.observer.observe(document.body, { childList: true, subtree: true });
        }
      };

      document.addEventListener('DOMContentLoaded', appa.boot);
      window.setTimeout(appa.boot, 250);
    })();
    """


def construir_dashboard(
    servico: DashboardService,
    snapshot_inicial: DashboardSnapshot | None = None,
) -> None:
    """Constroi um dashboard denso, visual e voltado a acompanhamento diario."""
    _registrar_assets_dashboard()
    with ui.column().classes("dashboard-shell gap-4"):
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
                """
                <div class="density-toggle" aria-label="Densidade do painel">
                  <button
                    type="button"
                    data-density-choice="comfortable"
                  >
                    Conforto
                  </button>
                  <button
                    type="button"
                    data-density-choice="compact"
                  >
                    Compacto
                  </button>
                </div>
                """
            )
            ui.html(
                """
                <div class="commandbar-note">
                  <span class="status-dot"></span>
                  <span>Atualizacao local ativa</span>
                </div>
                """
            )
            ui.button(
                "Atualizar",
                icon="refresh",
                on_click=lambda: atualizar(),
            ).classes("refresh-button")
            status = ui.label("Painel pronto.").classes("dashboard-status ml-auto")

        kpi_cards = _criar_kpis(snapshot_inicial)
        with ui.grid(columns=6).classes("kpi-grid w-full gap-3"):
            for card in kpi_cards:
                with ui.element("div").classes("kpi"):
                    ui.label(card["label"]).classes("kpi-label")
                    valor = ui.label(card["value"]).classes("kpi-value")
                    detalhe = ui.label(card["detail"]).classes("text-sm text-slate-500")
                    card["widgets"] = (valor, detalhe)

        with ui.grid(columns=3).classes("w-full gap-4"):
            with ui.column().classes("col-span-2 gap-4"):
                with ui.expansion(
                    "Radar do Dia",
                    caption="Clima de hoje e tendencia dos proximos sete dias.",
                    value=True,
                    icon="insights",
                ).classes("expansion-shell w-full"):
                    clima_resumo = _render_clima_resumo(snapshot_inicial)

                with ui.expansion(
                    "Santa Maria em Foco",
                    caption="Cobertura local validada para o dia atual.",
                    value=True,
                    icon="location_city",
                ).classes("expansion-shell w-full"):
                    santa_maria_cards = ui.column().classes("w-full gap-3")
                    _popular_santa_maria_em_foco(
                        santa_maria_cards,
                        snapshot_inicial.santa_maria_em_foco if snapshot_inicial else [],
                        servico.config.localizacao.timezone,
                        servico,
                        status,
                    )

                with ui.expansion(
                    "Feed Priorizado",
                    caption=(
                        "The News geral, tecnologia e economia global "
                        "do mais recente ao mais antigo."
                    ),
                    value=True,
                    icon="newspaper",
                ).classes("expansion-shell w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        noticias_total = ui.label("").classes("text-sm text-slate-500")

                    linhas_iniciais = _linhas_noticias(
                        _noticias_sem_santa_maria(snapshot_inicial.noticias)
                        if snapshot_inicial
                        else [],
                        servico.config.localizacao.timezone,
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
                            {"name": "publicado", "label": "Quando", "field": "publicado"},
                            {
                                "name": "acoes",
                                "label": "",
                                "field": "acoes",
                                "align": "right",
                            },
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
                            rel="noopener noreferrer"
                            @click="$parent.$emit('registrar-noticia', props.row)"
                            style="color:#0f172a;text-decoration:none;font-weight:600;"
                          >
                            {{ props.row.titulo }}
                          </a>
                        </q-td>
                        """,
                    )
                    tabela_noticias.add_slot(
                        "body-cell-acoes",
                        """
                        <q-td :props="props">
                          <q-btn
                            dense
                            flat
                            round
                            icon="bookmark_add"
                            class="news-action-button"
                            title="Salvar no Obsidian"
                            @click.stop="$parent.$emit('registrar-noticia', props.row)"
                          />
                        </q-td>
                        """,
                    )
                    tabela_noticias.on(
                        "registrar-noticia",
                        lambda evento: _salvar_noticia_observada(
                            servico,
                            evento.args,
                            status,
                        ),
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
                with ui.expansion(
                    "Interesses de Pesquisa",
                    caption="Tags usadas para priorizar o feed e organizar seu perfil.",
                    value=True,
                    icon="sell",
                ).classes("expansion-shell w-full"):
                    interesses_container = ui.element("div").classes("interest-list")
                    _popular_interesses(
                        interesses_container,
                        servico.config.fontes.noticias.interesses_busca,
                    )
                    interesse_texto = ui.textarea("Adicionar interesses").classes("w-full")
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
                        ),
                    ).classes("w-full")

                with ui.expansion(
                    "Google Agenda",
                    caption="Calendario mensal e criacao rapida de eventos.",
                    value=True,
                    icon="calendar_month",
                ).classes("expansion-shell w-full"):
                    agenda_mes_titulo = ui.label("").classes("section-title")
                    agenda_erro = ui.html("").classes("w-full")
                    calendario_google = ui.column().classes("w-full gap-2")
                    google_lista = ui.column().classes("gap-2")
                    _popular_agenda_google(
                        calendario_google,
                        google_lista,
                        agenda_erro,
                        agenda_mes_titulo,
                        snapshot_inicial.agenda_google_resultado if snapshot_inicial else None,
                        servico.config.localizacao.timezone,
                    )
                    ui.separator()
                    ui.label("Adicionar evento").classes("section-title")
                    evento_titulo = ui.input("Titulo").classes("w-full")
                    with ui.row().classes("w-full gap-3"):
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
                    evento_descricao.props("rows=4")
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

        def atualizar() -> None:
            """Recarrega os dados dinamicos sem reconstruir a pagina inteira."""
            try:
                snapshot = servico.carregar(
                    limite_noticias=int(limite_noticias.value or LIMITE_PADRAO_NOTICIAS),
                )
            except Exception as exc:  # pragma: no cover
                avisar(str(exc))
                status.text = f"Falha ao carregar painel: {exc}"
                return

            _atualizar_kpis(kpi_cards, snapshot)
            _atualizar_clima_resumo(clima_resumo, snapshot)
            _popular_santa_maria_em_foco(
                santa_maria_cards,
                snapshot.santa_maria_em_foco,
                servico.config.localizacao.timezone,
                servico,
                status,
            )
            tabela_noticias.rows = _linhas_noticias(
                _noticias_sem_santa_maria(snapshot.noticias),
                servico.config.localizacao.timezone,
            )
            tabela_noticias.update()
            noticias_feed = len(_noticias_sem_santa_maria(snapshot.noticias))
            noticias_total.text = (
                f"{noticias_feed} no feed | {len(snapshot.noticias)} no total | atualizado "
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

        total_feed_inicial = (
            len(_noticias_sem_santa_maria(snapshot_inicial.noticias)) if snapshot_inicial else 0
        )
        total_inicial = len(snapshot_inicial.noticias) if snapshot_inicial else 0
        noticias_total.text = f"{total_feed_inicial} no feed | {total_inicial} no total"
        cliente_dashboard = ui.context.client

        def atualizar_automaticamente() -> None:
            """Executa o refresh automatico apenas enquanto o cliente esta conectado."""
            if not atualizacao_auto.value or not cliente_dashboard.has_socket_connection:
                return
            with cliente_dashboard:
                atualizar()

        timer_atualizacao = app.timer(90.0, atualizar_automaticamente, immediate=False)
        cliente_dashboard.on_delete(
            lambda *_args: timer_atualizacao.cancel(with_current_invocation=True)
        )


def _cabecalho(snapshot: DashboardSnapshot | None) -> None:
    """Renderiza a faixa superior com contexto operacional do painel."""
    atualizado = escape(snapshot.atualizado_em if snapshot else "--:--:--")
    with ui.element("section").classes("appa-top w-full"):
        with ui.element("div").classes("appa-brand"):
            ui.image(_logo_appa_src()).classes("appa-logo")
            with ui.column().classes("gap-1"):
                ui.html('<p class="appa-kicker">Centro de controle pessoal</p>')
                ui.html('<h1 class="appa-title">APPA</h1>')
                ui.html(
                    """
                    <p class="appa-subtitle">
                      Assistente Pessoal Personalizado e Automatizado
                    </p>
                    """
                )
        ui.html(
            f"""
            <div class="appa-summary">
              <div class="summary-cell">
                <span>Agora</span>
                <strong data-appa-clock>--:--</strong>
              </div>
              <div class="summary-cell">
                <span>Data local</span>
                <strong data-appa-date>--</strong>
              </div>
              <div class="summary-cell">
                <span>Ultima leitura</span>
                <strong data-appa-updated>{atualizado}</strong>
              </div>
              <div class="summary-cell">
                <span>Modo</span>
                <strong>Local</strong>
              </div>
            </div>
            """
        )


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
            {
                "label": "Google Agenda",
                "value": str(snapshot.indicadores.eventos_google),
                "detail": "Eventos futuros sincronizados",
            },
            {
                "label": "Dolar agora",
                "value": _formatar_dolar(snapshot),
                "detail": _detalhe_dolar(snapshot),
            },
        ]
    return [
        {"label": "Noticias no radar", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "The News em destaque", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "Santa Maria hoje", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "Temperatura alvo", "value": "--", "detail": "Sem dados iniciais"},
        {"label": "Google Agenda", "value": "0", "detail": "Sem dados iniciais"},
        {"label": "Dolar agora", "value": "--", "detail": "Sem dados iniciais"},
    ]


def _atualizar_kpis(kpis: list[dict], snapshot: DashboardSnapshot) -> None:
    """Atualiza os cards de topo sem recriar seus elementos."""
    novos = _criar_kpis(snapshot)
    for card, novo in zip(kpis, novos, strict=False):
        valor, detalhe = card["widgets"]
        valor.text = novo["value"]
        detalhe.text = novo["detail"]


def _formatar_dolar(snapshot: DashboardSnapshot) -> str:
    """Formata USD/BRL para um card compacto."""
    valor = snapshot.cotacao_dolar.valor
    if valor is None:
        return "--"
    return f"R$ {valor:.2f}".replace(".", ",")


def _detalhe_dolar(snapshot: DashboardSnapshot) -> str:
    cotacao = snapshot.cotacao_dolar
    if cotacao.valor is None:
        return "Cotacao indisponivel agora"
    partes: list[str] = []
    if cotacao.variacao_percentual is not None:
        partes.append(f"{cotacao.variacao_percentual:+.2f}%".replace(".", ","))
    if cotacao.horario is not None:
        partes.append(f"Atualizado {cotacao.horario.strftime('%H:%M')}")
    partes.append(cotacao.fonte)
    return " | ".join(partes)


def _render_clima_resumo(snapshot: DashboardSnapshot | None) -> dict[str, ui.element]:
    """Constroi o resumo visual de clima em estilo dashboard."""
    with ui.element("div").classes("weather-panel w-full"):
        with ui.element("div").classes("weather-now"):
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
        semana = ui.element("div").classes("weather-week")
        _popular_semana_clima(semana, snapshot.resumo_semana if snapshot else [])
    return {
        "cidade": cidade,
        "data": data,
        "referencia": referencia,
        "temperatura": temperatura,
        "maxima": maxima,
        "minima": minima,
        "chuva": chuva,
        "contexto": contexto,
        "semana": semana,
    }


def _atualizar_clima_resumo(widgets: dict[str, ui.element], snapshot: DashboardSnapshot) -> None:
    """Atualiza o bloco principal de clima."""
    previsao = snapshot.previsao
    widgets["cidade"].text = previsao.cidade
    widgets["data"].text = previsao.data_alvo.isoformat()
    widgets["referencia"].text = _rotulo_referencia_clima(previsao)
    widgets["temperatura"].text = _formatar_grau(previsao.temperatura_referencia)
    widgets["maxima"].text = _formatar_grau(previsao.maxima)
    widgets["minima"].text = _formatar_grau(previsao.minima)
    widgets["chuva"].text = _formatar_chuva(previsao.chuva)
    widgets["contexto"].text = _texto_contexto_clima(previsao)
    _popular_semana_clima(widgets["semana"], snapshot.resumo_semana)


def _stat_box(rotulo: str, valor: str) -> ui.label:
    """Cria uma mini caixa numerica para os blocos de clima."""
    with ui.element("div").classes("stat-box"):
        ui.label(rotulo).classes("text-xs text-slate-500")
        texto = ui.label(valor).classes("text-lg font-semibold")
    return texto


def _popular_semana_clima(container: ui.element, resumo: list[ResumoClimaDia]) -> None:
    """Renderiza a faixa semanal de maxima, minima e chance de chuva."""
    container.clear()
    with container:
        if not resumo:
            ui.html(
                """
                <div class="weather-day is-empty">
                  <strong class="day-name">Semana indisponivel</strong>
                  <span class="day-date">A Open-Meteo nao retornou a faixa semanal agora.</span>
                </div>
                """
            )
            return
        for dia in resumo[:7]:
            rotulo = escape(_rotulo_dia_curto(dia))
            data = escape(dia.data.strftime("%d/%m"))
            maxima = escape(_formatar_grau(dia.maxima))
            minima = escape(_formatar_grau(dia.minima))
            chuva = escape(_formatar_chuva(dia.chuva))
            ui.html(
                f"""
                <div class="weather-day">
                  <strong class="day-name">{rotulo}</strong>
                  <span class="day-date">{data}</span>
                  <div class="weather-range">
                    <span>Max {maxima}</span>
                    <div class="range-line"></div>
                    <span>Min {minima}</span>
                    <span>Chuva {chuva}</span>
                  </div>
                </div>
                """
            )


def _rotulo_dia_curto(dia: ResumoClimaDia) -> str:
    """Devolve o nome curto do dia sem depender do locale do Windows."""
    nomes = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
    return nomes[dia.data.weekday()]


def _formatar_grau(valor: float | None) -> str:
    """Formata temperatura de forma compacta para os cards do dashboard."""
    if valor is None:
        return "--"
    return f"{valor:g} C"


def _formatar_chuva(valor: float | None) -> str:
    """Formata chance de chuva preservando ausencia de dados."""
    if valor is None:
        return "--"
    return f"{valor:g}%"


def _rotulo_referencia_clima(previsao: PrevisaoClima) -> str:
    """Explica se o numero principal do clima representa agora ou um dia futuro."""
    return "Agora" if previsao.e_hoje else "Temperatura prevista"


def _texto_contexto_clima(previsao: PrevisaoClima) -> str:
    """Monta um contexto coerente para hoje e para dias futuros."""
    if previsao.e_hoje:
        return f"Sensacao {previsao.sensacao} C | Vento {previsao.vento} km/h"
    return f"Vento previsto {previsao.vento} km/h | Chance de chuva {previsao.chuva}%"


def _linhas_noticias(noticias: list[Noticia], timezone: str) -> list[dict]:
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
                "publicado": texto_terminal_seguro(
                    rotulo_tempo_publicacao(noticia, timezone=timezone)
                ),
                "link": _link_seguro(noticia.link),
                "cor": GRUPOS_COR.get(noticia.grupo, "#475569"),
            }
        )
    return linhas


def _link_seguro(link: str) -> str:
    """Aceita apenas links HTTP(S) para conteudo externo exibido em HTML."""
    link_limpo = link.strip()
    if link_limpo.startswith(("https://", "http://")):
        return link_limpo
    return "#"


def _noticias_por_grupo(noticias: list[Noticia], grupo: str) -> list[Noticia]:
    """Filtra um subconjunto de noticias para blocos tematicos do dashboard."""
    return [noticia for noticia in noticias if noticia.grupo == grupo]


def _noticias_sem_santa_maria(noticias: list[Noticia]) -> list[Noticia]:
    """Mantem o painel principal focado em noticias gerais, sem duplicar o bloco local."""
    return [noticia for noticia in noticias if noticia.grupo != "santa_maria"]


def _popular_santa_maria_em_foco(
    container: ui.column,
    noticias: list[Noticia],
    timezone: str,
    servico: DashboardService | None = None,
    status_label=None,
) -> None:
    """Renderiza um bloco visual para noticias locais, sem depender da tabela principal."""
    container.clear()
    if not noticias:
        with container:
            with ui.element("div").classes("headline-card"):
                ui.label("Sem noticias locais validadas no dia atual.").classes(
                    "text-sm font-semibold text-slate-700"
                )
                ui.label(
                    "Quando as fontes locais nao publicam data confiavel, "
                    "o painel prefere nao inventar resultado."
                ).classes("headline-meta")
        return
    with container:
        for noticia in noticias[:6]:
            with ui.element("div").classes("headline-card"):
                titulo = texto_terminal_seguro(noticia.titulo)
                meta = (
                    f"{texto_terminal_seguro(noticia.fonte)} | "
                    f"{texto_terminal_seguro(rotulo_tempo_publicacao(noticia, timezone=timezone))}"
                )
                link = _link_seguro(noticia.link)
                if servico is not None and status_label is not None:
                    link_widget = ui.link(titulo, link, new_tab=True).classes("headline-link")
                    link_widget.on(
                        "click",
                        lambda _evento, noticia=noticia: _salvar_noticia_observada(
                            servico,
                            noticia,
                            status_label,
                        ),
                    )
                else:
                    ui.html(
                        '<a class="headline-link" '
                        f'href="{escape(link, quote=True)}" '
                        'target="_blank" rel="noopener noreferrer">'
                        f"{escape(titulo)}</a>"
                    )
                ui.label(meta).classes("headline-meta")


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


def _popular_interesses(container: ui.element, interesses: list[str]) -> None:
    """Renderiza os interesses cadastrados como chips simples."""
    container.clear()
    with container:
        if not interesses:
            ui.html('<span class="section-subtitle">Nenhum interesse cadastrado.</span>')
            return
        for interesse in interesses:
            ui.html(f'<span class="interest-chip">{escape(interesse)}</span>')


def _adicionar_interesses_gui(
    servico: DashboardService,
    campo_interesses,
    interesses_container: ui.element,
    status_label,
    painel_status,
) -> None:
    """Valida e salva interesses informados no painel."""
    texto = str(campo_interesses.value or "")
    if not texto.strip():
        status_label.text = "Digite ao menos um interesse."
        return
    try:
        interesses = servico.adicionar_interesses(texto)
    except Exception as exc:  # pragma: no cover
        status_label.text = f"Falha ao salvar interesses: {exc}"
        painel_status.text = status_label.text
        return
    campo_interesses.value = ""
    _popular_interesses(interesses_container, interesses)
    status_label.text = "Interesses salvos no config e no Obsidian."
    painel_status.text = "Interesses de pesquisa atualizados."


def _salvar_noticia_observada(
    servico: DashboardService,
    dados_noticia,
    status_label,
) -> None:
    """Registra uma noticia aberta ou marcada pelo usuario no Obsidian."""
    noticia = _normalizar_evento_noticia(dados_noticia)
    if noticia is None:
        status_label.text = "Nao consegui identificar a noticia para salvar."
        return
    try:
        caminho = servico.salvar_noticia_obsidian(noticia, origem="clique")
    except Exception as exc:  # pragma: no cover
        status_label.text = f"Falha ao salvar noticia: {exc}"
        return
    status_label.text = f"Noticia salva no Obsidian em {caminho}."
    ui.notify("Noticia salva no Obsidian.", type="positive")


def _normalizar_evento_noticia(dados_noticia):
    if isinstance(dados_noticia, Noticia):
        return dados_noticia
    if isinstance(dados_noticia, dict):
        return dados_noticia
    if isinstance(dados_noticia, list) and dados_noticia:
        primeiro = dados_noticia[0]
        if isinstance(primeiro, dict) or isinstance(primeiro, Noticia):
            return primeiro
    return None


def _popular_agenda_google(
    calendario_container: ui.column,
    lista_container: ui.column,
    erro_container,
    titulo_widget,
    resultado: ResultadoGoogleAgenda | None,
    timezone: str,
) -> None:
    """Atualiza o calendario mensal e a lista resumida de eventos do Google."""
    calendario_container.clear()
    lista_container.clear()
    erro_container.content = ""
    if resultado is None:
        titulo_widget.text = "Google Agenda"
        return
    referencia = resultado.mes_referencia or datetime.now().date().replace(day=1)
    titulo_widget.text = referencia.strftime("%B de %Y").capitalize()
    if resultado.erro:
        erro_container.content = f'<div class="calendar-error">{escape(resultado.erro)}</div>'
    _renderizar_calendario_google(calendario_container, resultado.eventos, referencia, timezone)
    if not resultado.eventos:
        with lista_container:
            ui.label("Nenhum evento encontrado para este mes.").classes("text-sm text-slate-500")
        return
    with lista_container:
        ui.label("Eventos do mes").classes("section-title")
        for evento in resultado.eventos[:10]:
            with ui.element("div").classes("stat-box"):
                ui.label(evento.titulo).classes("text-sm font-semibold text-slate-800")
                ui.label(formatar_data_hora_google(evento.inicio, timezone)).classes(
                    "text-xs text-slate-500"
                )
                if evento.local:
                    ui.label(evento.local).classes("text-xs text-slate-500")


def _renderizar_calendario_google(
    container: ui.column,
    eventos: list[EventoGoogleAgenda],
    referencia: datetime.date,
    timezone: str,
) -> None:
    """Desenha um calendario mensal simples com os eventos agrupados por dia."""
    eventos_por_dia: dict[int, list[EventoGoogleAgenda]] = {}
    for evento in eventos:
        data = data_evento_google(evento)
        if data is None or data.month != referencia.month or data.year != referencia.year:
            continue
        eventos_por_dia.setdefault(data.day, []).append(evento)
    semanas = calendar.Calendar(firstweekday=6).monthdayscalendar(referencia.year, referencia.month)
    with container:
        with ui.element("div").classes("calendar-grid w-full"):
            for nome in ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]:
                ui.label(nome).classes("calendar-head")
            for semana in semanas:
                for dia in semana:
                    classes = "calendar-cell"
                    if dia == 0:
                        classes += " calendar-muted"
                    with ui.element("div").classes(classes):
                        ui.label("" if dia == 0 else str(dia)).classes("calendar-day")
                        for evento in eventos_por_dia.get(dia, [])[:3]:
                            titulo = texto_terminal_seguro(evento.titulo)
                            horario = formatar_data_hora_google(
                                evento.inicio,
                                timezone,
                            ).split(" ", 1)
                            prefixo = horario[1] if len(horario) > 1 else horario[0]
                            link = escape(_link_seguro(evento.link), quote=True)
                            ui.html(
                                '<a class="calendar-event" '
                                f'href="{link}" '
                                'target="_blank" rel="noopener noreferrer">'
                                f"{escape(prefixo)} | {escape(titulo)}</a>"
                            )


def _criar_evento_google(
    servico: DashboardService,
    titulo: str,
    data_texto: str,
    hora_texto: str,
    duracao_minutos,
    local: str,
    descricao: str,
    status_label,
    painel_status,
    calendario_google: ui.column,
    google_lista: ui.column,
    agenda_erro,
    agenda_mes_titulo,
) -> None:
    """Cria um evento simples na Google Agenda e atualiza o calendario mensal."""
    if not titulo.strip() or not data_texto.strip() or not hora_texto.strip():
        status_label.text = "Preencha titulo, data e hora para criar o evento."
        return
    try:
        inicio = datetime.fromisoformat(f"{data_texto.strip()}T{hora_texto.strip()}:00").replace(
            tzinfo=ZoneInfo(servico.config.localizacao.timezone)
        )
    except ValueError:
        status_label.text = "Use data no formato AAAA-MM-DD e hora no formato HH:MM."
        return
    evento = NovoEventoGoogleAgenda(
        titulo=titulo.strip(),
        inicio=inicio,
        fim=inicio + timedelta(minutes=int(duracao_minutos or 60)),
        local=local.strip(),
        descricao=descricao.strip(),
    )
    try:
        servico.google_agenda.criar_evento(evento)
        resultado = servico.google_agenda.obter_eventos_mes(inicio.date())
    except RuntimeError as exc:
        status_label.text = str(exc)
        painel_status.text = str(exc)
        return
    _popular_agenda_google(
        calendario_google,
        google_lista,
        agenda_erro,
        agenda_mes_titulo,
        resultado,
        servico.config.localizacao.timezone,
    )
    status_label.text = "Evento criado no Google Agenda."
    painel_status.text = "Google Agenda atualizada com sucesso."


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
