# Segredos e Credenciais

Segredos nunca devem entrar em Markdown, TOML versionado, SQLite, logs ou frontend.

## Permitido

- Variaveis de ambiente.
- Secret manager externo em deploy futuro.

## Proibido

- `.env` commitado.
- `config.toml` com chave real.
- `googleAgenda.json` commitado.
- Token OAuth no vault.
- Print de header Authorization.
- Chave enviada ao renderer Tauri.

## Variaveis previstas

```env
OPENAI_API_KEY=
ASSISTENTE_CONFIG=config.toml
```

## Rotacao

Rotacione imediatamente quando:

- uma chave apareceu em arquivo local nao ignorado;
- uma chave foi colada em prompt;
- um token foi incluido em log;
- um arquivo OAuth foi enviado a outro lugar;
- o repositorio ficou publico com segredo.

## CI

O CI roda Gitleaks. Localmente, use:

```powershell
uv run detect-secrets scan --all-files
```
