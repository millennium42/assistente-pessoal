"""Testes da memoria Markdown e do indice SQLite."""

from pathlib import Path

from assistente_pessoal.memoria import MemoriaObsidian, normalizar_consulta_fts, slugificar


def test_salvar_e_buscar_memoria(tmp_path: Path) -> None:
    """Salva uma nota e encontra o conteudo pelo indice FTS5."""
    memoria = MemoriaObsidian(tmp_path / "vault")

    caminho = memoria.salvar_nota("Revisao de calculo", "Integrais pedem pratica diaria.")
    resultados = memoria.buscar("integrais")

    assert caminho.exists()
    assert resultados
    assert resultados[0].titulo == "Revisao de calculo"


def test_reindexar_memorias(tmp_path: Path) -> None:
    """Reconstrui o indice depois de salvar notas no vault."""
    memoria = MemoriaObsidian(tmp_path / "vault")
    memoria.salvar_nota("Fisica", "Energia mecanica e conservacao.")

    quantidade = memoria.reindexar()

    assert quantidade == 1
    assert memoria.buscar("energia")


def test_listar_e_apagar_memoria(tmp_path: Path) -> None:
    """Lista notas recentes e apaga apenas arquivos dentro do vault."""
    memoria = MemoriaObsidian(tmp_path / "vault")
    caminho = memoria.salvar_nota("Nota local", "Conteudo local.")

    notas = memoria.listar_notas()
    apagado = memoria.apagar_nota(caminho)

    assert notas[0].titulo == "Nota local"
    assert apagado is True
    assert not caminho.exists()


def test_slugificar_em_pt_br() -> None:
    """Remove acentos e caracteres problematicos de nomes de arquivo."""
    assert slugificar("Ol\u00e1, C\u00e1lculo 1!") == "ola-calculo-1"


def test_normalizar_consulta_fts() -> None:
    """Remove operadores que poderiam quebrar a consulta FTS."""
    assert normalizar_consulta_fts('"calculo"* OR') == "calculo OR"
