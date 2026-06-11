"""Memoria persistente em Markdown, compativel com Obsidian.

Este modulo gerencia as anotacoes da aplicacao criando notas Markdown
estruturadas com front matter YAML. Tambem mantem um indice de busca
de texto completo (FTS5) usando SQLite para recuperar rapidamente as notas.
"""

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
    """Resultado encontrado no indice de memoria.

    Attributes:
        titulo: O titulo do documento encontrado.
        caminho: O caminho completo do arquivo no vault.
        trecho: Um fragmento de texto (snippet) contendo os termos de busca.
    """

    titulo: str
    caminho: Path
    trecho: str


@dataclass(frozen=True)
class EstatisticasMemoria:
    """Resumo rapido do estado atual do vault e do indice.

    Attributes:
        vault_path: O caminho raiz do vault de memoria.
        quantidade_notas: O numero total de notas indexadas.
        indice_path: O caminho do arquivo do banco SQLite.
    """

    vault_path: Path
    quantidade_notas: int
    indice_path: Path


class MemoriaObsidian:
    """Gerencia notas Markdown e indice SQLite FTS5 dentro de um vault."""

    def __init__(self, vault_path: Path, timezone: str = "America/Sao_Paulo") -> None:
        """Inicializa a memoria apontando para um vault dedicado.

        Args:
            vault_path: O diretorio base do vault Obsidian.
            timezone: O fuso horario para as datas de criacao das notas.
        """
        self.vault_path = vault_path
        self.timezone = timezone
        self.indice_path = vault_path / ".assistente" / "index.sqlite3"

    def preparar(self) -> None:
        """Cria as pastas padroes e o banco de indice caso ainda nao existam."""
        criar_pastas_vault(self.vault_path)
        self._criar_schema()

    def salvar_nota(
        self,
        titulo: str,
        conteudo: str,
        pasta: str = "10_memoria",
        tags: list[str] | None = None,
    ) -> Path:
        """Salva uma nota Markdown com front matter simples e reindexa a nota.

        Args:
            titulo: Titulo da nota (sera usado tambem no nome do arquivo).
            conteudo: O conteudo textual da nota em Markdown.
            pasta: A subpasta dentro do vault onde a nota sera salva.
            tags: Lista opcional de tags para categorizar a nota.

        Returns:
            O caminho absoluto do arquivo recem-criado.
        """
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
        """Mantem um documento canonico do vault para GUI, agenda e planejamento.

        Sobrescreve o arquivo existente no caminho especificado e atualiza o indice.

        Args:
            nome_arquivo: Nome literal do arquivo (ex: 'agenda.md').
            conteudo: Conteudo atualizado do documento.
            pasta: O diretorio de destino relativo ao vault.
            titulo: Titulo humano para exibicao e busca.
            tags: Lista opcional de tags.

        Returns:
            O caminho absoluto do arquivo atualizado.
        """
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
        """Le o corpo Markdown de um documento fixo quando ele existir.

        Remove o front matter antes de retornar para facilitar o processamento.

        Args:
            pasta: Diretorio relativo do arquivo.
            nome_arquivo: O nome do arquivo a ser lido.

        Returns:
            O texto principal do documento, ou string vazia se nao existir.
        """
        caminho = self.vault_path / pasta / nome_arquivo
        if not caminho.exists():
            return ""
        texto = caminho.read_text(encoding="utf-8")
        return remover_front_matter(texto)

    def buscar(self, consulta: str, limite: int = 5) -> list[ResultadoMemoria]:
        """Busca notas pelo indice FTS5, com fallback tolerante para consultas simples.

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
        """Reconstrui o indice a partir de todos os Markdown existentes no vault.

        Returns:
            O numero de notas que foram processadas e indexadas.
        """
        self.preparar()
        arquivos = [
            caminho
            for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        ]
        with sqlite3.connect(self.indice_path) as conexao:
            conexao.execute("DELETE FROM notas")
            for caminho in arquivos:
                titulo, conteudo = extrair_titulo_e_conteudo(caminho)
                conexao.execute(
                    """
                    INSERT INTO notas(titulo, caminho, conteudo)
                    VALUES (?, ?, ?)
                    """,
                    (titulo, str(caminho), conteudo),
                )
        return len(arquivos)

    def listar_recentes(self, limite: int = 5) -> list[Path]:
        """Lista as notas mais recentes pelo nome de arquivo cronologico.

        Args:
            limite: Quantidade de caminhos a retornar.

        Returns:
            Uma lista com os caminhos mais recentes.
        """
        self.preparar()
        arquivos = (
            caminho
            for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        )
        return sorted(arquivos, reverse=True)[:limite]

    def indexar_nota(self, caminho: Path) -> None:
        """Insere ou atualiza uma unica nota no indice SQLite FTS5.

        Args:
            caminho: Caminho absoluto para a nota a ser indexada.
        """
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
        """Calcula um pequeno resumo util para diagnostico e GUI.

        Returns:
            As estatisticas de contagem de notas e caminhos vitais.
        """
        self.preparar()
        quantidade = sum(
            1 for caminho in self.vault_path.rglob("*.md")
            if ".assistente" not in caminho.parts
        )
        return EstatisticasMemoria(
            vault_path=self.vault_path,
            quantidade_notas=quantidade,
            indice_path=self.indice_path,
        )

    def caminho_relativo(self, caminho: Path) -> str:
        """Exibe um caminho relativo ao vault para facilitar a abertura no Obsidian.

        Args:
            caminho: O caminho absoluto do arquivo ou diretorio.

        Returns:
            O caminho relativo formatado em posix.
        """
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
    """Monta uma nota Markdown padronizada para o vault do assistente.

    Args:
        titulo: Titulo do documento.
        conteudo: O conteudo pre-formatado.
        tags: Lista de metadados de tags.
        timezone: O fuso horario para o timestamp de criacao.

    Returns:
        O texto completo do arquivo Markdown com front matter YAML.
    """
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
    """Remove o front matter YAML mantendo apenas o corpo util do documento.

    Args:
        texto: Conteudo original com possivel bloco de metadados na primeira linha.

    Returns:
        O texto sem o bloco YAML inicial.
    """
    if not texto.startswith("---\n"):
        return texto
    partes = texto.split("---\n", maxsplit=2)
    if len(partes) < 3:
        return texto
    return partes[2].lstrip()


def extrair_titulo_e_conteudo(caminho: Path) -> tuple[str, str]:
    """Extrai titulo e conteudo textual de uma nota Markdown.

    Args:
        caminho: O caminho para o arquivo.

    Returns:
        Uma tupla contendo o titulo derivado (da tag H1 ou nome do arquivo) e o conteudo total.
    """
    texto = caminho.read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip(), texto
    return caminho.stem, texto


def slugificar(texto: str) -> str:
    """Transforma texto livre em um nome de arquivo estavel e legivel.

    Args:
        texto: O texto original (geralmente um titulo).

    Returns:
        Um texto hifenizado compativel com sistema de arquivos.
    """
    texto_minusculo = normalizar_texto_ascii(texto).lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", texto_minusculo).strip("-")
    return slug or "nota"


def normalizar_consulta_fts(consulta: str) -> str:
    """Remove caracteres que quebram a sintaxe FTS5 e preserva termos uteis.

    Args:
        consulta: A query do usuario.

    Returns:
        A query sanitizada para o SQLite.
    """
    consulta_ascii = normalizar_texto_ascii(consulta)
    termos = re.findall(r"[\w]+", consulta_ascii, flags=re.UNICODE)
    return " ".join(termos) or consulta_ascii


def _timestamp_slug(timezone: str) -> str:
    """Gera um prefixo cronologico para ordenar notas por criacao.

    Args:
        timezone: O fuso horario a ser utilizado.

    Returns:
        String no formato YYYYMMDD-HHMMSS.
    """
    return datetime.now(ZoneInfo(timezone)).strftime("%Y%m%d-%H%M%S")


def _escapar_yaml(valor: str) -> str:
    """Escapa aspas para manter o front matter valido.

    Args:
        valor: String que sera interpolada dentro de aspas num YAML.

    Returns:
        String com aspas duplas escapadas.
    """
    return valor.replace('"', '\\"')
