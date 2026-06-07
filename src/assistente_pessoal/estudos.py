"""Ferramentas simples de estudo apoiadas pela memoria do Obsidian."""

from __future__ import annotations

from pathlib import Path

from assistente_pessoal.llm import ClienteLLM
from assistente_pessoal.memoria import MemoriaObsidian


def criar_nota_estudo(
    memoria: MemoriaObsidian,
    tema: str,
    conteudo: str,
    llm: ClienteLLM | None = None,
    quantidade_perguntas: int = 5,
) -> Path:
    """Cria uma nota de estudo com resumo e perguntas de revisao."""
    resumo = gerar_resumo(tema, conteudo, llm)
    perguntas = gerar_perguntas(tema, conteudo, quantidade_perguntas, llm)
    markdown = f"""## Resumo

{resumo}

## Perguntas de revisao

{perguntas}

## Material bruto

{conteudo.strip()}
"""
    return memoria.salvar_nota(
        titulo=f"Estudo - {tema}",
        conteudo=markdown,
        pasta="20_estudos",
        tags=["estudo", "revisao"],
    )


def gerar_resumo(tema: str, conteudo: str, llm: ClienteLLM | None = None) -> str:
    """Gera um resumo via LLM quando disponivel ou usa heuristica local."""
    if llm and llm.disponivel():
        resposta = llm.gerar(
            mensagem=(
                f"Resuma em pt-BR, em ate 8 linhas, o material sobre {tema}. "
                "Use linguagem clara para revisao de faculdade."
            ),
            contexto=conteudo,
        )
        if resposta:
            return resposta.texto
    return resumo_local(conteudo)


def gerar_perguntas(
    tema: str,
    conteudo: str,
    quantidade: int,
    llm: ClienteLLM | None = None,
) -> str:
    """Gera perguntas de revisao via LLM ou cria perguntas genericas uteis."""
    if llm and llm.disponivel():
        resposta = llm.gerar(
            mensagem=(
                f"Crie {quantidade} perguntas de revisao em pt-BR sobre {tema}. "
                "Prefira perguntas que testem compreensao, nao memorizacao vazia."
            ),
            contexto=conteudo,
        )
        if resposta:
            return resposta.texto
    linhas = [
        f"1. Qual e a ideia central de {tema}?",
        f"2. Quais conceitos de {tema} eu preciso definir sem consultar material?",
        f"3. Onde {tema} aparece em exemplos praticos?",
        f"4. Quais erros comuns eu devo evitar ao estudar {tema}?",
        f"5. Como eu explicaria {tema} em voz alta para outra pessoa?",
    ]
    return "\n".join(linhas[:quantidade])


def resumo_local(conteudo: str, limite_linhas: int = 6) -> str:
    """Produz um resumo local simples quando nao ha LLM configurado."""
    linhas = [linha.strip() for linha in conteudo.splitlines() if linha.strip()]
    if not linhas:
        return "Sem conteudo suficiente para resumir."
    return "\n".join(f"- {linha}" for linha in linhas[:limite_linhas])
