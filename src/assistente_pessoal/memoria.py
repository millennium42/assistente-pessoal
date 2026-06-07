"""Memoria persistente em Markdown, compativel com Obsidian."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente_pessoal.config import criar_pastas_vault


@dataclass(frozen=True)
class ResultadoMemoria:
    """Resultado encontrado no indice de memoria."""

    titulo: str
    caminho: Path
    trecho: str


class MemoriaObsidian:
    """Gerencia notas Markdown e indice SQLite FTS5 dentro de um vault."""

    def __init__(self, vault_path: Path, timezone: str = "America/Sao_Paulo") -> None:
        """Inicializa a memoria apontando para um vault dedicado."""
        self.vault_path = vault_path
        self.timezone = timezone
        self.indice_path = vault_path / ".assistente" / "index.sqlite3"

    def preparar(self) -> None:
        """Cria as pastas e o banco de indice caso ainda nao existam."""
        criar_pastas_vault(self.vault_path)
        self._criar_schema()

    def salvar_nota(
        self,
        titulo: str,
        conteudo: str,
        pasta: str = "10_memoria",
        tags: list[str] | None = None,
    ) -> Path:
        """Salva uma nota Markdown com front matter simples e reindexa a nota."""
        self.preparar()
        tags_reais = tags or []
        pasta_destino = self.vault_path / pasta
        pasta_destino.mkdir(parents=True, exist_ok=True)
        caminho = pasta_destino / f"{_timestamp_slug(self.timezone)}-{slugificar(titulo)}.md"
        texto = renderizar_markdown(
            titulo=titulo, conteudo=conteudo, tags=tags_reais, timezone=self.timezone
        )
        caminho.write_text(texto, encoding="utf-8")
        self.indexar_nota(caminho)
        return caminho

    def buscar(self, consulta: str, limite: int = 5) -> list[ResultadoMemoria]:
        """Busca notas pelo indice FTS5, com fallback tolerante para consultas simples."""
        self.preparar()
        termo = consulta.strip()
        if not termo:
            return []
        with sqlite3.connect(self.indice_path) as conexao:
            try:
                linhas = conexao.execute(
                    """
                    SELECT titulo, caminho, snippet(notas, 2, '[', ']', '...', 12)
                    FROM notas
                    WHERE notas MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (normalizar_consulta_fts(termo), limite),
                ).fetchall()
            except sqlite3.OperationalError:
                linhas = conexao.execute(
                    """
                    SELECT titulo, caminho, substr(conteudo, 1, 240)
                    FROM notas
                    WHERE conteudo LIKE ? OR titulo LIKE ?
                    LIMIT ?
                    """,
                    (f"%{termo}%", f"%{termo}%", limite),
                ).fetchall()
        return [
            ResultadoMemoria(titulo=titulo, caminho=Path(caminho), trecho=trecho)
            for titulo, caminho, trecho in linhas
        ]

    def reindexar(self) -> int:
        """Reconstrui o indice a partir de todos os Markdown existentes no vault."""
        self.preparar()
        arquivos = [
            caminho
            for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        ]
        with sqlite3.connect(self.indice_path) as conexao:
            conexao.execute("DELETE FROM notas")
        for caminho in arquivos:
            self.indexar_nota(caminho)
        return len(arquivos)

    def indexar_nota(self, caminho: Path) -> None:
        """Insere ou atualiza uma nota no indice SQLite FTS5."""
        titulo, conteudo = extrair_titulo_e_conteudo(caminho)
        with sqlite3.connect(self.indice_path) as conexao:
            conexao.execute("DELETE FROM notas WHERE caminho = ?", (str(caminho),))
            conexao.execute(
                """
                INSERT INTO notas(titulo, caminho, conteudo)
                VALUES (?, ?, ?)
                """,
                (titulo, str(caminho), conteudo),
            )

    def _criar_schema(self) -> None:
        """Cria a tabela FTS5 usada como indice de busca local."""
        self.indice_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.indice_path) as conexao:
            conexao.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS notas
                USING fts5(titulo, caminho UNINDEXED, conteudo, tokenize='unicode61')
                """
            )


def renderizar_markdown(
    titulo: str,
    conteudo: str,
    tags: list[str],
    timezone: str = "America/Sao_Paulo",
) -> str:
    """Monta uma nota Markdown padronizada para o vault do assistente."""
    agora = datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")
    tags_yaml = "\n".join(f"  - {tag}" for tag in tags)
    return f"""---
titulo: "{_escapar_yaml(titulo)}"
criado_em: "{agora}"
tags:
{tags_yaml if tags_yaml else "  - assistente"}
---

# {titulo}

{conteudo.strip()}
"""


def extrair_titulo_e_conteudo(caminho: Path) -> tuple[str, str]:
    """Extrai titulo e conteudo textual de uma nota Markdown."""
    texto = caminho.read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip(), texto
    return caminho.stem, texto


def slugificar(texto: str) -> str:
    """Transforma texto livre em um nome de arquivo estavel e legivel."""
    texto_minusculo = texto.lower().strip()
    texto_sem_acento = (
        texto_minusculo.replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", texto_sem_acento).strip("-")
    return slug or "nota"


def normalizar_consulta_fts(consulta: str) -> str:
    """Remove caracteres que quebram a sintaxe FTS5 e preserva termos uteis."""
    termos = re.findall(r"[\wÀ-ÿ]+", consulta, flags=re.UNICODE)
    return " ".join(termos) or consulta


def _timestamp_slug(timezone: str) -> str:
    """Gera um prefixo cronologico para ordenar notas por criacao."""
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%d-%H%M%S")


def _escapar_yaml(valor: str) -> str:
    """Escapa aspas para manter o front matter valido."""
    return valor.replace('"', '\\"')
