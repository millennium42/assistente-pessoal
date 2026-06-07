# Guia de contribuicao

Obrigado por querer melhorar o Assistente Pessoal. Este projeto e escrito em pt-BR por escolha deliberada: a documentacao, os comandos, as mensagens de erro e as docstrings devem conversar com quem vai usar o assistente no dia a dia.

## Ambiente local

```powershell
uv venv
uv pip install -e ".[dev]"
```

Se `uv`, `python`, `git` ou `ffmpeg` nao forem reconhecidos logo apos instalar, reinicie o terminal. No Windows, os instaladores costumam atualizar o PATH apenas para novas sessoes.

## Padroes de codigo

- Toda funcao, metodo e classe deve ter docstring em pt-BR.
- Comentarios devem explicar por que uma decisao existe, nao repetir o que a linha ja diz.
- Modulos devem ficar pequenos e com responsabilidade clara.
- Integracoes externas devem ter timeout e testes com mock.
- O assistente nao deve quebrar quando o LLM nao estiver configurado.

## Antes de abrir PR

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Filosofia tecnica

A V1 prioriza confiabilidade e modularidade sobre espetaculo. Ideias como wake word, interface grafica, RAG vetorial e TTS neural melhor devem entrar somente quando a base local estiver simples de usar e facil de testar.

