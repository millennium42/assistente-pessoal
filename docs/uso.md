# Guia de uso

Se esta for sua primeira vez com o projeto, comece por [primeiro-uso.md](primeiro-uso.md). Este arquivo e a referencia curta dos comandos.

Se a venv nao estiver ativada, troque `assistente-pessoal` por `.\.venv\Scripts\assistente-pessoal.exe`.

## Inicializar

```powershell
assistente-pessoal init
assistente-pessoal memoria info
```

O segundo comando confirma o vault efetivo, o que ajuda quando as notas nao aparecem no Obsidian.

## Memoria

```powershell
assistente-pessoal memoria salvar "Plano de estudo" "Revisar calculo toda segunda."
assistente-pessoal memoria buscar calculo
assistente-pessoal memoria reindexar
assistente-pessoal memoria info
```

## Estudo

```powershell
assistente-pessoal estudar "Algebra linear" --conteudo "Vetores, bases e transformacoes."
assistente-pessoal estudar "Fisica 1" --arquivo ".\resumo-aula.md"
```

## Clima

```powershell
assistente-pessoal clima
assistente-pessoal clima --dia amanha
assistente-pessoal clima --dia sexta
```

Regra: se voce pedir um dia que ja passou na semana, o sistema assume a proxima ocorrencia.

## Noticias

```powershell
assistente-pessoal noticias
```

Prioridade atual:

1. The News
2. Santa Maria - RS
3. tech
4. economia global

O filtro considera apenas noticias publicadas no dia atual do fuso configurado.

## Musica

```powershell
assistente-pessoal musica
```

Edite `fontes.artistas` no `config.toml` para personalizar a busca.

## Chat

```powershell
assistente-pessoal chat "o que voce consegue fazer?"
```

Sem LLM configurado, o comando mostra fallback local.

## Voz

```powershell
assistente-pessoal ouvir
```

## Dashboard grafico

```powershell
assistente-pessoal gui
```

O dashboard abre localmente no navegador e mostra:

- clima
- noticias
- nota rapida
- plano de estudos
- agenda local
- Google Agenda

Os blocos de planejamento escrevem em:

- `60_planejamento/plano-estudos.md`
- `61_agenda_local/agenda-local.md`

## Google Agenda

1. Ative a Google Calendar API no projeto do Google Cloud:

[Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?hl=pt-br)

2. Crie um client OAuth de aplicativo desktop no Google Cloud.
3. Baixe o JSON e coloque no caminho configurado em `google_agenda.credentials_path`.
4. Ative a integracao no `config.toml`:

```toml
[google_agenda]
habilitado = true
credentials_path = "google-oauth-client.json"
token_path = ".assistente/google-calendar-token.json"
calendar_id = "primary"
max_eventos = 10
janela_dias = 7
```

5. Autentique:

```powershell
assistente-pessoal agenda google-auth
```

6. Liste os proximos eventos:

```powershell
assistente-pessoal agenda google-listar
```

7. Crie um evento:

```powershell
assistente-pessoal agenda google-criar "Consulta" --data 2026-06-09 --hora 14:30 --duracao 45
```

O dashboard tambem tem um bloco "Adicionar evento" dentro de Google Agenda.
Se o token tiver sido criado com permissao antiga, rode `assistente-pessoal agenda google-auth`
novamente para conceder o escopo de eventos.
