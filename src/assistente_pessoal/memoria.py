"""Memoria persistente em Markdown, compativel com Obsidian."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente_pessoal.config import criar_pastas_vault
from assistente_pessoal.core_datas import normalizar_texto_ascii
from assistente_pessoal.core_paths import caminho_exibicao


@dataclass(frozen=True)
class ResultadoMemoria:
    """Resultado encontrado no indice de memoria."""

    titulo: str
    caminho: Path
    trecho: str


@dataclass(frozen=True)
class EstatisticasMemoria:
    """Resumo rapido do estado atual do vault e do indice."""

    vault_path: Path
    quantidade_notas: int
    indice_path: Path


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

    def salvar_documento_fixo(
        self,
        nome_arquivo: str,
        conteudo: str,
        pasta: str,
        titulo: str,
        tags: list[str] | None = None,
    ) -> Path:
        """Mantem um documento canonico do vault para GUI, agenda e planejamento."""
        self.preparar()
        caminho = self.vault_path / pasta / nome_arquivo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = renderizar_markdown(
            titulo=titulo,
            conteudo=conteudo,
            tags=tags or [],
            timezone=self.timezone,
        )
        caminho.write_text(texto, encoding="utf-8")
        self.indexar_nota(caminho)
        return caminho

    def ler_documento_fixo(self, pasta: str, nome_arquivo: str) -> str:
        """Le o corpo Markdown de um documento fixo quando ele existir."""
        caminho = self.vault_path / pasta / nome_arquivo
        if not caminho.exists():
            return ""
        texto = caminho.read_text(encoding="utf-8")
        return remover_front_matter(texto)

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

    def listar_recentes(self, limite: int = 5) -> list[Path]:
        """Lista as notas mais recentes pelo nome de arquivo cronologico."""
        self.preparar()
        arquivos = [
            caminho
            for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        ]
        return sorted(arquivos, reverse=True)[:limite]

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

    def estatisticas(self) -> EstatisticasMemoria:
        """Calcula um pequeno resumo util para diagnostico e GUI."""
        self.preparar()
        quantidade = len(
            [
                caminho
                for caminho in self.vault_path.rglob("*.md")
                if ".assistente" not in caminho.parts
            ]
        )
        return EstatisticasMemoria(
            vault_path=self.vault_path,
            quantidade_notas=quantidade,
            indice_path=self.indice_path,
        )

    def caminho_relativo(self, caminho: Path) -> str:
        """Exibe um caminho relativo ao vault para facilitar a abertura no Obsidian."""
        return caminho_exibicao(caminho, self.vault_path)

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


def remover_front_matter(texto: str) -> str:
    """Remove o front matter YAML mantendo apenas o corpo util do documento."""
    if not texto.startswith("---\n"):
        return texto
    partes = texto.split("---\n", maxsplit=2)
    if len(partes) < 3:
        return texto
    return partes[2].lstrip()


def extrair_titulo_e_conteudo(caminho: Path) -> tuple[str, str]:
    """Extrai titulo e conteudo textual de uma nota Markdown."""
    texto = caminho.read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip(), texto
    return caminho.stem, texto


def slugificar(texto: str) -> str:
    """Transforma texto livre em um nome de arquivo estavel e legivel."""
    texto_minusculo = normalizar_texto_ascii(texto).lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", texto_minusculo).strip("-")
    return slug or "nota"


def normalizar_consulta_fts(consulta: str) -> str:
    """Remove caracteres que quebram a sintaxe FTS5 e preserva termos uteis."""
    consulta_ascii = normalizar_texto_ascii(consulta)
    termos = re.findall(r"[\w]+", consulta_ascii, flags=re.UNICODE)
    return " ".join(termos) or consulta_ascii


def _timestamp_slug(timezone: str) -> str:
    """Gera um prefixo cronologico para ordenar notas por criacao."""
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%d-%H%M%S")


def _escapar_yaml(valor: str) -> str:
    """Escapa aspas para manter o front matter valido."""
    return valor.replace('"', '\\"')
