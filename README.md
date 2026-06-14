# Assistente Pessoal 0.2.1

Assistente pessoal local-first em Python, com interface em pt-BR, dashboard NiceGUI, memoria em SQLite, noticias priorizadas, clima, agenda e integracao opcional com LLM.

## Visao geral

Esta versao `0.2.1` marca a v2 do alpha: a base continua simples de executar localmente, mas agora com uma estrutura mais consistente para memoria, painel, privacidade e extensao por IA.

Principais capacidades:

- CLI para operacoes rapidas de memoria, clima, noticias, agenda e chat.
- Dashboard local com modos visual `Limpa` e `Detalhada`.
- Memoria persistente em SQLite com busca textual por FTS5.
- Noticias organizadas por prioridades e interesses do usuario.
- Integracao opcional com LLM compativel com Chat Completions.
- Integracao opcional com Google Agenda via OAuth local.

## Arquitetura em uma frase

Uma aplicacao Python modular que privilegia dados locais, falhas isoladas por integracao e configuracao previsivel.

Leia mais em [docs/arquitetura.md](docs/arquitetura.md).

## Requisitos

- Windows 10 ou superior
- Python 3.12
- `uv`
- FFmpeg

## Instalacao

Preparacao automatizada:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Preparacao manual:

```powershell
uv venv
uv pip install -e ".[dev]"
```

## Inicio rapido

1. Gere a configuracao inicial:

```powershell
.\.venv\Scripts\assistente-pessoal.exe init
```

2. Confira o banco efetivo:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria info
```

3. Faça um smoke test funcional:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Primeira memoria" "Revisar estatistica na segunda."
.\.venv\Scripts\assistente-pessoal.exe clima --dia amanha
.\.venv\Scripts\assistente-pessoal.exe noticias
.\.venv\Scripts\assistente-pessoal.exe gui
```

Guia detalhado: [docs/primeiro-uso.md](docs/primeiro-uso.md)

## Comandos principais

- `assistente-pessoal init`
- `assistente-pessoal memoria salvar`
- `assistente-pessoal memoria buscar`
- `assistente-pessoal memoria reindexar`
- `assistente-pessoal memoria info`
- `assistente-pessoal clima --dia amanha`
- `assistente-pessoal noticias`
- `assistente-pessoal chat "mensagem"`
- `assistente-pessoal gui`
- `assistente-pessoal agenda google-auth`
- `assistente-pessoal agenda google-listar`
- `assistente-pessoal agenda google-criar "Consulta" --data 2026-06-15 --hora 14:30`

## Configuracao

O projeto usa `config.toml` como fonte principal de configuracao. Um exemplo atualizado esta em [config.example.toml](config.example.toml).

Pontos importantes:

- `db_path` define onde a memoria local sera persistida.
- `llm.base_url` e `llm.modelo` habilitam o chat com um provedor compativel.
- `google_agenda.credentials_path` deve apontar para um arquivo OAuth local fora de versionamento.
- chaves e tokens devem ficar em variaveis de ambiente ou em arquivos locais ignorados pelo Git.

Variaveis de ambiente suportadas:

```dotenv
OPENAI_API_KEY=
ASSISTENTE_CONFIG=config.toml
```

## Privacidade e LGPD

O repositório foi organizado para reforçar um modelo local-first e opt-in para integracoes externas.

- dados pessoais e memoria ficam em SQLite local, inspecionavel e apagavel
- nenhuma chave deve ser salva em `config.toml`
- LLM, noticias, clima, musica e Google Agenda so enviam dados para fora quando configurados ou usados
- arquivos OAuth e tokens locais nao devem ser versionados

Leitura dedicada: [docs/lgpd-privacidade.md](docs/lgpd-privacidade.md)

## Documentacao

- [docs/primeiro-uso.md](docs/primeiro-uso.md)
- [docs/uso.md](docs/uso.md)
- [docs/arquitetura.md](docs/arquitetura.md)
- [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md)
- [docs/lgpd-privacidade.md](docs/lgpd-privacidade.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Qualidade

Verificacao rapida:

```powershell
.\scripts\verificar.ps1
```

Ou manualmente:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check .
```
