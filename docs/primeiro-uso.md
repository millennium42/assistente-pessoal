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

O caminho mais direto hoje e preencher o bloco `[llm]` com a chave do Gemini e um
modelo estavel.

Exemplo minimo no `config.toml`:

```toml
[llm]
modelo = "gemini-3.5-flash"
api_key = "SUA_CHAVE_GEMINI"
api_key_env = "GEMINI_API_KEY"
```

Se preferir nao gravar a chave no arquivo, deixe `api_key` vazio e defina apenas
`GEMINI_API_KEY` no ambiente. O app tenta `llm.api_key` primeiro e depois usa
`llm.api_key_env`.

`gemini-3.5-flash` e o modelo estavel recomendado para producao. Os modelos
`gemini-2.0-flash` foram descontinuados em 1 de junho de 2026.

Se nenhuma das trilhas estiver configurada, o comando `chat` cai no fallback local.

## 8. Configure Google Agenda de forma segura

Use um arquivo OAuth local, fora de versionamento, e mantenha o token em uma pasta local tambem fora de versionamento.

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

Esse comportamento so e esperado quando as duas trilhas estao ausentes:

- `llm.api_key` esta vazio e `GEMINI_API_KEY` nao esta definida
- `llm.base_url` ou `llm.modelo` estao vazios para a trilha Chat Completions

### O chat avisa que o Gemini atingiu o limite de uso

Quando a API responde `429 Too Many Requests`, o app mostra uma mensagem amigavel
em vez do traceback bruto e aguarda alguns minutos antes de insistir de novo.

Se isso acontecer com frequencia, revise:

- se a chave tem cota ativa no projeto Google AI Studio
- se o modelo configurado ainda esta disponivel
- se o dashboard esta fazendo chamadas repetidas demais por falta de cache
