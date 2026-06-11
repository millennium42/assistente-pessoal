"""Memoria persistente baseada em banco de dados relacional (SQLite).

Este modulo gerencia as anotacoes da aplicacao criando registros
em um banco de dados relacional. Mantem um indice de busca
de texto completo (FTS5) usando SQLite para recuperar rapidamente as notas.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente_pessoal.core_datas import normalizar_texto_ascii


@dataclass(frozen=True)
class ResultadoMemoria:
    """Resultado encontrado no indice de memoria.

    Attributes:
        titulo: O titulo do documento encontrado.
        caminho: O caminho (ID) do arquivo no banco.
        trecho: Um fragmento de texto (snippet) contendo os termos de busca.
    """
    titulo: str
    caminho: Path
    trecho: str


@dataclass(frozen=True)
class EstatisticasMemoria:
    """Resumo rapido do estado atual da memoria.

    Attributes:
        db_path: O caminho do banco de dados SQLite.
        quantidade_notas: O numero total de notas.
    """
    db_path: Path
    quantidade_notas: int


class Memoria:
    """Gerencia notas em banco de dados SQLite."""

    def __init__(self, db_path: Path, timezone: str = "America/Sao_Paulo") -> None:
        """Inicializa a memoria apontando para o banco de dados.

        Args:
            db_path: O caminho para o banco de dados SQLite.
            timezone: O fuso horario para as datas de criacao das notas.
        """
        self.db_path = db_path
        self.timezone = timezone

    def preparar(self) -> None:
        """Cria as tabelas e o banco caso ainda nao existam."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS documentos (
                    caminho TEXT PRIMARY KEY,
                    titulo TEXT,
                    conteudo TEXT,
                    pasta TEXT,
                    tags TEXT,
                    criado_em TEXT,
                    atualizado_em TEXT
                )
                """
            )
            conexao.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documentos_fts
                USING fts5(titulo, caminho UNINDEXED, conteudo, tokenize='unicode61')
                """
            )

    def salvar_nota(
        self,
        titulo: str,
        conteudo: str,
        pasta: str = "10_memoria",
        tags: list[str] | None = None,
    ) -> Path:
        """Salva uma nota e indexa.

        Args:
            titulo: Titulo da nota.
            conteudo: O conteudo textual da nota.
            pasta: A pasta (categoria) virtual.
            tags: Lista opcional de tags.

        Returns:
            O caminho virtual (ID) da nota recem-criada.
        """
        self.preparar()
        tags_reais = tags or []
        slug = f"{_timestamp_slug(self.timezone)}-{slugificar(titulo)}.md"
        caminho_str = f"{pasta}/{slug}"
        caminho = Path(caminho_str)
        agora = datetime.now(ZoneInfo(self.timezone)).isoformat(timespec="seconds")
        tags_json = json.dumps(tags_reais)

        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute(
                """
                INSERT OR REPLACE INTO documentos (caminho, titulo, conteudo, pasta, tags, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (caminho_str, titulo, conteudo, pasta, tags_json, agora, agora),
            )
            conexao.execute("DELETE FROM documentos_fts WHERE caminho = ?", (caminho_str,))
            conexao.execute(
                """
                INSERT INTO documentos_fts(titulo, caminho, conteudo)
                VALUES (?, ?, ?)
                """,
                (titulo, caminho_str, conteudo),
            )
        return caminho

    def salvar_documento_fixo(
        self,
        nome_arquivo: str,
        conteudo: str,
        pasta: str,
        titulo: str,
        tags: list[str] | None = None,
    ) -> Path:
        """Mantem um documento canonico.

        Args:
            nome_arquivo: Nome literal do arquivo virtual.
            conteudo: Conteudo atualizado do documento.
            pasta: O diretorio de destino virtual.
            titulo: Titulo humano para exibicao e busca.
            tags: Lista opcional de tags.

        Returns:
            O caminho virtual absoluto atualizado.
        """
        self.preparar()
        caminho_str = f"{pasta}/{nome_arquivo}"
        caminho = Path(caminho_str)
        agora = datetime.now(ZoneInfo(self.timezone)).isoformat(timespec="seconds")
        tags_json = json.dumps(tags or [])

        with sqlite3.connect(self.db_path) as conexao:
            # Verifica se existe para nao alterar data de criacao se nao precisar, ou apenas atualiza
            existente = conexao.execute("SELECT criado_em FROM documentos WHERE caminho = ?", (caminho_str,)).fetchone()
            criado_em = existente[0] if existente else agora

            conexao.execute(
                """
                INSERT OR REPLACE INTO documentos (caminho, titulo, conteudo, pasta, tags, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (caminho_str, titulo, conteudo, pasta, tags_json, criado_em, agora),
            )
            conexao.execute("DELETE FROM documentos_fts WHERE caminho = ?", (caminho_str,))
            conexao.execute(
                """
                INSERT INTO documentos_fts(titulo, caminho, conteudo)
                VALUES (?, ?, ?)
                """,
                (titulo, caminho_str, conteudo),
            )
        return caminho

    def ler_documento_fixo(self, pasta: str, nome_arquivo: str) -> str:
        """Le o corpo de um documento fixo quando ele existir no banco.

        Args:
            pasta: Diretorio virtual do arquivo.
            nome_arquivo: O nome do arquivo a ser lido.

        Returns:
            O texto principal do documento, ou string vazia se nao existir.
        """
        caminho_str = f"{pasta}/{nome_arquivo}"
        try:
            with sqlite3.connect(self.db_path) as conexao:
                linha = conexao.execute(
                    "SELECT conteudo FROM documentos WHERE caminho = ?", (caminho_str,)
                ).fetchone()
                return linha[0] if linha else ""
        except sqlite3.OperationalError:
            return ""

    def buscar(self, consulta: str, limite: int = 5) -> list[ResultadoMemoria]:
        """Busca notas pelo indice FTS5.

        Args:
            consulta: Termo ou frase a ser pesquisada.
            limite: Numero maximo de resultados a retornar.

        Returns:
            Uma lista de objetos ResultadoMemoria correspondentes.
        """
        self.preparar()
        termo = consulta.strip()
        if not termo:
            return []
        with sqlite3.connect(self.db_path) as conexao:
            try:
                linhas = conexao.execute(
                    """
                    SELECT titulo, caminho, snippet(documentos_fts, 2, '[', ']', '...', 12)
                    FROM documentos_fts
                    WHERE documentos_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (normalizar_consulta_fts(termo), limite),
                ).fetchall()
            except sqlite3.OperationalError:
                linhas = conexao.execute(
                    """
                    SELECT titulo, caminho, substr(conteudo, 1, 240)
                    FROM documentos
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
        """Reconstrui o indice.

        Returns:
            O numero de notas que foram processadas.
        """
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute("DELETE FROM documentos_fts")
            linhas = conexao.execute("SELECT titulo, caminho, conteudo FROM documentos").fetchall()
            for titulo, caminho, conteudo in linhas:
                conexao.execute(
                    """
                    INSERT INTO documentos_fts(titulo, caminho, conteudo)
                    VALUES (?, ?, ?)
                    """,
                    (titulo, caminho, conteudo),
                )
        return len(linhas)

    def listar_recentes(self, limite: int = 5) -> list[Path]:
        """Lista as notas mais recentes.

        Args:
            limite: Quantidade de caminhos a retornar.

        Returns:
            Uma lista com os caminhos virtuais mais recentes.
        """
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            linhas = conexao.execute(
                "SELECT caminho FROM documentos ORDER BY criado_em DESC LIMIT ?", (limite,)
            ).fetchall()
        return [Path(linha[0]) for linha in linhas]

    def estatisticas(self) -> EstatisticasMemoria:
        """Calcula um pequeno resumo.

        Returns:
            As estatisticas de contagem de notas.
        """
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            quantidade = conexao.execute("SELECT count(*) FROM documentos").fetchone()[0]
        return EstatisticasMemoria(
            db_path=self.db_path,
            quantidade_notas=quantidade,
        )

    def caminho_relativo(self, caminho: Path) -> str:
        """Retorna o proprio caminho ja que internamente usamos formato relativo.

        Args:
            caminho: O caminho virtual.

        Returns:
            O caminho relativo formatado em posix.
        """
        return caminho.as_posix()


def slugificar(texto: str) -> str:
    """Transforma texto livre em um nome de arquivo estavel.

    Args:
        texto: O texto original (geralmente um titulo).

    Returns:
        Um texto hifenizado.
    """
    texto_minusculo = normalizar_texto_ascii(texto).lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", texto_minusculo).strip("-")
    return slug or "nota"


def normalizar_consulta_fts(consulta: str) -> str:
    """Remove caracteres que quebram a sintaxe FTS5.

    Args:
        consulta: A query do usuario.

    Returns:
        A query sanitizada para o SQLite.
    """
    consulta_ascii = normalizar_texto_ascii(consulta)
    termos = re.findall(r"[\w]+", consulta_ascii, flags=re.UNICODE)
    return " ".join(termos) or consulta_ascii


def _timestamp_slug(timezone: str) -> str:
    """Gera um prefixo cronologico para notas.

    Args:
        timezone: O fuso horario a ser utilizado.

    Returns:
        String no formato YYYYMMDD-HHMMSS.
    """
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%d-%H%M%S")
