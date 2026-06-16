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

Com `llm.api_key` e `llm.modelo = "gemini-3.5-flash"` no `config.toml`, o chat usa
Gemini diretamente. Se `api_key` estiver vazio, o app tenta a variavel definida em
`llm.api_key_env`, como `GEMINI_API_KEY`.

`llm.base_url` continua disponivel para endpoints compativeis com Chat Completions.
Sem nenhuma configuracao valida, o comando cai em fallback local.

## Dashboard

```powershell
assistente-pessoal gui
```

O dashboard local oferece:

- aba `Insights` como visao principal
- resumo de agenda, noticias e clima com apoio do Gemini quando disponivel
- clima atual e previsao
- noticias priorizadas
- nota rapida
- plano de estudos
- agenda local
- Google Agenda

Modos visuais:

- `Limpa`: foco em leitura rapida
- `Detalhada`: foco em operacao e contexto

## Google Agenda

```powershell
assistente-pessoal agenda google-auth
assistente-pessoal agenda google-listar
assistente-pessoal agenda google-criar "Consulta" --data 2026-06-15 --hora 14:30 --duracao 45
```

Mantenha o arquivo OAuth e o token local fora de versionamento.
