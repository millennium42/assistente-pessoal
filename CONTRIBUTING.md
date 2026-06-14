# Guia de contribuicao

O projeto e mantido em pt-BR por escolha de produto. Documentacao, mensagens e exemplos devem continuar claros para quem usa o assistente no dia a dia.

## Ambiente local

```powershell
uv venv
uv pip install -e ".[dev]"
```

## Boas praticas

- escreva docstrings curtas e uteis
- prefira modulos pequenos e responsabilidades claras
- trate integracoes externas com timeout e falha graciosa
- mantenha segredos fora do codigo e dos arquivos versionados
- preserve fallback local quando um LLM nao estiver configurado

## Validacao antes de propor mudancas

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Direcao tecnica

A linha atual do projeto prioriza confiabilidade, privacidade, legibilidade e iteracao local rapida. Novas capacidades devem reforcar essa base, e nao enfraquece-la.
