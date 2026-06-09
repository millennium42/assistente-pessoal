"""Memoria persistente em Markdown, compativel com Obsidian."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from heapq import nlargest
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente_pessoal.config import criar_pastas_vault


@dataclass(frozen=True)
class ResultadoMemoria:
    """Resultado encontrado no indice de memoria."""

    titulo: str
    caminho: Path
    trecho: str

    def to_dict(self) -> dict[str, str]:
        """Serializa resultado para API sem carregar conteudo completo."""
        return {"titulo": self.titulo, "caminho": str(self.caminho), "trecho": self.trecho}


@dataclass(frozen=True)
class NotaResumo:
    """Resumo seguro de uma nota local do vault."""

    titulo: str
    caminho: Path
    criado_em: str
    trecho: str

    def to_dict(self) -> dict[str, str]:
        """Serializa a nota para interfaces externas."""
        return {
            "titulo": self.titulo,
            "caminho": str(self.caminho),
            "criado_em": self.criado_em,
            "trecho": self.trecho,
        }


class MemoriaObsidian:
    """Gerencia notas Markdown e indice SQLite FTS5 dentro de um vault."""

    def __init__(self, vault_path: Path, timezone: str = "America/Sao_Paulo") -> None:
        """Inicializa a memoria apontando para um vault dedicado."""
        self.vault_path = vault_path
        self.timezone = timezone
        self.indice_path = vault_path / ".assistente" / "index.sqlite3"
        self._prepared = False

    def preparar(self) -> None:
        """Cria as pastas e o banco de indice caso ainda nao existam."""
        if self._prepared:
            return
        criar_pastas_vault(self.vault_path)
        self._criar_schema()
        self._prepared = True

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
            titulo=titulo,
            conteudo=conteudo,
            tags=tags_reais,
            timezone=self.timezone,
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
        arquivos = list(self._listar_arquivos_markdown())
        with self._connect() as conexao:
            conexao.execute("DELETE FROM notas")
            for caminho in arquivos:
                self._upsert_nota(conexao, caminho)
        return len(arquivos)

    def listar_notas(self, limite: int = 20) -> list[NotaResumo]:
        """Lista notas recentes sem expor metadados tecnicos do indice."""
        self.preparar()
        arquivos = nlargest(
            limite,
            self._listar_arquivos_markdown(),
            key=lambda caminho: caminho.stat().st_mtime,
        )
        notas: list[NotaResumo] = []
        for caminho in arquivos:
            stat = caminho.stat()
            titulo, conteudo = extrair_titulo_e_conteudo(caminho)
            trecho = " ".join(conteudo.split())[:240]
            criado_em = datetime.fromtimestamp(
                stat.st_mtime,
                tz=ZoneInfo(self.timezone),
            ).isoformat(timespec="seconds")
            notas.append(
                NotaResumo(
                    titulo=titulo,
                    caminho=caminho,
                    criado_em=criado_em,
                    trecho=trecho,
                )
            )
        return notas

    def apagar_nota(self, caminho: Path) -> bool:
        """Apaga uma nota Markdown dentro do vault e atualiza o indice."""
        self.preparar()
        caminho_real = caminho.resolve()
        vault_real = self.vault_path.resolve()
        if not caminho_real.is_relative_to(vault_real):
            raise ValueError("A nota informada esta fora do vault configurado.")
        if caminho_real.suffix.lower() != ".md":
            raise ValueError("Somente notas Markdown podem ser apagadas por esta rotina.")
        if not caminho_real.exists():
            return False
        caminho_real.unlink()
        with self._connect() as conexao:
            conexao.execute("DELETE FROM notas WHERE caminho = ?", (str(caminho_real),))
        return True

    def indexar_nota(self, caminho: Path) -> None:
        """Insere ou atualiza uma nota no indice SQLite FTS5."""
        with self._connect() as conexao:
            self._upsert_nota(conexao, caminho)

    def _criar_schema(self) -> None:
        """Cria a tabela FTS5 usada como indice de busca local."""
        self.indice_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conexao:
            conexao.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS notas
                USING fts5(titulo, caminho UNINDEXED, conteudo, tokenize='unicode61')
                """
            )

    def _connect(self) -> sqlite3.Connection:
        """Abre conexao SQLite com pragmas leves para desktop local."""
        conexao = sqlite3.connect(self.indice_path)
        conexao.execute("PRAGMA journal_mode=WAL")
        conexao.execute("PRAGMA synchronous=NORMAL")
        conexao.execute("PRAGMA temp_store=MEMORY")
        return conexao

    def _listar_arquivos_markdown(self):
        """Itera pelas notas Markdown visiveis sem incluir area tecnica."""
        yield from (
            caminho
            for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        )

    def _upsert_nota(self, conexao: sqlite3.Connection, caminho: Path) -> None:
        """Atualiza uma unica nota usando a mesma transacao ativa."""
        titulo, conteudo = extrair_titulo_e_conteudo(caminho)
        conexao.execute("DELETE FROM notas WHERE caminho = ?", (str(caminho),))
        conexao.execute(
            """
            INSERT INTO notas(titulo, caminho, conteudo)
            VALUES (?, ?, ?)
            """,
            (titulo, str(caminho), conteudo),
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
        unicodedata.normalize("NFKD", texto_minusculo)
        .encode("ascii", errors="ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", texto_sem_acento).strip("-")
    return slug or "nota"


def normalizar_consulta_fts(consulta: str) -> str:
    """Remove caracteres que quebram a sintaxe FTS5 e preserva termos uteis."""
    termos = re.findall(r"[\w\u00c0-\u00ff]+", consulta, flags=re.UNICODE)
    return " ".join(termos) or consulta


def _timestamp_slug(timezone: str) -> str:
    """Gera um prefixo cronologico para ordenar notas por criacao."""
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%d-%H%M%S")


def _escapar_yaml(valor: str) -> str:
    """Escapa aspas para manter o front matter valido."""
    return valor.replace('"', '\\"')
