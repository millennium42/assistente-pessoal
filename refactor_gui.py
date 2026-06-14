import re
from pathlib import Path

file_path = Path("src/assistente_pessoal/gui.py")
content = file_path.read_text(encoding="utf-8")

# 1. CSS view toggles removal
clean_css_patterns = [
    r'html\[data-view="clean"\] \.detail-metric\s*\{\s*display:\s*none;\s*\}',
    r'html\[data-view="clean"\] \.dashboard-shell\s*\{\s*gap:\s*16px;\s*\}',
    r'html\[data-view="clean"\] \.appa-top\s*\{\s*min-height:\s*132px;\s*\}',
    r'html\[data-view="clean"\] \.appa-title\s*\{\s*font-size:\s*1\.32rem;\s*\}',
    r'html\[data-view="clean"\] \.commandbar\s*\{\s*padding:\s*14px;\s*\}',
    r'html\[data-view="clean"\] \.kpi\s*\{\s*min-height:\s*104px;\s*padding:\s*18px;\s*\}',
    r'html\[data-view="clean"\] \.kpi-detail\s*\{\s*display:\s*none;\s*\}',
    r'html\[data-view="clean"\] \.kpi-value\s*\{\s*font-size:\s*1\.65rem;\s*\}',
    r'html\[data-view="clean"\] \.overview-charts-grid,\s*html\[data-view="clean"\] \.overview-local-grid\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important;\s*\}',
    r'html\[data-view="clean"\] \.panel-news-distribution\s*\{\s*display:\s*none;\s*\}',
    r'html\[data-view="clean"\] \.chart-weather\s*\{\s*height:\s*330px;\s*\}',
    r'html\[data-view="clean"\] \.weather-now\s*\{\s*min-height:\s*250px;\s*\}',
    r'html\[data-view="clean"\] \.stat-grid-modern\s*\{\s*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);\s*\}',
]

for p in clean_css_patterns:
    content = re.sub(p, '', content, flags=re.DOTALL)

# Make "detailed" the default
content = content.replace('html[data-view="detailed"] ', '')
content = content.replace('html[data-view="detailed"]', '')

# 2. JS View controls removal
content = content.replace('document.documentElement.dataset.view = \'clean\';', '')

# Use simple splits to remove JS functions
def remove_js_func(name):
    global content
    if name in content:
        start = content.find(name)
        # Find the closing brace of the function at the correct indentation
        # Since these are in _dashboard_js, they end with "      };\n"
        end = content.find("      };", start)
        if end != -1:
            content = content[:start] + content[end + 8:]

remove_js_func("appa.applyViewControls = function () {")
remove_js_func("appa.setView = function (mode) {")

if "if (!appa.viewClickHandler) {" in content:
    start = content.find("if (!appa.viewClickHandler) {")
    end = content.find("      }", start)
    content = content[:start] + content[end + 7:]

# Boot logic
boot_view_logic = """        let storedView = document.documentElement.dataset.view || 'clean';
        try { storedView = localStorage.getItem('appa-dashboard-view') || storedView; }
        catch (error) {}
        appa.setView(storedView);"""
content = content.replace(boot_view_logic, '')

content = content.replace("appa.applyViewControls();", "")
content = content.replace("appa.currentView = appa.currentView || 'clean';", "")

# 3. HTML View Toggles removal
view_toggle_1 = """                <div class="view-toggle" aria-label="Visualizacao do painel">
                  <button type="button" data-view-choice="clean">
                    <span class="material-icons appa-seg-icon">view_agenda</span>
                    Limpa
                  </button>
                  <button type="button" data-view-choice="detailed">
                    <span class="material-icons appa-seg-icon">table_rows</span>
                    Detalhada
                  </button>
                </div>"""
content = content.replace(view_toggle_1, '')

view_toggle_2 = """                            <div class="view-toggle mb-2" aria-label="Visualizacao do painel">
                              <button type="button" data-view-choice="clean">
                                <span class="material-icons appa-seg-icon">view_agenda</span>
                                Limpa
                              </button>
                              <button type="button" data-view-choice="detailed">
                                <span class="material-icons appa-seg-icon">table_rows</span>
                                Detalhada
                              </button>
                            </div>"""
content = content.replace(view_toggle_2, '')

# 4. GUI Visual Enhancements
replacements = {
    "--appa-bg: #0a0f1a;": "--appa-bg: #050810;",
    "--appa-panel: #111827;": "--appa-panel: #0b111a;",
    "--appa-panel-soft: #172033;": "--appa-panel-soft: #141c2b;",
    "--appa-card-bg: #111827;": "--appa-card-bg: #0b111a;",
    "border-radius: 8px;": "border-radius: 12px;",
    "backdrop-filter: blur(12px);": "backdrop-filter: blur(24px);",
    "--appa-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);": "--appa-shadow: 0 12px 32px rgba(0, 240, 255, 0.08);",
    "--appa-line: rgba(148, 163, 184, 0.20);": "--appa-line: rgba(148, 163, 184, 0.12);",
    "--appa-command: rgba(15, 23, 42, 0.94);": "--appa-command: rgba(11, 17, 26, 0.85);",
    "box-shadow: var(--appa-shadow);": "box-shadow: 0 4px 20px rgba(0,0,0,0.4), var(--appa-shadow);"
}
for old, new in replacements.items():
    content = content.replace(old, new)

# One minor fix: limit of news is already on configurations tab, but let's make sure its padding/spacing is fine
# We did replace border-radius: 8px to 12px, so the GUI will look softer and more modern.

file_path.write_text(content, encoding="utf-8")
print("gui.py visually enhanced and view toggle removed.")