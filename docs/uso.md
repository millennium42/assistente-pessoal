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

Com LLM configurado, o assistente usa um endpoint compativel com Chat Completions. Sem LLM, cai em fallback local.

## Dashboard

```powershell
assistente-pessoal gui
```

O dashboard local oferece:

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
