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

_SQL_UPSERT_DOCUMENTO = """
INSERT OR REPLACE INTO documentos (
    caminho,
    titulo,
    conteudo,
    pasta,
    tags,
    criado_em,
    atualizado_em
)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""


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


@dataclass(frozen=True)
class InteracaoNoticiaMemoria:
    """Representa uma noticia relevante observada pela assistente."""

    titulo: str
    link: str
    fonte: str
    grupo: str
    origem: str
    contexto: str
    registrado_em: str


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
            conexao.execute("PRAGMA foreign_keys = ON")
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
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS perfil_pessoal (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    conteudo TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS interesses_usuario (
                    interesse TEXT PRIMARY KEY,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS interacoes_noticias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    link TEXT NOT NULL,
                    fonte TEXT NOT NULL,
                    grupo TEXT NOT NULL,
                    origem TEXT NOT NULL,
                    contexto TEXT NOT NULL,
                    registrado_em TEXT NOT NULL
                )
                """
            )
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS memoria_comportamental (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    nivel_confianca TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            _sincronizar_documentos_canonicos_estruturados(conexao)

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

        with sqlite3.connect(self.db_path) as conexao:
            _salvar_documento_sqlite(
                conexao=conexao,
                caminho=caminho_str,
                titulo=titulo,
                conteudo=conteudo,
                pasta=pasta,
                tags=tags_reais,
                criado_em=agora,
                atualizado_em=agora,
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

        with sqlite3.connect(self.db_path) as conexao:
            existente = conexao.execute(
                "SELECT criado_em FROM documentos WHERE caminho = ?",
                (caminho_str,),
            ).fetchone()
            criado_em = existente[0] if existente else agora
            _salvar_documento_sqlite(
                conexao=conexao,
                caminho=caminho_str,
                titulo=titulo,
                conteudo=conteudo,
                pasta=pasta,
                tags=tags or [],
                criado_em=criado_em,
                atualizado_em=agora,
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

    def salvar_perfil_pessoal(self, conteudo: str) -> None:
        """Persiste o perfil pessoal canonico em tabela estruturada."""
        self.preparar()
        agora = _agora_iso(self.timezone)
        conteudo_limpo = conteudo.strip() or "Perfil pessoal ainda nao preenchido."
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute(
                """
                INSERT INTO perfil_pessoal (id, conteudo, atualizado_em)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conteudo = excluded.conteudo,
                    atualizado_em = excluded.atualizado_em
                """,
                (conteudo_limpo, agora),
            )

    def obter_perfil_pessoal(self) -> str:
        """Le o perfil pessoal estruturado."""
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            linha = conexao.execute("SELECT conteudo FROM perfil_pessoal WHERE id = 1").fetchone()
        return str(linha[0]) if linha and linha[0] else ""

    def substituir_interesses(self, interesses: list[str]) -> None:
        """Substitui a lista de interesses usada para personalizacao."""
        self.preparar()
        agora = _agora_iso(self.timezone)
        itens = [interesse.strip() for interesse in interesses if interesse.strip()]
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute("DELETE FROM interesses_usuario")
            conexao.executemany(
                """
                INSERT INTO interesses_usuario (interesse, criado_em, atualizado_em)
                VALUES (?, ?, ?)
                """,
                [(interesse, agora, agora) for interesse in itens],
            )

    def adicionar_interesses(self, interesses: list[str]) -> list[str]:
        """Mescla interesses inferidos com a lista atual sem perder o historico ativo."""
        atuais = self.listar_interesses()
        atuais_casefold = {interesse.casefold() for interesse in atuais}
        for interesse in interesses:
            termo = interesse.strip()
            if termo and termo.casefold() not in atuais_casefold:
                atuais.append(termo)
                atuais_casefold.add(termo.casefold())
        self.substituir_interesses(atuais)
        return atuais

    def listar_interesses(self) -> list[str]:
        """Retorna os interesses persistidos no banco estruturado."""
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            linhas = conexao.execute(
                "SELECT interesse FROM interesses_usuario ORDER BY rowid ASC"
            ).fetchall()
        return [str(linha[0]) for linha in linhas]

    def registrar_interacao_noticia(
        self,
        *,
        titulo: str,
        link: str,
        fonte: str,
        grupo: str,
        origem: str,
        contexto: str = "",
    ) -> None:
        """Armazena uma noticia observada para orientar relevancia futura."""
        self.preparar()
        agora = _agora_iso(self.timezone)
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute(
                """
                INSERT INTO interacoes_noticias (
                    titulo,
                    link,
                    fonte,
                    grupo,
                    origem,
                    contexto,
                    registrado_em
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (titulo, link, fonte, grupo, origem, contexto, agora),
            )

    def listar_interacoes_noticias(self, limite: int = 20) -> list[InteracaoNoticiaMemoria]:
        """Entrega o historico recente de noticias consideradas relevantes."""
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            linhas = conexao.execute(
                """
                SELECT titulo, link, fonte, grupo, origem, contexto, registrado_em
                FROM interacoes_noticias
                ORDER BY registrado_em DESC, id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return [
            InteracaoNoticiaMemoria(
                titulo=titulo,
                link=link,
                fonte=fonte,
                grupo=grupo,
                origem=origem,
                contexto=contexto,
                registrado_em=registrado_em,
            )
            for titulo, link, fonte, grupo, origem, contexto, registrado_em in linhas
        ]

    def registrar_comportamento(
        self, tipo: str, conteudo: str, nivel_confianca: str = "medio"
    ) -> None:
        """Registra um comportamento, habito ou preferencia para uso adaptativo."""
        self.preparar()
        agora = _agora_iso(self.timezone)
        with sqlite3.connect(self.db_path) as conexao:
            conexao.execute(
                """
                INSERT INTO memoria_comportamental (
                    tipo, conteudo, nivel_confianca, criado_em, atualizado_em
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (tipo, conteudo, nivel_confianca, agora, agora),
            )

    def listar_comportamentos(self, limite: int = 15) -> list[dict]:
        """Recupera comportamentos adaptativos mapeados recentes."""
        self.preparar()
        with sqlite3.connect(self.db_path) as conexao:
            try:
                linhas = conexao.execute(
                    """
                    SELECT tipo, conteudo, nivel_confianca FROM memoria_comportamental
                    ORDER BY atualizado_em DESC LIMIT ?
                    """,
                    (limite,),
                ).fetchall()
                return [{"tipo": t, "conteudo": c, "nivel_confianca": n} for t, c, n in linhas]
            except sqlite3.OperationalError:
                return []

    def contexto_secretaria_virtual(self, limite_noticias: int = 12) -> str:
        """Resume perfil, interesses e historico recente para a APPA."""
        perfil = self.obter_perfil_pessoal().strip() or "Nao informado."
        interesses = self.listar_interesses()
        noticias = self.listar_interacoes_noticias(limite=limite_noticias)
        linhas = [f"Perfil pessoal: {perfil}"]
        if interesses:
            linhas.append(f"Interesses atuais: {', '.join(interesses)}")
        else:
            linhas.append("Interesses atuais: nenhum interesse salvo.")
        if noticias:
            linhas.append("Noticias e sinais recentes de relevancia:")
            for noticia in noticias:
                detalhe_contexto = f" | contexto: {noticia.contexto}" if noticia.contexto else ""
                linhas.append(
                    f"- {noticia.titulo} [{noticia.grupo}] via {noticia.fonte} "
                    f"(origem: {noticia.origem}){detalhe_contexto}"
                )
        else:
            linhas.append("Noticias e sinais recentes de relevancia: nenhum registro ainda.")

        comportamentos = self.listar_comportamentos()
        if comportamentos:
            linhas.append("\nComportamentos, hábitos e preferências mapeadas:")
            for comp in comportamentos:
                linhas.append(
                    f"- [{comp['tipo']}] {comp['conteudo']} (confiança: {comp['nivel_confianca']})"
                )
        return "\n".join(linhas)

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


def _salvar_documento_sqlite(
    conexao: sqlite3.Connection,
    caminho: str,
    titulo: str,
    conteudo: str,
    pasta: str,
    tags: list[str],
    criado_em: str,
    atualizado_em: str,
) -> None:
    """Atualiza a tabela principal e mantem o FTS sincronizado."""
    tags_json = json.dumps(tags)
    conexao.execute(
        _SQL_UPSERT_DOCUMENTO,
        (caminho, titulo, conteudo, pasta, tags_json, criado_em, atualizado_em),
    )
    conexao.execute("DELETE FROM documentos_fts WHERE caminho = ?", (caminho,))
    conexao.execute(
        """
        INSERT INTO documentos_fts(titulo, caminho, conteudo)
        VALUES (?, ?, ?)
        """,
        (titulo, caminho, conteudo),
    )


def _sincronizar_documentos_canonicos_estruturados(conexao: sqlite3.Connection) -> None:
    """Sincroniza documentos canonicos antigos com as tabelas estruturadas atuais."""
    perfil = conexao.execute("SELECT conteudo FROM perfil_pessoal WHERE id = 1").fetchone()
    if not perfil or not str(perfil[0]).strip():
        documento_perfil = conexao.execute(
            "SELECT conteudo FROM documentos WHERE caminho = ?",
            ("10_memoria/perfil-pessoal.md",),
        ).fetchone()
        conteudo_perfil = (
            str(documento_perfil[0]).strip() if documento_perfil and documento_perfil[0] else ""
        )
        if conteudo_perfil:
            atualizado_em = _agora_iso("America/Sao_Paulo")
            conexao.execute(
                """
                INSERT INTO perfil_pessoal (id, conteudo, atualizado_em)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conteudo = excluded.conteudo,
                    atualizado_em = excluded.atualizado_em
                """,
                (conteudo_perfil, atualizado_em),
            )

    quantidade_interesses = conexao.execute("SELECT count(*) FROM interesses_usuario").fetchone()[0]
    if quantidade_interesses:
        return
    documento_interesses = conexao.execute(
        "SELECT conteudo FROM documentos WHERE caminho = ?",
        ("10_memoria/interesses-de-pesquisa.md",),
    ).fetchone()
    if not documento_interesses or not documento_interesses[0]:
        return
    interesses = [
        linha.removeprefix("-").strip()
        for linha in str(documento_interesses[0]).splitlines()
        if linha.strip().startswith("-")
    ]
    if not interesses:
        return
    atualizado_em = _agora_iso("America/Sao_Paulo")
    conexao.executemany(
        """
        INSERT OR IGNORE INTO interesses_usuario (interesse, criado_em, atualizado_em)
        VALUES (?, ?, ?)
        """,
        [(interesse, atualizado_em, atualizado_em) for interesse in interesses],
    )


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


def _agora_iso(timezone: str) -> str:
    """Entrega o timestamp local padronizado usado nas tabelas estruturadas."""
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")
