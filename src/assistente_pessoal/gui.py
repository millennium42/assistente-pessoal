"""Dashboard grafico local baseado em NiceGUI."""

from __future__ import annotations

import calendar
import hashlib
import socket
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from nicegui import app, core, ui

from assistente_pessoal.agenda_google import (
    EventoGoogleAgenda,
    NovoEventoGoogleAgenda,
    ResultadoGoogleAgenda,
    data_evento_google,
    evento_google_ainda_futuro,
    formatar_data_hora_google,
)
from assistente_pessoal.clima import PrevisaoClima, ResumoClimaDia
from assistente_pessoal.config import AppConfig
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
    "interesses": "Interesses",
}

GRUPOS_COR = {
    "the_news": "#22d3ee",
    "santa_maria": "#34d399",
    "tech": "#f472b6",
    "economia_global": "#fbbf24",
    "interesses": "#a3e635",
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
    ui.run(
        host=host,
        port=port,
        title=titulo,
        reload=False,
        show=False,
        root=lambda: construir_dashboard(servico),
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


def _executar_javascript(codigo: str) -> None:
    """Executa JS apenas quando o contexto do NiceGUI tem loop ativo."""
    if core.loop is None:
        return
    ui.run_javascript(codigo)


def _logo_appa_src() -> str:
    """Retorna a URL servida pelo dashboard para o logo minimalista."""
    if not LOGO_APPA_FILE.exists():
        return ""
    return f"{ASSETS_ROUTE}/{LOGO_APPA_FILE.name}"


def _dashboard_css() -> str:
    """Mantem o tema visual centralizado para facilitar futuras iteracoes de produto."""
    return """
    :root {
      --appa-bg: #050810;
      --appa-panel: #0b111a;
      --appa-panel-soft: #141c2b;
      --appa-panel-strong: #0f172a;
      --appa-ink: #edf2f7;
      --appa-muted: #94a3b8;
      --appa-line: rgba(148, 163, 184, 0.12);
      --appa-accent: #14b8a6;
      --appa-blue: #60a5fa;
      --appa-green: #22c55e;
      --appa-amber: #f59e0b;
      --appa-rose: #fb7185;
      --appa-magenta: #e879f9;
      --appa-shadow: 0 12px 32px rgba(0, 240, 255, 0.08);
      --appa-cell: #111827;
      --appa-command: rgba(11, 17, 26, 0.85);
      --appa-card-bg: #0b111a;
      --appa-card-subtle: #172033;
      --appa-empty: #121a2a;
      --appa-input-bg: #0f172a;
      --appa-button-ink: #052e2b;
      --appa-chart-axis: #94a3b8;
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
    }
    .weather-now {
      background: var(--appa-card-bg);
      border: 1px solid var(--appa-line);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
      backdrop-filter: blur(16px);
      border-radius: 12px;
      padding: 16px;
    }
    .stat-box {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
    }
    .stat-grid-modern {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    

    .detail-metric {
      display: flex;
    }

    .climate-pill {
      border: 1px solid var(--appa-line);
      border-radius: 999px;
      padding: 4px 8px;
      background: var(--appa-card-subtle);
      color: var(--appa-muted);
      font-size: 0.64rem;
      font-weight: 800;
      text-transform: uppercase;
    }
    .text-neon {
      color: var(--appa-accent);
    }

    html[data-theme="light"] {
      --appa-bg: #f6f8fb;
      --appa-panel: #ffffff;
      --appa-panel-soft: #f1f5f9;
      --appa-panel-strong: #e8eef6;
      --appa-ink: #142033;
      --appa-muted: #607086;
      --appa-line: rgba(64, 85, 112, 0.16);
      --appa-accent: #0f766e;
      --appa-blue: #2563eb;
      --appa-green: #059669;
      --appa-amber: #b45309;
      --appa-rose: #be123c;
      --appa-magenta: #a21caf;
      --appa-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
      --appa-cell: #ffffff;
      --appa-command: rgba(255, 255, 255, 0.96);
      --appa-card-bg: #ffffff;
      --appa-card-subtle: #f4f7fb;
      --appa-empty: #f1f5f9;
      --appa-input-bg: #ffffff;
      --appa-button-ink: #ffffff;
      --appa-chart-axis: #64748b;
    }

    html[data-density="compact"] {
      --appa-card-pad: 12px;
      --appa-row-gap: 10px;
    }

    html[data-density="comfortable"] {
      --appa-card-pad: 8px;
      --appa-row-gap: 10px;
    }

    body.appa-dashboard {
      background: var(--appa-bg);
      color: var(--appa-ink);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .appa-dashboard .q-page,
    .appa-dashboard .nicegui-content {
      background: transparent;
    }

    .appa-dashboard .text-slate-400,
    .appa-dashboard .text-slate-500 {
      color: var(--appa-muted) !important;
    }

    .appa-dashboard .text-slate-700,
    .appa-dashboard .text-slate-800 {
      color: var(--appa-ink) !important;
    }

    .dashboard-shell {
      max-width: 1220px;
      margin: 0 auto;
      padding: 10px 14px 18px;
    }

    .dashboard-shell {
      max-width: 1520px;
    }

    

    body.appa-dashboard {
      background:
        linear-gradient(90deg, rgba(20, 184, 166, 0.075) 1px, transparent 1px),
        linear-gradient(180deg, rgba(96, 165, 250, 0.06) 1px, transparent 1px),
        var(--appa-bg);
      background-size: 32px 32px, 32px 32px, auto;
    }

    [data-theme="light"] body.appa-dashboard {
      background:
        linear-gradient(90deg, rgba(15, 118, 110, 0.08) 1px, transparent 1px),
        linear-gradient(180deg, rgba(37, 99, 235, 0.055) 1px, transparent 1px),
        var(--appa-bg);
      background-size: 32px 32px, 32px 32px, auto;
    }

    .appa-top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: stretch;
      background:
        linear-gradient(90deg, var(--appa-panel), var(--appa-panel-strong));
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
      overflow: hidden;
    }

    

    .appa-top {
      min-height: 86px;
      grid-template-columns: minmax(0, 0.9fr) minmax(420px, 0.65fr);
    }

    .appa-brand {
      display: flex;
      gap: 16px;
      align-items: center;
      padding: 18px 20px;
      border-left: 5px solid var(--appa-accent);
    }

    .appa-brand {
      padding: 10px 14px;
      gap: 10px;
    }

    .appa-logo {
      width: 58px;
      height: 58px;
      border-radius: 12px;
      object-fit: cover;
      border: 1px solid rgba(34, 211, 238, 0.42);
      background: var(--appa-panel-soft);
      box-shadow: 0 0 24px rgba(34, 211, 238, 0.16);
    }

    .appa-logo {
      width: 38px;
      height: 38px;
      box-shadow: none;
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
      font-size: 1.15rem;
      line-height: 1.1;
      font-weight: 800;
      color: var(--appa-ink);
    }

    

    .appa-title {
      font-size: 1.02rem;
    }

    .appa-subtitle,
    .appa-kicker {
      display: none;
    }

    .appa-subtitle {
      margin: 5px 0 0;
      color: var(--appa-muted);
      font-size: 0.75rem;
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
      background: var(--appa-cell);
      padding: 15px 18px;
    }

    .summary-cell {
      padding: 8px 12px;
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
      background: var(--appa-command);
      backdrop-filter: blur(10px);
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 12px 14px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
    }

    

    .commandbar {
      padding: 7px 9px;
      box-shadow: none;
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
      box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.16), 0 0 18px rgba(34, 197, 94, 0.24);
    }

    .view-toggle,
    .theme-toggle {
      display: inline-flex;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      background: var(--appa-card-subtle);
    }

    .view-toggle button,
    .theme-toggle button {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 0;
      border-radius: 6px;
      padding: 5px 8px;
      color: var(--appa-muted);
      background: transparent;
      font-weight: 700;
      font-size: 0.72rem;
      cursor: pointer;
    }

    .view-toggle button.is-active,
    .theme-toggle button.is-active {
      color: var(--appa-ink);
      background: color-mix(in srgb, var(--appa-accent) 13%, transparent);
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--appa-accent) 28%, transparent);
    }

    .view-toggle .q-icon,
    .theme-toggle .q-icon,
    .appa-seg-icon {
      font-size: 14px;
      line-height: 1;
    }

    .kpi-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    }

    .kpi-grid {
      grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
    }

    .kpi {
      position: relative;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent),
        var(--appa-panel);
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: var(--appa-card-pad, 16px);
      min-height: 60px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
      overflow: hidden;
    }

    

    .kpi {
      min-height: 76px;
      padding: 10px 11px;
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
    .kpi:nth-child(3)::before { background: var(--appa-green); }
    .kpi:nth-child(4)::before { background: var(--appa-amber); }
    .kpi:nth-child(5)::before { background: var(--appa-magenta); }
    .kpi:nth-child(6)::before { background: var(--appa-rose); }

    .kpi-label {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--appa-muted);
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
    }

    .kpi-icon {
      color: var(--appa-accent);
      font-size: 14px;
    }

    .kpi-detail {
      color: var(--appa-muted);
    }

    

    .kpi-value {
      margin-top: 9px;
      color: var(--appa-ink);
      font-size: 1.2rem;
      font-weight: 800;
      line-height: 1;
    }

    

    .kpi-value {
      font-size: 1.25rem;
    }

    .overview-charts-grid,
    .overview-local-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    

    

    

    .chart-weather,
    .chart-news {
      height: 230px;
    }

    .overview-local-grid {
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr) !important;
    }

    .expansion-shell {
      background: var(--appa-panel);
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
    }

    .expansion-shell .q-expansion-item__container > .q-item {
      min-height: 52px;
      padding: 11px 14px;
      background: var(--appa-cell);
      border-bottom: 1px solid var(--appa-line);
    }

    .expansion-shell .q-item__section--avatar,
    .expansion-shell .q-icon,
    .expansion-shell .q-expansion-item__toggle-icon {
      color: var(--appa-accent);
    }

    .expansion-shell .q-item__label {
      color: var(--appa-ink);
      font-weight: 800;
      font-size: 0.96rem;
    }

    .expansion-shell .q-item__label--caption {
      color: var(--appa-muted);
      font-weight: 500;
      font-size: 0.76rem;
    }

    .expansion-shell .q-expansion-item__content > div {
      padding: 14px;
      background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.035), transparent 180px),
        var(--appa-panel);
    }

    .section-title {
      color: var(--appa-ink);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0;
    }

    .section-title {
      font-size: 0.72rem;
      text-transform: uppercase;
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
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 10px 12px;
      background: var(--appa-card-subtle);
    }

    .weather-panel {
      display: grid;
      grid-template-columns: minmax(260px, 0.9fr) minmax(0, 1.1fr);
      gap: 16px;
      align-items: stretch;
    }

    .weather-now {
      border: 1px solid rgba(52, 211, 153, 0.28);
      border-radius: 12px;
      padding: 16px;
      background: var(--appa-card-bg);
    }

    

    .weather-now {
      min-height: 100%;
      padding: 12px;
    }

    .weather-temp {
      color: var(--appa-ink);
      font-size: 2.35rem;
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
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 10px;
      background: var(--appa-card-bg);
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
      background: linear-gradient(90deg, var(--appa-blue), var(--appa-amber));
    }

    .headline-card {
      border: 1px solid var(--appa-line);
      border-left: 4px solid var(--appa-accent);
      border-radius: 12px;
      padding: 12px 14px;
      background: var(--appa-card-bg);
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }

    .headline-card:hover {
      transform: translateY(-1px);
      border-color: rgba(34, 211, 238, 0.52);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
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
      border-radius: 12px;
      box-shadow: none;
      background: var(--appa-panel);
      color: var(--appa-ink);
    }

    .q-table {
      background: var(--appa-panel);
    }

    .q-table thead th {
      color: var(--appa-muted);
      background: var(--appa-panel-soft);
      font-size: 0.76rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .q-table tbody td {
      color: var(--appa-ink);
      border-color: var(--appa-line);
    }

    .q-table tbody tr:hover {
      background: rgba(34, 211, 238, 0.08);
    }

    .ag-theme-balham-dark {
      --ag-background-color: var(--appa-card-bg);
      --ag-foreground-color: var(--appa-ink);
      --ag-header-background-color: var(--appa-panel-soft);
      --ag-header-foreground-color: var(--appa-muted);
      --ag-border-color: var(--appa-line);
      --ag-row-hover-color: color-mix(in srgb, var(--appa-accent) 8%, transparent);
      --ag-odd-row-background-color: var(--appa-card-bg);
      --ag-control-panel-background-color: var(--appa-panel-soft);
    }

    .calendar-grid {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 5px;
    }

    .calendar-head {
      padding: 0 3px 4px;
      color: var(--appa-muted);
      font-size: 0.66rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .calendar-cell {
      min-height: 90px;
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 6px;
      background: var(--appa-card-bg);
    }

    .calendar-muted {
      background: var(--appa-card-subtle);
      color: #64748b;
    }

    .calendar-day {
      margin-bottom: 5px;
      color: var(--appa-ink);
      font-size: 0.74rem;
      font-weight: 800;
    }

    .calendar-events {
      display: grid;
      gap: 4px;
    }

    .calendar-event {
      display: block;
      border-radius: 6px;
      padding: 4px 5px;
      color: var(--appa-ink);
      background: rgba(34, 211, 238, 0.14);
      border: 1px solid rgba(34, 211, 238, 0.22);
      text-decoration: none;
      font-size: 0.68rem;
      line-height: 1.18;
      overflow: hidden;
    }

    .calendar-event-time {
      display: block;
      margin-bottom: 2px;
      color: color-mix(in srgb, var(--appa-accent) 72%, white);
      font-size: 0.61rem;
      font-weight: 800;
      letter-spacing: 0.01em;
    }

    .calendar-event-title {
      display: -webkit-box;
      overflow: hidden;
      text-overflow: ellipsis;
      overflow-wrap: anywhere;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }

    .calendar-more {
      color: var(--appa-muted);
      font-size: 0.64rem;
      font-weight: 700;
      padding: 1px 2px 0;
    }

    .agenda-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.82fr);
      gap: 12px;
      align-items: start;
    }

    .agenda-calendar-pane,
    .agenda-side-pane,
    .agenda-form-shell {
      display: grid;
      gap: 10px;
    }

    .agenda-side-pane,
    .agenda-form-shell {
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 12px;
      background: var(--appa-card-subtle);
    }

    .agenda-lista {
      display: grid;
      gap: 8px;
    }

    .agenda-upcoming-item {
      border: 1px solid var(--appa-line);
      border-radius: 12px;
      padding: 8px 9px;
      background: var(--appa-card-bg);
    }

    .agenda-upcoming-title {
      color: var(--appa-ink);
      font-size: 0.82rem;
      font-weight: 800;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }

    .agenda-upcoming-meta {
      color: var(--appa-muted);
      font-size: 0.71rem;
      line-height: 1.3;
    }

    .agenda-form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .agenda-form-shell .q-field__native,
    .agenda-form-shell .q-field__input,
    .agenda-form-shell .q-field__label {
      font-size: 0.85rem;
    }

    .agenda-form-shell .q-field--outlined .q-field__control {
      min-height: 42px;
    }

    .calendar-error {
      border: 1px solid #fecaca;
      border-radius: 12px;
      padding: 9px 11px;
      color: #fecdd3;
      background: rgba(127, 29, 29, 0.32);
      font-size: 0.78rem;
    }

    .q-field--outlined .q-field__control {
      border-radius: 12px;
      background: var(--appa-input-bg);
      color: var(--appa-ink);
    }

    .q-field--outlined .q-field__control::before {
      border-color: var(--appa-line);
    }

    .q-field--focused .q-field__control::after {
      border-color: var(--appa-accent);
    }

    .q-field__native,
    .q-field__prefix,
    .q-field__suffix,
    .q-field__input,
    .q-field__label,
    .q-toggle__label {
      color: var(--appa-ink);
    }

    .q-btn {
      border-radius: 12px;
      font-weight: 700;
      text-transform: none;
    }

    .refresh-button {
      background: var(--appa-accent) !important;
      color: var(--appa-button-ink) !important;
      padding-left: 14px;
      padding-right: 14px;
      box-shadow: none;
    }

    .interest-list {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .interest-chip {
      border: 1px solid rgba(34, 211, 238, 0.22);
      border-radius: 999px;
      padding: 5px 9px;
      background: rgba(34, 211, 238, 0.10);
      color: var(--appa-ink);
      font-size: 0.78rem;
      font-weight: 700;
    }

    .news-live-count {
      color: var(--appa-ink);
      font-size: 0.9rem;
      font-weight: 800;
    }

    .ghost-button {
      color: var(--appa-ink) !important;
      border: 1px solid var(--appa-line);
      background: var(--appa-card-subtle) !important;
    }

    .news-stream-shell {
      width: 100%;
      margin-top: 12px;
    }

    .news-stream {
      display: flex;
      gap: 12px;
      min-height: 252px;
      overflow-x: auto;
      overflow-y: hidden;
      padding: 4px 4px 14px;
      scroll-behavior: smooth;
      scroll-snap-type: x mandatory;
      scrollbar-color: rgba(34, 211, 238, 0.52) rgba(15, 23, 42, 0.72);
      scrollbar-width: thin;
    }

    .news-card {
      position: relative;
      flex: 0 0 min(360px, 84vw);
      min-height: 232px;
      display: grid;
      grid-template-rows: auto 1fr auto auto auto;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--appa-line);
      border-top: 3px solid var(--news-color, var(--appa-accent));
      border-radius: 12px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.045), transparent),
        var(--appa-card-bg);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);
      scroll-snap-align: start;
      transition:
        border-color 180ms ease,
        box-shadow 180ms ease,
        opacity 180ms ease,
        transform 180ms ease;
    }

    .news-card.is-active {
      border-color: var(--news-color, var(--appa-accent));
      box-shadow:
        var(--appa-shadow),
        0 0 0 1px color-mix(in srgb, var(--news-color, var(--appa-accent)) 22%, transparent);
      transform: translateY(-2px);
    }

    .news-card.is-read {
      display: none;
    }

    .news-card-top {
      min-height: 28px;
    }

    .news-chip {
      display: inline-flex;
      align-items: center;
      max-width: 74%;
      border: 1px solid color-mix(in srgb, var(--news-color, var(--appa-accent)) 42%, transparent);
      border-radius: 999px;
      padding: 4px 8px;
      background: color-mix(in srgb, var(--news-color, var(--appa-accent)) 13%, transparent);
      color: var(--appa-ink);
      font-size: 0.72rem;
      font-weight: 850;
      line-height: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .news-index {
      color: color-mix(in srgb, var(--news-color, var(--appa-accent)) 72%, white);
      font-size: 0.75rem;
      font-weight: 850;
    }

    .news-title {
      display: block;
      color: var(--appa-ink);
      font-size: 1.02rem;
      font-weight: 820;
      line-height: 1.32;
      text-decoration: none;
      overflow-wrap: anywhere;
    }

    .news-title:hover,
    .news-open:hover,
    .headline-link:hover,
    .calendar-event:hover {
      color: var(--appa-accent);
    }

    .news-source {
      color: var(--appa-muted);
      font-size: 0.78rem;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .news-time {
      color: color-mix(in srgb, var(--news-color, var(--appa-accent)) 70%, white);
      font-size: 0.76rem;
      font-weight: 750;
    }

    .news-card-actions {
      min-height: 34px;
    }

    .news-open {
      color: var(--appa-ink);
      font-size: 0.75rem;
      font-weight: 800;
      text-decoration: none;
    }

    .news-card .q-btn {
      color: var(--news-color, var(--appa-accent)) !important;
    }

    .news-empty {
      flex: 1 0 100%;
      min-height: 150px;
      display: grid;
      place-items: center;
      align-content: center;
      gap: 6px;
      border: 1px dashed var(--appa-line);
      border-radius: 12px;
      color: var(--appa-muted);
      background: var(--appa-empty);
      text-align: center;
    }

    .news-empty strong {
      color: var(--appa-ink);
      font-size: 0.98rem;
    }

    .news-action-button {
      min-width: 34px;
      min-height: 30px;
    }

    html[data-density="compact"] .dashboard-shell {
      padding: 8px 12px 16px;
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
      min-height: 40px;
      padding: 7px 11px;
    }

    html[data-density="compact"] .expansion-shell .q-expansion-item__content > div {
      padding: 9px 11px;
    }

    html[data-density="compact"] .weather-temp {
      font-size: 2.45rem;
    }

    

    .stat-grid-modern {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
    }

    html[data-density="compact"] .weather-day {
      min-height: 128px;
      padding: 8px;
    }

    html[data-density="compact"] .calendar-cell {
      min-height: 60px;
      padding: 5px;
    }

    html[data-density="compact"] .news-stream {
      min-height: 212px;
    }

    html[data-density="compact"] .news-card {
      flex-basis: min(320px, 82vw);
      min-height: 196px;
      gap: 8px;
      padding: 11px;
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

      .agenda-layout {
        grid-template-columns: 1fr;
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
      .stat-grid {
        grid-template-columns: 1fr;
      }

      .weather-week {
        grid-template-columns: repeat(7, minmax(118px, 1fr));
        overflow-x: auto;
      }

      .news-card {
        flex-basis: min(328px, 88vw);
      }

      .calendar-grid {
        overflow-x: auto;
        grid-template-columns: repeat(7, minmax(120px, 1fr));
      }

      .agenda-form-grid {
        grid-template-columns: 1fr;
      }
    }
    """


def _dashboard_js() -> str:
    """Fornece microinteracoes visuais sem controlar dados de negocio no navegador."""
    return """
    (function () {
      const appa = window.APPA_DASHBOARD = window.APPA_DASHBOARD || {};
      appa.currentDensity = appa.currentDensity || 'comfortable';
      appa.currentTheme = appa.currentTheme || 'dark';

      appa.applyDensityControls = function () {
        document.querySelectorAll('[data-density-choice]').forEach(function (button) {
          const active = button.dataset.densityChoice === appa.currentDensity;
          button.classList.toggle('is-active', active);
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
      };

      appa.applyThemeControls = function () {
        document.querySelectorAll('[data-theme-choice]').forEach(function (button) {
          const active = button.dataset.themeChoice === appa.currentTheme;
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

      appa.setTheme = function (mode) {
        const chosen = mode === 'light' ? 'light' : 'dark';
        appa.currentTheme = chosen;
      document.documentElement.dataset.theme = chosen;
      try { localStorage.setItem('appa-dashboard-theme', chosen); } catch (error) {}
      appa.applyThemeControls();
      };

      

      

      

      if (!appa.densityClickHandler) {
        appa.densityClickHandler = function (event) {
          const button = event.target.closest('[data-density-choice]');
          if (!button) return;
          appa.setDensity(button.dataset.densityChoice);
        };
        document.addEventListener('click', appa.densityClickHandler);
      }

      if (!appa.themeClickHandler) {
        appa.themeClickHandler = function (event) {
          const button = event.target.closest('[data-theme-choice]');
          if (!button) return;
          appa.setTheme(button.dataset.themeChoice);
        };
        document.addEventListener('click', appa.themeClickHandler);
      }

      ;
        document.addEventListener('click', appa.viewClickHandler);
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

      appa.newsReadKey = 'appa-news-read-v2';

      appa.readNewsIds = function () {
        try {
          return new Set(JSON.parse(localStorage.getItem(appa.newsReadKey) || '[]'));
        } catch (error) {
          return new Set();
        }
      };

      appa.writeNewsIds = function (ids) {
        try {
          localStorage.setItem(appa.newsReadKey, JSON.stringify(Array.from(ids)));
        } catch (error) {}
      };

      appa.scrollNewsCard = function (stream, card) {
        const streamBox = stream.getBoundingClientRect();
        const cardBox = card.getBoundingClientRect();
        const margin = 14;
        if (cardBox.left >= streamBox.left + margin && cardBox.right <= streamBox.right - margin) {
          return;
        }
        const delta = cardBox.left - streamBox.left - margin;
        stream.scrollTo({
          left: stream.scrollLeft + delta,
          behavior: 'smooth'
        });
      };

      appa.refreshNewsStream = function (stream) {
        const readIds = appa.readNewsIds();
        const cards = Array.from(stream.querySelectorAll('[data-news-card]'));
        const empty = stream.querySelector('[data-news-empty]');
        cards.forEach(function (card) {
          card.classList.toggle('is-read', readIds.has(card.dataset.newsId));
        });
        const unread = cards.filter(function (card) {
          return !card.classList.contains('is-read');
        });
        if (empty) empty.hidden = unread.length > 0;
        if (!unread.length) return;
        if (!unread.some(function (card) { return card.classList.contains('is-active'); })) {
          unread[0].classList.add('is-active');
          appa.scrollNewsCard(stream, unread[0]);
        }
      };

      appa.advanceNewsStream = function (stream) {
        if (!document.body.contains(stream)) return false;
        const cards = Array.from(stream.querySelectorAll('[data-news-card]:not(.is-read)'));
        if (!cards.length) {
          appa.refreshNewsStream(stream);
          return true;
        }
        const current = cards.findIndex(function (card) {
          return card.classList.contains('is-active');
        });
        const nextIndex = current < 0 ? 0 : (current + 1) % cards.length;
        stream.querySelectorAll('[data-news-card]').forEach(function (card) {
          card.classList.remove('is-active');
        });
        cards[nextIndex].classList.add('is-active');
        appa.scrollNewsCard(stream, cards[nextIndex]);
        return true;
      };

      appa.mountNewsStreams = function () {
        document.querySelectorAll('[data-news-stream]').forEach(function (stream) {
          if (!stream.dataset.newsMounted) {
            stream.dataset.newsMounted = 'true';
            stream.addEventListener('click', function (event) {
              const link = event.target.closest('[data-news-link]');
              if (!link) return;
              const card = link.closest('[data-news-card]');
              if (!card) return;
              const readIds = appa.readNewsIds();
              readIds.add(card.dataset.newsId);
              appa.writeNewsIds(readIds);
              card.classList.add('is-read');
              window.setTimeout(function () {
                appa.refreshNewsStream(stream);
                appa.advanceNewsStream(stream);
              }, 180);
            });
            const timer = window.setInterval(function () {
              if (!appa.advanceNewsStream(stream)) window.clearInterval(timer);
            }, 6500);
          }
          appa.refreshNewsStream(stream);
        });
      };

      appa.clearReadNews = function () {
        try { localStorage.removeItem(appa.newsReadKey); } catch (error) {}
        document.querySelectorAll('[data-news-card]').forEach(function (card) {
          card.classList.remove('is-read');
        });
        document.querySelectorAll('[data-news-stream]').forEach(appa.refreshNewsStream);
      };

      appa.boot = function () {
        document.body.classList.add('appa-dashboard');
        let stored = document.documentElement.dataset.density || 'comfortable';
        try { stored = localStorage.getItem('appa-dashboard-density') || stored; }
        catch (error) {}
        appa.setDensity(stored);
        let storedTheme = document.documentElement.dataset.theme || 'dark';
        try { storedTheme = localStorage.getItem('appa-dashboard-theme') || storedTheme; }
        catch (error) {}
        appa.setTheme(storedTheme);

        appa.tick();
        appa.mountNewsStreams();
        if (!appa.clockTimer) {
          appa.clockTimer = window.setInterval(appa.tick, 30000);
        }
        if (!appa.observer && document.body) {
          appa.observer = new MutationObserver(function () {
            window.requestAnimationFrame(function () {
              appa.applyDensityControls();
              appa.applyThemeControls();
              
              appa.tick();
              appa.mountNewsStreams();
            });
          });
          appa.observer.observe(document.body, { childList: true, subtree: true });
        }
      };

      document.addEventListener('DOMContentLoaded', appa.boot);
      window.setTimeout(appa.boot, 250);
    })();
    """


def _criar_grafico_clima(resumo: list[ResumoClimaDia]):
    dias = [_rotulo_dia_curto(d) for d in resumo]
    maximas = [d.maxima for d in resumo]
    minimas = [d.minima for d in resumo]
    return ui.echart(
        {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Max", "Min"], "textStyle": {"color": "#9fb2c7"}},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "data": dias, "axisLabel": {"color": "#9fb2c7"}},
            "yAxis": {
                "type": "value",
                "axisLabel": {"color": "#9fb2c7"},
                "splitLine": {"lineStyle": {"color": "#1e293b"}},
            },
            "series": [
                {
                    "name": "Max",
                    "type": "line",
                    "data": maximas,
                    "itemStyle": {"color": "#fbbf24"},
                    "smooth": True,
                },
                {
                    "name": "Min",
                    "type": "line",
                    "data": minimas,
                    "itemStyle": {"color": "#60a5fa"},
                    "smooth": True,
                },
            ],
        }
    ).classes("chart-weather w-full h-64")


def _atualizar_grafico_clima(chart, resumo: list[ResumoClimaDia]):
    dias = [_rotulo_dia_curto(d) for d in resumo]
    maximas = [d.maxima for d in resumo]
    minimas = [d.minima for d in resumo]
    chart.options["xAxis"]["data"] = dias
    chart.options["series"][0]["data"] = maximas
    chart.options["series"][1]["data"] = minimas
    chart.update()


def _criar_grafico_noticias(grupos: dict[str, int]):
    data = [{"value": v, "name": GRUPOS_LABEL.get(k, k.title())} for k, v in grupos.items()]
    return ui.echart(
        {
            "tooltip": {"trigger": "item"},
            "legend": {"top": "5%", "left": "center", "textStyle": {"color": "#9fb2c7"}},
            "series": [
                {
                    "name": "Notícias",
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "avoidLabelOverlap": False,
                    "itemStyle": {"borderRadius": 5, "borderColor": "#060914", "borderWidth": 2},
                    "label": {"show": False, "position": "center"},
                    "emphasis": {"label": {"show": True, "fontSize": 16, "fontWeight": "bold"}},
                    "labelLine": {"show": False},
                    "data": data,
                }
            ],
        }
    ).classes("chart-news w-full h-64")


def _atualizar_grafico_noticias(chart, grupos: dict[str, int]):
    data = [{"value": v, "name": GRUPOS_LABEL.get(k, k.title())} for k, v in grupos.items()]
    chart.options["series"][0]["data"] = data
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


def construir_dashboard(
    servico: DashboardService,
    snapshot_inicial: DashboardSnapshot | None = None,
) -> None:
    """Constroi um dashboard denso, visual e voltado a acompanhamento diario."""
    _registrar_assets_dashboard()
    _executar_javascript("document.documentElement.dataset.density = 'compact';")
    with ui.column().classes("dashboard-shell gap-3 w-full max-w-[1600px]"):
        _cabecalho(snapshot_inicial)
        with ui.row().classes("commandbar items-center gap-3 w-full"):
            ui.html(
                """
                <div class="commandbar-note">
                  <span class="status-dot"></span>
                  <span>Atualização local ativa</span>
                </div>
                """
            )
            ui.button(
                "Atualizar Painel",
                icon="refresh",
                on_click=lambda: atualizar(),
            ).classes("refresh-button")
            ui.html(
                """

                <div class="theme-toggle" aria-label="Tema do painel">
                  <button type="button" data-theme-choice="light">
                    <span class="material-icons appa-seg-icon">light_mode</span>
                    Claro
                  </button>
                  <button type="button" data-theme-choice="dark">
                    <span class="material-icons appa-seg-icon">dark_mode</span>
                    Escuro
                  </button>
                </div>
                """
            )
            status = ui.label("Painel pronto.").classes("dashboard-status ml-auto")

        with ui.tabs().classes("w-full") as tabs:
            tab_visao_geral = ui.tab("Visão Geral", icon="dashboard")
            tab_noticias = ui.tab("Explorador de Notícias", icon="analytics")
            tab_agenda = ui.tab("Agenda e Eventos", icon="calendar_month")
            tab_interesses = ui.tab("Configurações", icon="settings")

        with ui.tab_panels(tabs, value=tab_visao_geral).classes("w-full bg-transparent p-0"):
            with ui.tab_panel(tab_visao_geral).classes("p-0 gap-3 flex flex-col"):
                kpi_cards = _criar_kpis(snapshot_inicial)
                with ui.grid(columns=6).classes("kpi-grid w-full gap-3"):
                    for card in kpi_cards:
                        with ui.element("div").classes("kpi"):
                            with ui.element("div").classes("kpi-label"):
                                ui.icon(card["icon"]).classes("kpi-icon")
                                ui.label(card["label"])
                            valor = ui.label(card["value"]).classes("kpi-value")
                            detalhe = ui.label(card["detail"]).classes("kpi-detail text-xs")
                            card["widgets"] = (valor, detalhe)

                with ui.grid(columns=2).classes("overview-charts-grid w-full gap-3"):
                    with ui.element("div").classes("expansion-shell panel-week p-3"):
                        ui.label("Previsão da Semana").classes("section-title mb-2")
                        grafico_clima = _criar_grafico_clima(
                            snapshot_inicial.resumo_semana if snapshot_inicial else []
                        )

                    with ui.element("div").classes("expansion-shell panel-news-distribution p-3"):
                        ui.label("Distribuição de Notícias").classes("section-title mb-2")
                        grafico_noticias = _criar_grafico_noticias(
                            snapshot_inicial.noticias_por_grupo if snapshot_inicial else {}
                        )

                with ui.grid(columns=2).classes("overview-local-grid w-full gap-3"):
                    with ui.element("div").classes("expansion-shell panel-local p-3"):
                        ui.label("Santa Maria em Foco").classes("section-title mb-2")
                        santa_maria_cards = ui.column().classes("w-full gap-2")
                        _popular_santa_maria_em_foco(
                            santa_maria_cards,
                            snapshot_inicial.santa_maria_em_foco if snapshot_inicial else [],
                            servico.config.localizacao.timezone,
                            servico,
                            status,
                        )

                    with ui.element("div").classes("expansion-shell panel-weather p-3"):
                        ui.label("Clima Atual").classes("section-title mb-2")
                        clima_resumo = _render_clima_resumo(snapshot_inicial)

            with ui.tab_panel(tab_noticias).classes("p-0 gap-3 flex flex-col"):
                with ui.element("div").classes(
                    "expansion-shell p-3 w-full h-[600px] flex flex-col"
                ):
                    with ui.row().classes("w-full items-center justify-between mb-2"):
                        ui.label("Explorador de Notícias").classes("section-title")
                        noticias_total = ui.label("").classes("news-live-count text-sm")

                    renderer_link = (
                        "(params) => "
                        '`<a href="${params.value}" target="_blank" '
                        'style="color: #22d3ee; text-decoration: underline;">Abrir</a>`'
                    )
                    tabela_noticias = ui.aggrid(
                        {
                            "columnDefs": [
                                {
                                    "headerName": "Grupo",
                                    "field": "grupo",
                                    "sortable": True,
                                    "filter": True,
                                    "width": 130,
                                },
                                {
                                    "headerName": "Fonte",
                                    "field": "fonte",
                                    "sortable": True,
                                    "filter": True,
                                    "width": 130,
                                },
                                {
                                    "headerName": "Título",
                                    "field": "titulo",
                                    "sortable": True,
                                    "filter": True,
                                    "flex": 1,
                                },
                                {
                                    "headerName": "Publicado",
                                    "field": "publicado",
                                    "sortable": True,
                                    "filter": True,
                                    "width": 150,
                                },
                                {
                                    "headerName": "Link",
                                    "field": "link",
                                    "cellRenderer": renderer_link,
                                    "width": 90,
                                },
                            ],
                            "rowData": _linhas_noticias_aggrid(
                                _noticias_sem_santa_maria(snapshot_inicial.noticias)
                                if snapshot_inicial
                                else [],
                                servico.config.localizacao.timezone,
                            ),
                            "rowSelection": "single",
                            "defaultColDef": {"resizable": True},
                        }
                    ).classes("w-full flex-grow ag-theme-balham-dark")

            with ui.tab_panel(tab_agenda).classes("p-0 gap-3 flex flex-col"):
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

            with ui.tab_panel(tab_interesses).classes("p-0 gap-3 flex flex-col"):
                with ui.grid(columns=2).classes("w-full gap-3"):
                    with ui.element("div").classes("expansion-shell p-3"):
                        ui.label("Aparência e Comportamento").classes("section-title mb-2")
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
                        ui.label("Visual do Painel").classes(
                            "text-xs font-semibold text-slate-500 mb-1"
                        )
                        ui.html(
                            """

                            <div class="theme-toggle" aria-label="Tema do painel">
                              <button type="button" data-theme-choice="light">
                                <span class="material-icons appa-seg-icon">light_mode</span>
                                Claro
                              </button>
                              <button type="button" data-theme-choice="dark">
                                <span class="material-icons appa-seg-icon">dark_mode</span>
                                Escuro
                              </button>
                            </div>
                            """
                        )

                    with ui.element("div").classes("expansion-shell p-3"):
                        ui.label("Interesses de Pesquisa").classes("section-title mb-2")
                        interesses_container = ui.element("div").classes("interest-list")
                        _popular_interesses(
                            interesses_container,
                            servico.config.fontes.noticias.interesses_busca,
                        )
                        interesse_texto = ui.textarea("Adicionar interesses (vírgula)").classes(
                            "w-full mt-3"
                        )
                        interesse_texto.props("rows=3")
                        interesses_status = ui.label("").classes("text-sm text-slate-500")
                        ui.button(
                            "Salvar interesses",
                            icon="save",
                            on_click=lambda: (
                                _adicionar_interesses_gui(
                                    servico,
                                    interesse_texto,
                                    interesses_container,
                                    interesses_status,
                                    status,
                                )
                                and atualizar()
                            ),
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
            tabela_noticias.options["rowData"] = _linhas_noticias_aggrid(
                novas_noticias, servico.config.localizacao.timezone
            )
            tabela_noticias.update()

            noticias_total.text = (
                f"{_resumo_feed_noticias(novas_noticias)} | atualizado {snapshot.atualizado_em}"
            )
            _popular_agenda_google(
                calendario_google,
                google_lista,
                agenda_erro,
                agenda_mes_titulo,
                snapshot.agenda_google_resultado,
                servico.config.localizacao.timezone,
            )
            _executar_javascript(
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
                "icon": "article",
                "label": "Noticias no radar",
                "value": str(snapshot.indicadores.total_noticias),
                "detail": "Itens do dia atual carregados no painel",
            },
            {
                "icon": "newspaper",
                "label": "The News em destaque",
                "value": str(snapshot.indicadores.noticias_the_news),
                "detail": "Artigos do grupo prioritario",
            },
            {
                "icon": "location_on",
                "label": "Santa Maria hoje",
                "value": str(snapshot.indicadores.noticias_santa_maria),
                "detail": "Cobertura local disponivel hoje",
            },
            {
                "icon": "thermostat",
                "label": "Temperatura alvo",
                "value": f"{previsao.maxima or '--'} C",
                "detail": (f"Minima {previsao.minima or '--'} C | Chuva {previsao.chuva or '--'}%"),
            },
            {
                "icon": "event",
                "label": "Google Agenda",
                "value": str(snapshot.indicadores.eventos_google),
                "detail": "Eventos futuros sincronizados",
            },
            {
                "icon": "payments",
                "label": "Dolar agora",
                "value": _formatar_dolar(snapshot),
                "detail": _detalhe_dolar(snapshot),
            },
        ]
    return [
        {"icon": "article", "label": "Noticias no radar", "value": "0", "detail": "Sem dados"},
        {"icon": "newspaper", "label": "The News em destaque", "value": "0", "detail": "Sem dados"},
        {"icon": "location_on", "label": "Santa Maria hoje", "value": "0", "detail": "Sem dados"},
        {"icon": "thermostat", "label": "Temperatura alvo", "value": "--", "detail": "Sem dados"},
        {"icon": "event", "label": "Google Agenda", "value": "0", "detail": "Sem dados"},
        {"icon": "payments", "label": "Dolar agora", "value": "--", "detail": "Sem dados"},
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
    """Constroi o resumo visual de clima em estilo limpo e compacto."""
    with ui.element("div").classes("weather-now w-full h-full flex flex-col justify-center"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                cidade = ui.label(snapshot.previsao.cidade if snapshot else "Sem dados").classes(
                    "text-lg font-bold text-neon tracking-wide"
                )
                data = ui.label(
                    snapshot.previsao.data_alvo.isoformat() if snapshot else "--"
                ).classes("text-xs text-slate-400")
            referencia = ui.label(
                _rotulo_referencia_clima(snapshot.previsao) if snapshot else "Sem referencia"
            ).classes("climate-pill")

        with ui.row().classes("w-full items-center gap-4 mt-2"):
            temperatura = ui.label(
                _formatar_grau(snapshot.previsao.temperatura_referencia) if snapshot else "--"
            ).classes("weather-temp")
            with ui.column().classes("gap-0"):
                texto_sensacao = (
                    _formatar_grau(snapshot.previsao.sensacao)
                    if snapshot and snapshot.previsao.sensacao
                    else "--"
                )
                sensacao = ui.label(f"Sensação: {texto_sensacao}").classes("text-xs text-slate-400")
                ui.label("Condição atual").classes("text-xs text-slate-300 font-medium")

        with ui.element("div").classes("stat-grid-modern"):
            maxima = _stat_box_modern(
                "Máx",
                _formatar_grau(snapshot.previsao.maxima) if snapshot else "--",
                "mdi-arrow-up text-rose-400",
            )
            minima = _stat_box_modern(
                "Mín",
                _formatar_grau(snapshot.previsao.minima) if snapshot else "--",
                "mdi-arrow-down text-blue-400",
            )
            chuva = _stat_box_modern(
                "Chuva",
                _formatar_chuva(snapshot.previsao.chuva) if snapshot else "--",
                "mdi-water-percent text-cyan-400",
            )
            uv = _stat_box_modern(
                "UV Max",
                str(snapshot.previsao.uv_max) if snapshot and snapshot.previsao.uv_max else "--",
                "mdi-white-balance-sunny text-amber-400",
            )
            umidade = _stat_box_modern(
                "Umidade",
                f"{snapshot.previsao.umidade}%" if snapshot and snapshot.previsao.umidade else "--",
                "mdi-water text-blue-300",
                detalhado=True,
            )
            vento = _stat_box_modern(
                "Vento",
                f"{snapshot.previsao.vento}km/h" if snapshot and snapshot.previsao.vento else "--",
                "mdi-weather-windy text-slate-300",
                detalhado=True,
            )
            nascer = _stat_box_modern(
                "Nascer",
                snapshot.previsao.nascer_sol if snapshot and snapshot.previsao.nascer_sol else "--",
                "mdi-weather-sunset-up text-orange-400",
                detalhado=True,
            )
            por = _stat_box_modern(
                "Pôr",
                snapshot.previsao.por_sol if snapshot and snapshot.previsao.por_sol else "--",
                "mdi-weather-sunset-down text-purple-400",
                detalhado=True,
            )

    return {
        "cidade": cidade,
        "data": data,
        "referencia": referencia,
        "temperatura": temperatura,
        "sensacao": sensacao,
        "maxima": maxima,
        "minima": minima,
        "chuva": chuva,
        "uv": uv,
        "umidade": umidade,
        "vento": vento,
        "nascer": nascer,
        "por": por,
    }


def _stat_box_modern(
    rotulo: str,
    valor: str,
    icone: str,
    detalhado: bool = False,
) -> ui.label:
    """Cria uma mini caixa numerica para os blocos de clima, mais minimalista."""
    classes = "stat-box flex flex-col items-center justify-center p-2"
    if detalhado:
        classes += " detail-metric"
    with ui.element("div").classes(classes):
        ui.icon(icone.split(" ")[0]).classes(f"text-[13px] mb-1 {icone.split(' ')[1]}")
        texto = ui.label(valor).classes("text-sm font-bold text-slate-200")
        ui.label(rotulo).classes("text-[9px] uppercase tracking-wider text-slate-500 mt-1")
    return texto


def _atualizar_clima_resumo(widgets: dict[str, ui.element], snapshot: DashboardSnapshot) -> None:
    """Atualiza o bloco principal de clima."""
    previsao = snapshot.previsao
    widgets["cidade"].text = previsao.cidade
    widgets["data"].text = previsao.data_alvo.isoformat()
    widgets["referencia"].text = _rotulo_referencia_clima(previsao)
    widgets["temperatura"].text = _formatar_grau(previsao.temperatura_referencia)
    widgets[
        "sensacao"
    ].text = f"Sensação: {_formatar_grau(previsao.sensacao) if previsao.sensacao else '--'}"
    widgets["maxima"].text = _formatar_grau(previsao.maxima)
    widgets["minima"].text = _formatar_grau(previsao.minima)
    widgets["chuva"].text = _formatar_chuva(previsao.chuva)
    widgets["uv"].text = str(previsao.uv_max) if previsao.uv_max else "--"
    widgets["umidade"].text = f"{previsao.umidade}%" if previsao.umidade else "--"
    widgets["vento"].text = f"{previsao.vento}km/h" if previsao.vento else "--"
    widgets["nascer"].text = previsao.nascer_sol if previsao.nascer_sol else "--"
    widgets["por"].text = previsao.por_sol if previsao.por_sol else "--"


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


def _resumo_feed_noticias(noticias: list[Noticia]) -> str:
    """Resume o volume do feed dinamico por grupo principal."""
    total = len(noticias)
    the_news = len(_noticias_por_grupo(noticias, "the_news"))
    interesses = len(_noticias_por_grupo(noticias, "interesses"))
    return f"{total} no feed | {the_news} The News | {interesses} interesses"


def _popular_feed_dinamico(
    container: ui.element,
    noticias: list[Noticia],
    timezone: str,
    servico: DashboardService,
    status_label,
) -> None:
    """Renderiza um fluxo horizontal que alterna noticias ainda nao clicadas."""
    container.clear()
    with container:
        with ui.element("div").classes("news-stream").props("data-news-stream"):
            if not noticias:
                ui.html(
                    """
                    <div class="news-empty" data-news-empty>
                      <strong>Sem sinal agora</strong>
                      <span>--</span>
                    </div>
                    """
                )
                return
            for indice, noticia in enumerate(noticias, start=1):
                _renderizar_card_noticia(
                    noticia,
                    indice,
                    timezone,
                    servico,
                    status_label,
                )
            ui.html(
                """
                <div class="news-empty" data-news-empty hidden>
                  <strong>Tudo lido por enquanto</strong>
                  <span>aguardando a proxima rodada</span>
                </div>
                """
            )
    _executar_javascript("window.APPA_DASHBOARD && window.APPA_DASHBOARD.mountNewsStreams();")


def _renderizar_card_noticia(
    noticia: Noticia,
    indice: int,
    timezone: str,
    servico: DashboardService,
    status_label,
) -> None:
    """Cria um card de noticia clicavel e rastreavel pelo front-end."""
    card_id = _noticia_dom_id(noticia)
    grupo = GRUPOS_LABEL.get(noticia.grupo, noticia.grupo.replace("_", " ").title())
    cor = GRUPOS_COR.get(noticia.grupo, "#5bd8ff")
    link = _link_seguro(noticia.link)
    with (
        ui.element("article")
        .classes("news-card")
        .props(f'data-news-card data-news-id="{card_id}"')
        .style(f"--news-color: {cor};")
    ):
        with ui.row().classes("news-card-top items-center justify-between"):
            ui.label(grupo).classes("news-chip")
            ui.label(f"#{indice:02d}").classes("news-index")
        ui.link(
            texto_terminal_seguro(noticia.titulo),
            link,
            new_tab=True,
        ).classes("news-title").props("data-news-link").on(
            "click",
            lambda _evento, noticia=noticia: _salvar_noticia_observada(
                servico,
                noticia,
                status_label,
            ),
        )
        ui.label(texto_terminal_seguro(noticia.fonte)).classes("news-source")
        ui.label(
            texto_terminal_seguro(rotulo_tempo_publicacao(noticia, timezone=timezone))
        ).classes("news-time")
        with ui.row().classes("news-card-actions items-center justify-between"):
            ui.link("Abrir", link, new_tab=True).classes("news-open").props("data-news-link")
            ui.button(
                icon="bookmark_add",
                on_click=lambda noticia=noticia: _salvar_noticia_observada(
                    servico,
                    noticia,
                    status_label,
                ),
            ).props("flat round dense title=Salvar")


def _noticia_dom_id(noticia: Noticia) -> str:
    """Gera um identificador estavel para marcar noticias ja clicadas."""
    base = noticia.link or f"{noticia.fonte}:{noticia.titulo}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


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
    """Atualiza a lista curta de artefatos recentes do banco."""
    container.clear()
    if not notas:
        with container:
            ui.label("Nenhuma nota recente encontrada.").classes("text-sm text-slate-500")
        return
    with container:
        for nota in notas[:6]:
            with ui.element("div").classes("stat-box"):
                ui.label("Banco").classes("text-[11px] uppercase text-slate-400")
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
) -> bool:
    """Valida e salva interesses informados no painel."""
    texto = str(campo_interesses.value or "")
    if not texto.strip():
        status_label.text = "Digite ao menos um interesse."
        return False
    try:
        interesses = servico.adicionar_interesses(texto)
    except Exception as exc:  # pragma: no cover
        status_label.text = f"Falha ao salvar interesses: {exc}"
        painel_status.text = status_label.text
        return False
    campo_interesses.value = ""
    _popular_interesses(interesses_container, interesses)
    status_label.text = "Interesses salvos. Buscando noticias relacionadas..."
    painel_status.text = "Interesses atualizados; atualizando o feed."
    return True


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
    status_label.text = f"Noticia salva no banco em {caminho}."
    ui.notify("Noticia salva no banco.", type="positive")


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
    eventos_lista = [
        evento for evento in resultado.eventos if evento_google_ainda_futuro(evento, timezone)
    ]
    if not eventos_lista:
        with lista_container:
            ui.label("Nenhum evento futuro encontrado para este mes.").classes(
                "text-sm text-slate-500"
            )
        return
    with lista_container:
        ui.label("Proximos eventos do mes").classes("section-title")
        with ui.element("div").classes("agenda-lista"):
            for evento in eventos_lista[:8]:
                with ui.element("div").classes("agenda-upcoming-item"):
                    ui.label(evento.titulo).classes("agenda-upcoming-title")
                    ui.label(formatar_data_hora_google(evento.inicio, timezone)).classes(
                        "agenda-upcoming-meta"
                    )
                    if evento.local:
                        ui.label(evento.local).classes("agenda-upcoming-meta")


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
                        eventos_dia = eventos_por_dia.get(dia, [])
                        if eventos_dia:
                            with ui.element("div").classes("calendar-events"):
                                for evento in eventos_dia[:3]:
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
                                        '<span class="calendar-event-time">'
                                        f"{escape(prefixo)}"
                                        "</span>"
                                        '<span class="calendar-event-title">'
                                        f"{escape(titulo)}"
                                        "</span>"
                                        "</a>"
                                    )
                                if len(eventos_dia) > 3:
                                    ui.label(f"+{len(eventos_dia) - 3} outros").classes(
                                        "calendar-more"
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
    status_label.text = "Nota criada no banco."


def _salvar_documento(funcao_salvar, conteudo: str, caminho_label, status_label) -> None:
    """Persiste um documento fixo da GUI e atualiza os avisos ao usuario."""
    caminho = funcao_salvar(conteudo.strip())
    caminho_label.text = f"Arquivo salvo em {caminho}"
    status_label.text = "Documento salvo no banco."
