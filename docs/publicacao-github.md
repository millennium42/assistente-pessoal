# Publicacao no GitHub

O repositório local ja está pronto na branch `codex/v1-assistente-pessoal`. A publicacao remota depende de login no GitHub CLI.

## 1. Fazer login

```powershell
gh auth login
```

Escolha GitHub.com e autentique com sua conta `millennium42`.

## 2. Criar repositório público e enviar a V1

Depois do login:

```powershell
.\scripts\publicar_github.ps1 -Owner millennium42 -Repo assistente-pessoal
```

O script:

- verifica se `gh` está autenticado;
- cria o repositório público se ele ainda não existir;
- adiciona ou atualiza o remote `origin`;
- envia a branch atual para o GitHub.

## 3. Conferir CI

Depois do push, abra:

```text
https://github.com/millennium42/assistente-pessoal/actions
```

O workflow deve executar:

- `uv pip install -e ".[dev]"`
- `pytest`
- `ruff check .`
- `ruff format --check .`

## Observacao importante

Nesta sessao, o GitHub CLI foi instalado, mas `gh auth status` retornou que nao ha login local. Por isso a publicacao remota nao pode ser feita automaticamente ainda.

