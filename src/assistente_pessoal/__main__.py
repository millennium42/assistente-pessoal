"""Ponto de entrada para executar o pacote com ``python -m assistente_pessoal``."""

from assistente_pessoal.cli import app


def main() -> None:
    """Executa a aplicacao de linha de comando do assistente."""
    app()


if __name__ == "__main__":
    main()
