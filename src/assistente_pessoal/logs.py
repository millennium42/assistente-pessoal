"""Utilitarios de saida e log com redaction de dados sensiveis."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from rich.console import Console

console = Console()

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)(api[_-]?key|token|secret|authorization|client_secret)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(bearer\s+)([a-z0-9._\-]+)"),
    re.compile(r"(?i)(GOCSPX-[a-z0-9_\-]+)"),
)


def redact_sensitive(value: Any) -> Any:
    """Redige segredos em strings, listas e dicionarios."""
    if isinstance(value, str):
        texto = value
        for pattern in SENSITIVE_PATTERNS:
            texto = pattern.sub(_replace_match, texto)
        return texto
    if isinstance(value, Mapping):
        return {
            chave: "***redacted***" if _is_sensitive_key(str(chave)) else redact_sensitive(item)
            for chave, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value


class RedactingFormatter(logging.Formatter):
    """Formatter que evita vazamento de segredos em mensagens tecnicas."""

    def format(self, record: logging.LogRecord) -> str:
        """Aplica redaction no resultado final do formatter base."""
        return str(redact_sensitive(super().format(record)))


def configurar_logs(nivel: int = logging.INFO) -> None:
    """Configura logs basicos com redaction para execucao local."""
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(levelname)s:%(name)s:%(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)


def avisar(mensagem: str) -> None:
    """Mostra um aviso em amarelo sem interromper o fluxo do usuario."""
    console.print(f"[yellow]{redact_sensitive(mensagem)}[/yellow]")


def sucesso(mensagem: str) -> None:
    """Mostra uma mensagem de sucesso em verde."""
    console.print(f"[green]{redact_sensitive(mensagem)}[/green]")


def erro(mensagem: str) -> None:
    """Mostra uma mensagem de erro em vermelho."""
    console.print(f"[red]{redact_sensitive(mensagem)}[/red]")


def _replace_match(match: re.Match[str]) -> str:
    """Preserva o nome do campo e remove somente o valor sensivel."""
    if len(match.groups()) == 3:
        return f"{match.group(1)}{match.group(2)}***redacted***"
    if len(match.groups()) == 2:
        return f"{match.group(1)}***redacted***"
    return "***redacted***"


def _is_sensitive_key(key: str) -> bool:
    """Identifica nomes de campos que nunca devem sair em claro."""
    key_lower = key.lower()
    return any(part in key_lower for part in ("api_key", "token", "secret", "authorization"))
