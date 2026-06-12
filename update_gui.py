import re
from pathlib import Path

gui_path = Path("d:/milla/OneDrive/Documentos/Assistente de IA pessoal/src/assistente_pessoal/gui.py")
content = gui_path.read_text(encoding="utf-8")

# 1. Update CSS to be even smaller, minimalist and futuristic glassmorphism
old_css_part = r"""    :root \{
      --appa-bg: #060914;"""
new_css_part = """    :root {
      --appa-bg: #03050a; /* Darker, more futuristic */
      --appa-panel: rgba(16, 23, 39, 0.4); /* Glass effect */
      --appa-panel-soft: rgba(21, 31, 49, 0.3);
      --appa-panel-strong: rgba(11, 16, 32, 0.6);
      --appa-ink: #edf7ff;
      --appa-muted: #7b8eab;
      --appa-line: rgba(143, 164, 196, 0.15);
      --appa-accent: #00f0ff; /* Neon cyan */
      --appa-blue: #3b82f6;
      --appa-green: #10b981;
      --appa-amber: #f59e0b;
      --appa-rose: #f43f5e;
      --appa-magenta: #d946ef;
      --appa-shadow: 0 8px 32px rgba(0, 240, 255, 0.05); /* Soft neon glow */
      --appa-cell: rgba(11, 16, 32, 0.5);
      --appa-command: rgba(3, 5, 10, 0.8);
      --appa-card-bg: rgba(12, 18, 34, 0.4);
      --appa-card-subtle: rgba(21, 31, 49, 0.3);
      --appa-empty: rgba(11, 16, 32, 0.3);
      --appa-input-bg: rgba(8, 13, 26, 0.5);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }
    .weather-now {
      background: linear-gradient(135deg, rgba(16,23,39,0.7) 0%, rgba(3,5,10,0.8) 100%);
      border: 1px solid rgba(0, 240, 255, 0.2);
      box-shadow: 0 0 20px rgba(0, 240, 255, 0.05);
      backdrop-filter: blur(16px);
      border-radius: 12px;
      padding: 16px;
    }
    .stat-box {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
    }
    .stat-grid-modern {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .text-neon {
      color: var(--appa-accent);
      text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
    }"""
content = re.sub(r"    :root \{\n      --appa-bg: #060914;", new_css_part, content)

css_replacements = [
    (r"font-size: 13px;", r"font-size: 12px;"),
    (r"font-size: 1.25rem;", r"font-size: 1.15rem;"),
    (r"font-size: 0.8rem;", r"font-size: 0.75rem;"),
    (r"font-size: 1.5rem;", r"font-size: 1.2rem;"),
    (r"font-size: 2.4rem;", r"font-size: 2.8rem;"),
    (r"min-height: 80px;", r"min-height: 60px;"),
    (r"--appa-card-pad: 10px;", r"--appa-card-pad: 8px;"),
]
for old, new in css_replacements:
    content = content.replace(old, new)


# 2. Replace _render_clima_resumo and _atualizar_clima_resumo
old_render_clima = r"""def _render_clima_resumo\(snapshot: DashboardSnapshot \| None\) -> dict\[str, ui\.element\]:.*?def _atualizar_clima_resumo.*?widgets\["contexto"\]\.text = _texto_contexto_clima\(previsao\)"""

