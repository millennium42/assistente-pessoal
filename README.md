# Assistente Pessoal

Assistente pessoal modular, open source, em Python e em pt-BR. A V1 foi pensada para ser util agora, mesmo em uma maquina simples: comandos por texto, voz push-to-talk, memoria em um vault dedicado do Obsidian, clima, noticias, lancamentos musicais e IA opcional via endpoint compativel com OpenAI.

## Decisoes da V1

- **CLI antes de interface grafica:** reduz bugs e deixa os comandos testaveis.
- **Voz push-to-talk:** evita wake word instavel e consumo constante de CPU.
- **Obsidian como memoria:** o assistente grava Markdown comum, entao voce pode ler, editar e versionar tudo.
- **SQLite FTS5 para busca:** simples, local e rebuildavel; vector DB fica para uma versao futura.
- **LLM opcional:** sem provedor configurado, o assistente ainda executa clima, noticias, musica e memoria.
- **Sem LiteLLM por enquanto:** a V1 usa um adaptador proprio pequeno para reduzir dependencia de cadeia de suprimentos.

## Requisitos

- Windows 10 ou superior.
- Python 3.12.
- `uv`.
- Git.
- FFmpeg.

Depois de instalar as ferramentas, reinicie o terminal se os comandos nao forem reconhecidos no PATH.

## Instalacao

```powershell
uv venv
uv pip install -e ".[dev]"
```

## Primeiro uso

```powershell
assistente-pessoal init
assistente-pessoal memoria salvar "Primeira memoria" "Quero estudar com revisoes curtas e frequentes."
assistente-pessoal memoria buscar "revisoes"
assistente-pessoal clima
assistente-pessoal noticias
assistente-pessoal musica
assistente-pessoal chat "o que voce consegue fazer?"
```

Para voz:

```powershell
assistente-pessoal ouvir
```

O comando `ouvir` grava por alguns segundos, transcreve com `faster-whisper` e manda o texto para o roteador de comandos.

## Configuracao

Rode `assistente-pessoal init` para criar `config.toml` e um vault dedicado em `vault/AssistentePessoal`.

Exemplo minimo:

```toml
vault_path = "vault/AssistentePessoal"

[localizacao]
cidade = "Santa Maria, RS"
latitude = -29.6868
longitude = -53.8149
timezone = "America/Sao_Paulo"

[llm]
base_url = ""
modelo = ""
api_key_env = "OPENAI_API_KEY"
```

Para usar Ollama futuramente:

```toml
[llm]
base_url = "http://localhost:11434/v1"
modelo = "llama3.2:3b"
api_key_env = "OPENAI_API_KEY"
```

## Arquitetura

- `config`: leitura e criacao da configuracao.
- `cli`: interface Typer.
- `memoria`: vault Obsidian, Markdown e indice SQLite FTS5.
- `estudos`: notas de estudo, resumos simples e perguntas de revisao.
- `noticias`: leitura de RSS/Atom.
- `clima`: Open-Meteo.
- `musica`: MusicBrainz.
- `llm`: cliente pequeno para APIs compativeis com OpenAI.
- `voz`: gravacao push-to-talk e transcricao local.
- `roteador`: decide qual modulo chamar a partir de texto livre.

Leia tambem:

- [Arquitetura da V1](docs/arquitetura.md)
- [Guia de uso](docs/uso.md)
- [Guia de contribuicao](CONTRIBUTING.md)

## Qualidade

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Todas as funcoes, classes e metodos publicos devem ter docstrings em pt-BR. Comentarios devem explicar decisoes relevantes, nao repetir mecanicamente o que cada linha faz.
