# Publicacao no GitHub

O repositorio publico da V1 esta em:

```text
https://github.com/millennium42/assistente-pessoal
```

Use este guia quando quiser autenticar o GitHub CLI, configurar o remote ou reenviar a branch atual.

## 1. Fazer login

Se o GitHub CLI ainda nao estiver instalado:

```powershell
.\scripts\bootstrap_windows.ps1
```

Depois autentique:

```powershell
gh auth login
```

Escolha GitHub.com e autentique com sua conta `millennium42`.

## 2. Criar repositorio publico e enviar a V1

Depois do login:

```powershell
.\scripts\publicar_github.ps1 -Owner millennium42 -Repo assistente-pessoal
```

O script:

- verifica se `gh` esta autenticado;
- cria o repositorio publico se ele ainda nao existir;
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

## Estado atual da V1

- Repositorio publico: `millennium42/assistente-pessoal`.
- Branch padrao: `main`.
- CI configurado em `.github/workflows/ci.yml`.

