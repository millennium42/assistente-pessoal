# Guia de primeiro uso

Este guia foi reescrito para duas coisas que ficaram muito importantes nesta versao:

1. saber onde o banco de dados esta sendo armazenado
2. começar a usar o dashboard sem depender de integrações externas

## 1. Instale e ative o ambiente

Se estiver usando o bootstrap:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Se estiver fazendo manualmente:

```powershell
uv venv
uv pip install -e ".[dev]"
```

## 2. Crie a configuracao

```powershell
.\.venv\Scripts\assistente-pessoal.exe init
```

Isso cria:

- `config.toml`
- um banco de dados em `banco/AssistentePessoal/memoria.sqlite`

## 3. Descubra o banco de dados efetivo

Este passo e importante para saber onde seus dados estao sendo salvos:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria info
```

Verifique o caminho absoluto do banco de dados na resposta do comando.

## 4. Teste a memoria

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Primeira memoria" "Revisar estatistica na terca."
.\.venv\Scripts\assistente-pessoal.exe memoria buscar estatistica
```

## 5. Teste o clima

```powershell
.\.venv\Scripts\assistente-pessoal.exe clima
.\.venv\Scripts\assistente-pessoal.exe clima --dia amanha
.\.venv\Scripts\assistente-pessoal.exe clima --dia sexta
```

## 6. Teste as noticias

```powershell
.\.venv\Scripts\assistente-pessoal.exe noticias
```

Prioridade atual:

1. The News
2. Santa Maria - RS
3. tech
4. economia global

Regra importante: so entram noticias do dia atual no fuso configurado.

## 7. Abra o dashboard

```powershell
.\.venv\Scripts\assistente-pessoal.exe gui
```

Abra a URL informada no terminal. O painel tem:

- clima
- noticias
- nota rapida
- plano de estudos
- agenda local
- Google Agenda

Quando voce salvar:

- o plano de estudos e a agenda local sao atualizados de forma isolada no banco de dados

## 8. Configurar LLM opcional

No `config.toml`:

```toml
[llm]
base_url = "http://localhost:11434/v1"
modelo = "llama3.2:3b"
api_key_env = "OPENAI_API_KEY"
```

Se usar um servidor local compativel, o chat melhora sem mudar o restante do projeto.

## 9. Integrar Google Agenda

Primeiro, ative a Google Calendar API no projeto do Google Cloud:

[Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?hl=pt-br)

No `config.toml`:

```toml
[google_agenda]
habilitado = true
credentials_path = "google-oauth-client.json"
token_path = ".assistente/google-calendar-token.json"
calendar_id = "primary"
max_eventos = 10
janela_dias = 7
```

Depois de baixar o arquivo OAuth do Google Cloud para `credentials_path`:

```powershell
.\.venv\Scripts\assistente-pessoal.exe agenda google-auth
.\.venv\Scripts\assistente-pessoal.exe agenda google-listar
.\.venv\Scripts\assistente-pessoal.exe agenda google-criar "Consulta" --data 2026-06-09 --hora 14:30
```

Quando a integracao estiver autenticada, o dashboard mostra os proximos eventos e permite
criar eventos no calendario configurado. Se o token foi criado antes da criacao de eventos,
rode `agenda google-auth` novamente.

## 10. Problemas comuns

### A memoria nao aparece ou nao e encontrada

Quase sempre e um destes casos:

1. o banco de dados que voce esta acessando nao e o mesmo que o assistente esta modificando (veja `memoria info`)
2. o `config.toml` usado no terminal nao e o mesmo que voce acha que esta usando

### O dashboard abre, mas sem noticias

Isso pode acontecer quando:

- as fontes do dia ainda nao publicaram
- uma fonte local mudou o HTML
- a sua rede bloqueou uma das consultas

The News, RSS e HTML local falham de forma isolada; uma fonte ruim nao deveria derrubar todo o painel.

### O chat responde que nao ha LLM

Isso e esperado quando `base_url` e `modelo` estao vazios.
