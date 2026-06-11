# Assistente Pessoal

Assistente pessoal modular, open source, em Python e em pt-BR. Esta versao combina CLI, dashboard local com `NiceGUI`, memoria em banco de dados relacional, noticias priorizadas, clima por dia, estudo, musica e LLM opcional.

## O que mudou nesta versao

- substituicao do vault do Obsidian por um banco de dados relacional SQLite;
- dashboard local com clima, noticias, notas rapidas, plano de estudos, agenda local e Google Agenda;
- noticias priorizadas em grupos dinamicos:
  1. The News
  2. Santa Maria - RS
  3. tech
  4. economia global
  5. interesses de pesquisa
- clima com `--dia hoje|amanha|segunda|...`;
- limpeza da documentacao para remover caminhos pessoais;
- revisao pratica de privacidade e LGPD.

## Requisitos

- Windows 10 ou superior
- Python 3.12
- `uv`
- Git
- FFmpeg

Se algum comando novo nao for reconhecido, abra um terminal novo.

## Instalacao

Para preparar uma maquina Windows:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Instalacao manual:

```powershell
uv venv
uv pip install -e ".[dev]"
```

Se preferir usar o executavel da venv sem ativacao:

```powershell
.\.venv\Scripts\assistente-pessoal.exe --help
```

## Primeiro uso

1. Crie a configuracao inicial:

```powershell
.\.venv\Scripts\assistente-pessoal.exe init
```

2. Confira onde o banco de dados esta armazenado:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria info
```

3. Teste os modulos basicos:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Primeira memoria" "Revisar calculo toda segunda."
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
- `assistente-pessoal estudar`
- `assistente-pessoal clima --dia amanha`
- `assistente-pessoal noticias`
- `assistente-pessoal musica`
- `assistente-pessoal agenda google-auth`
- `assistente-pessoal agenda google-listar`
- `assistente-pessoal agenda google-criar "Consulta" --data 2026-06-09 --hora 14:30`
- `assistente-pessoal chat "mensagem"`
- `assistente-pessoal ouvir`
- `assistente-pessoal gui`

## Configuracao

Estrutura resumida do `config.toml`:

```toml
db_path = "banco/AssistentePessoal/memoria.sqlite"

[localizacao]
cidade = "Santa Maria, RS"
latitude = -29.6868
longitude = -53.8149
timezone = "America/Sao_Paulo"

[google_agenda]
habilitado = false
credentials_path = "google-oauth-client.json"
token_path = ".assistente/google-calendar-token.json"
calendar_id = "primary"
max_eventos = 10
janela_dias = 7

[dashboard]
intervalo_atualizacao_segundos = 15
ttl_dolar_segundos = 15
ttl_noticias_segundos = 60
ttl_agenda_segundos = 1800
ttl_clima_segundos = 3600

[fontes.noticias]
timezone = "America/Sao_Paulo"
apenas_dia_atual = true
interesses_busca = []
prioridades = ["the_news", "santa_maria", "tech", "economia_global"]

[fontes.noticias.the_news]
habilitado = true
categoria = "" # vazio busca todas as categorias do The News

[fontes.noticias.santa_maria]
habilitado = true
modo = "midia_local"
titulo_fonte = "santa maria - midia local"
urls = [
  "https://diariosm.com.br/",
  "https://bei.net.br/plantao/",
]
palavras_chave = [
  "santa maria",
  "santa-mariense",
  "ufsm",
  "regiao central",
  "quarta colonia",
  "agudo",
  "sao sepe",
  "sao pedro do sul",
  "julio de castilhos",
  "cruz alta",
]

[fontes.noticias.tech]
habilitado = true
titulo_fonte = "tech"
rss = [
  "https://tecnoblog.net/feed/",
  "https://www.canaltech.com.br/rss/",
  "https://olhardigital.com.br/feed/",
]

[fontes.noticias.economia_global]
habilitado = true
modo = "misto"
titulo_fonte = "economia global"
rss = [
  "https://www.federalreserve.gov/feeds/press_monetary.xml",
  "https://www.federalreserve.gov/feeds/press_all.xml",
]
urls = [
  "https://www.imf.org/en/News",
  "https://www.worldbank.org/en/news",
]
```

## Armazenamento de Dados

O assistente utiliza um banco de dados relacional SQLite para gerenciar a memoria e os dados locais.

O arquivo do banco de dados ficara armazenado por padrao em `banco/AssistentePessoal/memoria.sqlite`, de acordo com o configurado em `db_path`.

Se voce quiser verificar onde o banco esta sendo armazenado:

1. rode `assistente-pessoal memoria info`
2. o comando retornara o caminho absoluto do banco de dados em uso
3. confirme se o `config.toml` que voce esta usando e o mesmo da sessao atual

## Privacidade e LGPD

- nenhuma chave de API deve ser salva no `config.toml`; use variaveis de ambiente
- o banco de dados e local, inspecionavel e apagavel por voce
- clima, noticias, musica e LLM externo enviam dados para fora da maquina quando habilitados
- logs nao devem carregar conteudo pessoal por padrao
- a Google Agenda usa OAuth local, escopo de eventos e a API oficial `calendar-json.googleapis.com`
- o arquivo de credenciais OAuth e o token local nao devem ser versionados

Leia: [docs/lgpd-privacidade.md](docs/lgpd-privacidade.md)

## Documentacao

- [docs/primeiro-uso.md](docs/primeiro-uso.md)
- [docs/uso.md](docs/uso.md)
- [docs/arquitetura.md](docs/arquitetura.md)
- [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md)
- [docs/lgpd-privacidade.md](docs/lgpd-privacidade.md)
- [docs/publicacao-github.md](docs/publicacao-github.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Qualidade

```powershell
.\scripts\verificar.ps1
```

Ou:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check .
```
