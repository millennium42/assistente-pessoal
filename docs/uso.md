# Guia de uso

Se esta for sua primeira execucao, comece por [primeiro-uso.md](primeiro-uso.md).

Se a venv nao estiver ativada, troque `assistente-pessoal` por `.\.venv\Scripts\assistente-pessoal.exe`.

## Inicializacao

```powershell
assistente-pessoal init
assistente-pessoal memoria info
```

## Memoria

```powershell
assistente-pessoal memoria salvar "Plano de estudo" "Revisar calculo toda segunda."
assistente-pessoal memoria buscar calculo
assistente-pessoal memoria reindexar
assistente-pessoal memoria info
```

## Clima

```powershell
assistente-pessoal clima
assistente-pessoal clima --dia amanha
assistente-pessoal clima --dia sexta
```

Se voce pedir um dia da semana que ja passou, o sistema usa a proxima ocorrencia.

## Noticias

```powershell
assistente-pessoal noticias
```

Prioridade padrao do feed:

1. The News
2. Santa Maria
3. tech
4. economia global

## Chat

```powershell
assistente-pessoal chat "o que voce consegue fazer?"
```

Com `llm.api_key` e `llm.modelo = "gemini-3.1-flash-lite"` no `config.toml`, o chat usa
Gemini diretamente. Se `api_key` estiver vazio, o app tenta a variavel definida em
`llm.api_key_env`, como `GEMINI_API_KEY`.

Sem Gemini operacional, a APPA entra em modo bloqueado.

## Dashboard

```powershell
assistente-pessoal gui
```

O dashboard local oferece:

- aba `Insights` como visao principal
- chat operacional da APPA dentro de `Insights`
- card de anotacoes alimentado pelo chat
- resumo de agenda, noticias e clima gerado pelo Gemini
- cache de insights controlado por `dashboard.ttl_insights_segundos`
- clima atual e previsao
- noticias priorizadas
- interesses e perfil pessoal editaveis pela interface
- Google Agenda

## Google Agenda

```powershell
assistente-pessoal agenda google-auth
assistente-pessoal agenda google-listar
assistente-pessoal agenda google-criar "Consulta" --data 2026-06-15 --hora 14:30 --duracao 45
```

Mantenha o arquivo OAuth e o token local fora de versionamento.