new_render_clima = """def _render_clima_resumo(snapshot: DashboardSnapshot | None) -> dict[str, ui.element]:
    \"\"\"Constroi o resumo visual de clima em estilo dashboard (Minimalista/Futurista).\"\"\"
    with ui.element("div").classes("weather-now w-full h-full flex flex-col justify-center relative overflow-hidden"):
        # Decorative glow
        ui.html('<div style="position:absolute; top:-50px; right:-50px; width:150px; height:150px; background:radial-gradient(circle, rgba(0,240,255,0.15) 0%, transparent 70%); border-radius:50%; pointer-events:none;"></div>')
        
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                cidade = ui.label(snapshot.previsao.cidade if snapshot else "Sem dados").classes(
                    "text-lg font-bold text-neon tracking-wide"
                )
                data = ui.label(snapshot.previsao.data_alvo.isoformat() if snapshot else "--").classes(
                    "text-xs text-slate-400"
                )
            referencia = ui.label(
                _rotulo_referencia_clima(snapshot.previsao) if snapshot else "Sem referencia"
            ).classes("text-[10px] uppercase font-bold text-slate-500 bg-slate-800/50 px-2 py-1 rounded-full border border-slate-700/50")
            
        with ui.row().classes("w-full items-center gap-4 mt-2"):
            temperatura = ui.label(
                _formatar_grau(snapshot.previsao.temperatura_referencia) if snapshot else "--"
            ).classes("text-5xl font-black text-white drop-shadow-md")
            with ui.column().classes("gap-0"):
                sensacao = ui.label(f"Sensação: {_formatar_grau(snapshot.previsao.sensacao) if snapshot and snapshot.previsao.sensacao else '--'}").classes("text-xs text-slate-400")
                condicao = ui.label("Condição atual").classes("text-xs text-slate-300 font-medium")

        with ui.element("div").classes("stat-grid-modern"):
            maxima = _stat_box_modern("Máx", _formatar_grau(snapshot.previsao.maxima) if snapshot else "--", "mdi-arrow-up text-rose-400")
            minima = _stat_box_modern("Mín", _formatar_grau(snapshot.previsao.minima) if snapshot else "--", "mdi-arrow-down text-blue-400")
            chuva = _stat_box_modern("Chuva", _formatar_chuva(snapshot.previsao.chuva) if snapshot else "--", "mdi-water-percent text-cyan-400")
            uv = _stat_box_modern("UV Max", str(snapshot.previsao.uv_max) if snapshot and snapshot.previsao.uv_max else "--", "mdi-white-balance-sunny text-amber-400")
            umidade = _stat_box_modern("Umidade", f"{snapshot.previsao.umidade}%" if snapshot and snapshot.previsao.umidade else "--", "mdi-water text-blue-300")
            vento = _stat_box_modern("Vento", f"{snapshot.previsao.vento}km/h" if snapshot and snapshot.previsao.vento else "--", "mdi-weather-windy text-slate-300")
            nascer = _stat_box_modern("Nascer", snapshot.previsao.nascer_sol if snapshot and snapshot.previsao.nascer_sol else "--", "mdi-weather-sunset-up text-orange-400")
            por = _stat_box_modern("Pôr", snapshot.previsao.por_sol if snapshot and snapshot.previsao.por_sol else "--", "mdi-weather-sunset-down text-purple-400")
            
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

def _stat_box_modern(rotulo: str, valor: str, icone: str) -> ui.label:
    \"\"\"Cria uma mini caixa numerica para os blocos de clima, mais minimalista.\"\"\"
    with ui.element("div").classes("stat-box flex flex-col items-center justify-center p-2"):
        ui.icon(icone.split(" ")[0]).classes(f"text-base mb-1 {icone.split(' ')[1]}")
        texto = ui.label(valor).classes("text-sm font-bold text-slate-200")
        ui.label(rotulo).classes("text-[9px] uppercase tracking-wider text-slate-500 mt-1")
    return texto

def _atualizar_clima_resumo(widgets: dict[str, ui.element], snapshot: DashboardSnapshot) -> None:
    \"\"\"Atualiza o bloco principal de clima.\"\"\"
    previsao = snapshot.previsao
    widgets["cidade"].text = previsao.cidade
    widgets["data"].text = previsao.data_alvo.isoformat()
    widgets["referencia"].text = _rotulo_referencia_clima(previsao)
    widgets["temperatura"].text = _formatar_grau(previsao.temperatura_referencia)
    widgets["sensacao"].text = f"Sensação: {_formatar_grau(previsao.sensacao) if previsao.sensacao else '--'}"
    widgets["maxima"].text = _formatar_grau(previsao.maxima)
    widgets["minima"].text = _formatar_grau(previsao.minima)
    widgets["chuva"].text = _formatar_chuva(previsao.chuva)
    widgets["uv"].text = str(previsao.uv_max) if previsao.uv_max else "--"
    widgets["umidade"].text = f"{previsao.umidade}%" if previsao.umidade else "--"
    widgets["vento"].text = f"{previsao.vento}km/h" if previsao.vento else "--"
    widgets["nascer"].text = previsao.nascer_sol if previsao.nascer_sol else "--"
    widgets["por"].text = previsao.por_sol if previsao.por_sol else "--"
"""

content = re.sub(old_render_clima, new_render_clima, content, flags=re.DOTALL)

# 3. Remove _texto_contexto_clima
content = re.sub(r"def _texto_contexto_clima\(previsao: PrevisaoClima\) -> str:.*?return f.*?%", "", content, flags=re.DOTALL)


gui_path.write_text(content, encoding="utf-8")
print("gui.py updated")
