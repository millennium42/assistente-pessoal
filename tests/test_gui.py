"""Testes leves do dashboard sem depender de navegador."""

from pathlib import Path

from assistente_pessoal.config import AppConfig
from assistente_pessoal.gui import construir_dashboard
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.painel import DashboardService


def test_dashboard_service_salva_documentos_fixos(tmp_path: Path) -> None:
    """Permite que GUI grave plano e agenda nos caminhos esperados do vault."""
    config = AppConfig(vault_path=tmp_path / "vault")
    servico = DashboardService(config)

    caminho_plano = servico.salvar_plano_estudos("Revisar algebra na segunda.")
    caminho_agenda = servico.salvar_agenda_local("10h - monitoria")

    assert caminho_plano == "60_planejamento/plano-estudos.md"
    assert caminho_agenda == "61_agenda_local/agenda-local.md"
    assert servico.carregar().indicadores.eventos_google == 0


def test_construir_dashboard_sem_subir_servidor(tmp_path: Path) -> None:
    """Constroi a arvore principal da GUI para capturar erros imediatos de import/layout."""
    config = AppConfig(vault_path=tmp_path / "vault")
    MemoriaObsidian(config.vault_path).salvar_nota("Teste", "Conteudo")

    construir_dashboard(DashboardService(config))
