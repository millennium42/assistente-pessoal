"""Utilitarios de saida e log para manter a CLI consistente em pt-BR."""

from __future__ import annotations

import logging

from rich.console import Console

console = Console()


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Configura logs basicos para mensagens tecnicas durante a execucao."""
    logging.basicConfig(
        level=nivel,
        format="%(levelname)s:%(name)s:%(message)s",
    )


def avisar(mensagem: str) -> None:
    """Mostra um aviso em amarelo sem interromper o fluxo do usuario."""
    console.print(f"[yellow]{mensagem}[/yellow]")


def sucesso(mensagem: str) -> None:
    """Mostra uma mensagem de sucesso em verde."""
    console.print(f"[green]{mensagem}[/green]")


def erro(mensagem: str) -> None:
    """Mostra uma mensagem de erro em vermelho."""
    console.print(f"[red]{mensagem}[/red]")
