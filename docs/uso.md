# Guia de uso da V1

Se esta for sua primeira vez com o projeto, comece pelo [Guia de primeiro uso](primeiro-uso.md). Este arquivo aqui e uma referencia mais curta dos comandos.

Se a venv nao estiver ativada, troque `assistente-pessoal` por `.\.venv\Scripts\assistente-pessoal.exe` em qualquer exemplo abaixo.

## Inicializar

Se a maquina ainda nao tiver Python, uv, Git, FFmpeg e GitHub CLI:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Se voce so quiser conferir o ambiente:

```powershell
.\scripts\bootstrap_windows.ps1 -SomenteVerificar
```

```powershell
assistente-pessoal init
```

Isso cria `config.toml` e prepara o vault em `vault/AssistentePessoal`.

Para escolher outro local:

```powershell
assistente-pessoal init --vault "D:\Notas\AssistentePessoal"
```

## Memoria

Salvar:

```powershell
assistente-pessoal memoria salvar "Plano de estudo" "Revisar calculo toda segunda."
```

Buscar:

```powershell
assistente-pessoal memoria buscar calculo
```

Reindexar:

```powershell
assistente-pessoal memoria reindexar
```

## Estudo

Criar nota a partir de texto:

```powershell
assistente-pessoal estudar "Algebra linear" --conteudo "Vetores, bases, matrizes e transformacoes lineares."
```

Criar nota a partir de arquivo:

```powershell
assistente-pessoal estudar "Fisica 1" --arquivo ".\resumo-aula.md"
```

Sem LLM, o resumo e simples. Com LLM configurado, o assistente gera resumo e perguntas melhores.

## Clima

```powershell
assistente-pessoal clima
```

A localizacao vem de `config.toml`.

## Noticias

```powershell
assistente-pessoal noticias --limite 5
```

Por padrao, as noticias priorizam The News tecnologia e complementam com RSS tech. As fontes RSS ficam em `fontes.rss` no `config.toml`, e `incluir_the_news_tecnologia = true` controla a fonte do The News.

O filtro usa apenas noticias publicadas no dia atual do fuso `localizacao.timezone`.

Para priorizar assuntos que voce considera relevantes, edite:

```toml
[fontes]
assuntos_interesse = [
  "inteligencia artificial",
  "faculdade",
  "mercado",
]
```

Na GUI, o painel carrega 100 noticias inicialmente e permite carregar mais. Ao abrir ou salvar uma noticia, o app cria uma nota em `40_noticias` no Obsidian com trecho, categoria, tags e links internos para materias clicadas anteriormente com termos em comum.

## Google Agenda

Coloque `googleAgenda.json` na raiz do projeto ou configure `GOOGLE_CALENDAR_CREDENTIALS_FILE`.

Na GUI, conecte a agenda pelo card `Google Agenda`. Depois disso, o dashboard lista eventos futuros e pode criar novos eventos pelo app usando a API oficial.

## Musica

Edite `config.toml`:

```toml
[fontes]
artistas = [
  "Radiohead",
  "Milton Nascimento",
]
```

Depois rode:

```powershell
assistente-pessoal musica
```

## Chat

Sem LLM:

```powershell
assistente-pessoal chat "o que voce consegue fazer?"
```

Com Ollama, exemplo:

```toml
[llm]
base_url = "http://localhost:11434/v1"
modelo = "llama3.2:3b"
api_key_env = "OPENAI_API_KEY" # pragma: allowlist secret
```

O valor da chave pode ficar vazio para Ollama; o cliente envia um placeholder quando necessario.

## Voz

```powershell
assistente-pessoal ouvir
```

O assistente grava pelo tempo configurado em `voz.duracao_segundos`, transcreve e executa o texto detectado.

Exemplos de frases:

- "qual e o clima?"
- "buscar calculo"
- "memorizar revisar algebra linear"
- "noticias"
- "lancamentos de musica"
