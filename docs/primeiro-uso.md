# Guia de primeiro uso

Este guia ajuda a subir o projeto pela primeira vez sem depender de integracoes externas logo no inicio.

## 1. Prepare o ambiente

Opcao automatizada:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Opcao manual:

```powershell
uv venv
uv pip install -e ".[dev]"
```

## 2. Gere a configuracao inicial

```powershell
.\.venv\Scripts\assistente-pessoal.exe init
```

Isso cria a base minima de execucao, incluindo o `config.toml` e o banco SQLite local.

## 3. Descubra onde seus dados estao

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria info
```

Use esse comando sempre que quiser confirmar qual banco esta em uso na sessao atual.

## 4. Teste a memoria

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Primeira memoria" "Revisar estatistica na terca."
.\.venv\Scripts\assistente-pessoal.exe memoria buscar estatistica
```

## 5. Teste clima e noticias

```powershell
.\.venv\Scripts\assistente-pessoal.exe clima
.\.venv\Scripts\assistente-pessoal.exe clima --dia amanha
.\.venv\Scripts\assistente-pessoal.exe noticias
```

## 6. Abra o dashboard

```powershell
.\.venv\Scripts\assistente-pessoal.exe gui
```

O dashboard sobe primeiro e atualiza os blocos externos depois. Isso deixa a abertura mais responsiva mesmo quando clima, noticias ou agenda estiverem lentos.

## 7. Habilite o LLM apenas se quiser

Exemplo minimo no `config.toml`:

```toml
[llm]
base_url = "http://localhost:11434/v1"
modelo = "llama3.2:3b"
api_key_env = "OPENAI_API_KEY"
```

Sem essa configuracao, o comando `chat` continua disponivel com fallback local.

## 8. Configure Google Agenda de forma segura

Use um arquivo OAuth local, fora de versionamento, e mantenha o token em uma pasta local ignorada pelo Git.

Exemplo:

```toml
[google_agenda]
habilitado = true
credentials_path = "google-oauth-client.json"
token_path = ".assistente/google-calendar-token.json"
calendar_id = "primary"
max_eventos = 10
janela_dias = 7
```

Depois autentique:

```powershell
.\.venv\Scripts\assistente-pessoal.exe agenda google-auth
.\.venv\Scripts\assistente-pessoal.exe agenda google-listar
```

## 9. Problemas comuns

### A memoria parece vazia

Verifique se o `config.toml` da sessao atual aponta para o banco que voce espera e confirme isso com `memoria info`.

### O dashboard abre sem noticias

Isso normalmente significa uma destas situacoes:

- as fontes do dia ainda nao publicaram
- algum portal mudou o HTML
- a rede falhou em uma das consultas

### O chat diz que nao ha LLM configurado

Esse comportamento e esperado quando `llm.base_url` ou `llm.modelo` estao vazios.
