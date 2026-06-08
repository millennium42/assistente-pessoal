"""Resolucao centralizada de caminhos da aplicacao."""

from __future__ import annotations

from pathlib import Path


def resolver_relativo_ao_arquivo(caminho: Path, arquivo_base: Path) -> Path:
    """Resolve um caminho relativo usando a pasta do arquivo de referencia."""
    if caminho.is_absolute():
        return caminho
    return (arquivo_base.parent / caminho).resolve()


def caminho_exibicao(caminho: Path, base: Path | None = None) -> str:
    """Converte caminho para uma forma legivel sem depender do separador do sistema."""
    if base:
        try:
            return caminho.relative_to(base).as_posix()
        except ValueError:
            pass
    return caminho.as_posix()
