"""Protege a documentacao contra exposicao de caminhos pessoais."""

from pathlib import Path


def test_docs_nao_expoem_caminhos_pessoais() -> None:
    """Evita reintroduzir exemplos com nomes de usuario ou pastas pessoais reais."""
    raiz = Path(__file__).resolve().parents[1]
    textos = []
    for caminho in [raiz / "README.md", *(raiz / "docs").glob("*.md")]:
        textos.append(caminho.read_text(encoding="utf-8"))
    combinado = "\n".join(textos)
    assert "OneDrive" not in combinado
    assert "D:\\milla" not in combinado
    assert "C:\\Users\\" not in combinado
