"""Resolucao centralizada de caminhos da aplicacao.

Este modulo prove funcoes utilitarias para manipulacao e resolucao
de caminhos de arquivos de forma consistente na aplicacao.
"""

from __future__ import annotations

from pathlib import Path


def resolver_relativo_ao_arquivo(caminho: Path, arquivo_base: Path) -> Path:
    """Resolve um caminho relativo usando a pasta do arquivo de referencia.

    Args:
        caminho: O caminho a ser resolvido (pode ser absoluto ou relativo).
        arquivo_base: O caminho do arquivo cujo diretorio servira de base caso o
            caminho informado seja relativo.

    Returns:
        Um objeto Path absoluto e resolvido.
    """
    if caminho.is_absolute():
        return caminho
    return (arquivo_base.parent / caminho).resolve()


def caminho_exibicao(caminho: Path, base: Path | None = None) -> str:
    """Converte caminho para uma forma legivel sem depender do separador do sistema.

    Util para exibicao de caminhos em logs e interfaces, sempre usando barra normal (/).

    Args:
        caminho: O caminho a ser formatado.
        base: Opcional. Se fornecido e o caminho estiver contido nesta base,
            o resultado sera um caminho relativo a ela.

    Returns:
        O caminho em formato de string (posix).
    """
    if base:
        try:
            return caminho.relative_to(base).as_posix()
        except ValueError:
            pass
    return caminho.as_posix()
