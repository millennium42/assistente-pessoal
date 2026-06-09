"""Servidor local da API usada pela GUI da V1."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from assistente_pessoal.api.app import create_app
from assistente_pessoal.config import carregar_config

server_app = typer.Typer(help="Servidor local do Assistente Pessoal.")


@server_app.command()
def run(
    host: Annotated[
        str,
        typer.Option(help="Host local. Use 127.0.0.1 para evitar exposicao na rede."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Porta local da API.")] = 8777,
    config: Annotated[Path | None, typer.Option("--config", help="Arquivo config.toml.")] = None,
) -> None:
    """Inicia API local para a GUI desktop ou desenvolvimento."""
    app = create_app(carregar_config(config))
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    """Entrada console_script para API local."""
    server_app()


if __name__ == "__main__":
    main()
