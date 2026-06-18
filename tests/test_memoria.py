"""Testes da memoria Markdown e do indice SQLite."""

from pathlib import Path

from assistente_pessoal.memoria import Memoria, normalizar_consulta_fts, slugificar


def test_salvar_e_buscar_memoria(tmp_path: Path) -> None:
    """Salva uma nota e encontra o conteudo pelo indice FTS5."""
    memoria = Memoria(tmp_path / "banco")

    caminho = memoria.salvar_nota("Revisao de calculo", "Integrais pedem pratica diaria.")
    resultados = memoria.buscar("integrais")

    assert caminho.as_posix().startswith("10_memoria/")
    assert resultados
    assert resultados[0].titulo == "Revisao de calculo"


def test_reindexar_memorias(tmp_path: Path) -> None:
    """Reconstrui o indice depois de salvar notas no banco."""
    memoria = Memoria(tmp_path / "banco")
    memoria.salvar_nota("Fisica", "Energia mecanica e conservacao.")

    quantidade = memoria.reindexar()

    assert quantidade == 1
    assert memoria.buscar("energia")


def test_slugificar_em_pt_br() -> None:
    """Remove acentos e caracteres problematicos de nomes de arquivo."""
    assert slugificar("Olá, Cálculo 1!") == "ola-calculo-1"


def test_normalizar_consulta_fts() -> None:
    """Remove operadores que poderiam quebrar a consulta FTS."""
    assert normalizar_consulta_fts('"cálculo"* OR') == "calculo OR"


def test_salvar_documento_fixo(tmp_path: Path) -> None:
    """Mantem documentos canonicos em caminhos estaveis dentro do banco."""
    memoria = Memoria(tmp_path / "banco")

    caminho = memoria.salvar_documento_fixo(
        nome_arquivo="planejamento.md",
        conteudo="Prova de algebra na quarta.",
        pasta="61_planejamento",
        titulo="Planejamento",
    )

    assert caminho.name == "planejamento.md"
    assert "Prova de algebra" in memoria.ler_documento_fixo("61_planejamento", "planejamento.md")


def test_memoria_structurada_para_secretaria_virtual(tmp_path: Path) -> None:
    """Mantem perfil, interesses e noticias relevantes em tabelas SQLite proprias."""
    memoria = Memoria(tmp_path / "banco")

    memoria.salvar_perfil_pessoal("Sou professora e prefiro tarefas pela manha.")
    memoria.substituir_interesses(["ia", "educacao"])
    memoria.registrar_interacao_noticia(
        titulo="Nova politica para educacao digital",
        link="https://noticias.test/educacao-digital",
        fonte="Fonte Teste",
        grupo="interesses",
        origem="clique",
        contexto="usuario abriu a noticia",
    )

    contexto = memoria.contexto_secretaria_virtual()

    assert "professora" in memoria.obter_perfil_pessoal()
    assert memoria.listar_interesses() == ["ia", "educacao"]
    assert memoria.listar_interacoes_noticias(limite=1)[0].origem == "clique"
    assert "educacao digital" in contexto.lower()


def test_sincronizar_documentos_canonicos_para_tabelas_estruturadas(tmp_path: Path) -> None:
    """Sincroniza perfil e interesses canonicos durante a preparacao."""
    memoria = Memoria(tmp_path / "banco")
    memoria.salvar_documento_fixo(
        nome_arquivo="perfil-pessoal.md",
        conteudo="Prefiro compromissos pela manha.",
        pasta="10_memoria",
        titulo="Perfil pessoal",
    )
    memoria.salvar_documento_fixo(
        nome_arquivo="interesses-de-pesquisa.md",
        conteudo="- ia\n- educacao\n",
        pasta="10_memoria",
        titulo="Interesses de pesquisa",
    )

    assert memoria.obter_perfil_pessoal() == "Prefiro compromissos pela manha."
    assert memoria.listar_interesses() == ["ia", "educacao"]
