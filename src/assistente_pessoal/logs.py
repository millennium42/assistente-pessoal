"""Utilitarios de saida e log para manter a CLI consistente em pt-BR.

Este modulo centraliza a formatacao de mensagens para o usuario (usando rich)
e a configuracao basica da biblioteca de logging padrao do Python para
mensagens tecnicas e de diagnostico.
"""

from __future__ import annotations

import logging

from rich.console import Console

console = Console()


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Configura logs basicos para mensagens tecnicas durante a execucao.

    Args:
        nivel: O nivel de severidade dos logs (ex: logging.INFO, logging.DEBUG).
               O padrao e INFO.
    """
    logging.basicConfig(
        level=nivel,
        format="%(levelname)s:%(name)s:%(message)s",
    )


def avisar(mensagem: str) -> None:
    """Mostra um aviso em amarelo sem interromper o fluxo do usuario.

    Args:
        mensagem: A mensagem de aviso a ser exibida.
    """
    console.print(f"[yellow]{mensagem}[/yellow]")


def sucesso(mensagem: str) -> None:
    """Mostra uma mensagem de sucesso em verde.

    Args:
        mensagem: A mensagem de sucesso a ser exibida.
    """
    console.print(f"[green]{mensagem}[/green]")


def erro(mensagem: str) -> None:
    """Mostra uma mensagem de erro em vermelho.

    Args:
        mensagem: A mensagem de erro a ser exibida.
    """
    console.print(f"[red]{mensagem}[/red]")
