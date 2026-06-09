"""Servicos de privacidade, exportacao e eliminacao local de dados."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from assistente_pessoal.config import AppConfig
from assistente_pessoal.domain.privacy import DATA_INVENTORY

SENSITIVE_CONFIG_FIELDS = {"api_key", "api_key_env", "token", "secret", "password"}


def data_map() -> list[dict[str, str]]:
    """Retorna o inventario de dados tratado pela aplicacao."""
    return [item.to_dict() for item in DATA_INVENTORY]


def safe_config(config: AppConfig) -> dict:
    """Serializa configuracao sem segredos, tokens ou paths absolutos desnecessarios."""
    dados = config.model_dump(mode="json")
    llm = dados.get("llm", {})
    if isinstance(llm, dict):
        llm["api_key_env"] = "***redacted***"
        llm["habilitado"] = config.llm.habilitado()
    dados["vault_path"] = str(config.vault_path)
    return _redact_mapping(dados)


def export_privacy_bundle(config: AppConfig, destino: Path) -> Path:
    """Exporta dados locais do assistente para um pacote JSON legivel."""
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"assistente-export-{_timestamp()}.json"
    payload = {
        "exportado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "configuracao_segura": safe_config(config),
        "mapa_de_dados": data_map(),
        "arquivos_markdown": _ler_markdown(config.vault_path),
    }
    arquivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return arquivo


def purge_generated_data(config: AppConfig) -> dict[str, list[str]]:
    """Remove indices e caches gerados sem apagar notas Markdown do usuario."""
    removidos: list[str] = []
    ignorados: list[str] = []
    candidatos = [
        config.vault_path / ".assistente" / "index.sqlite3",
        config.vault_path / ".assistente",
        Path(".assistente"),
        Path(".pytest_cache"),
        Path(".ruff_cache"),
    ]
    for caminho in candidatos:
        try:
            if not caminho.exists():
                ignorados.append(str(caminho))
                continue
            if caminho.is_dir():
                shutil.rmtree(caminho)
            else:
                caminho.unlink()
            removidos.append(str(caminho))
        except OSError:
            ignorados.append(str(caminho))
    return {"removidos": removidos, "ignorados": ignorados}


def _ler_markdown(vault_path: Path) -> list[dict[str, str]]:
    """Le Markdown do vault para portabilidade do titular."""
    if not vault_path.exists():
        return []
    arquivos = []
    for caminho in sorted(vault_path.rglob("*.md")):
        if ".assistente" in caminho.parts:
            continue
        arquivos.append(
            {
                "caminho": str(caminho.relative_to(vault_path)),
                "conteudo": caminho.read_text(encoding="utf-8"),
            }
        )
    return arquivos


def _redact_mapping(valor):
    """Redige chaves sensiveis recursivamente."""
    if isinstance(valor, dict):
        return {
            chave: "***redacted***"
            if any(sensivel in chave.lower() for sensivel in SENSITIVE_CONFIG_FIELDS)
            else _redact_mapping(item)
            for chave, item in valor.items()
        }
    if isinstance(valor, list):
        return [_redact_mapping(item) for item in valor]
    return valor


def _timestamp() -> str:
    """Gera timestamp seguro para nomes de arquivo."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
