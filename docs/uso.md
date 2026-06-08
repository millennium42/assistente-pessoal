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
assistente-pessoal noticias --limite 5
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

Os blocos de planejamento escrevem em:

- `60_planejamento/plano-estudos.md`
- `61_agenda_local/agenda-local.md`
