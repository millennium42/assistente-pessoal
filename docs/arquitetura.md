# Arquitetura

O projeto foi organizado para manter responsabilidades pequenas, configuracao previsivel e degradacao graciosa quando uma integracao externa falha.

## Principios

- local-first para memoria e configuracao sensivel
- integracoes externas opt-in
- baixo acoplamento entre interface, casos de uso e adaptadores
- falhas isoladas por fonte
- paths resolvidos a partir do `config.toml`

## Modulos principais

- `config`: leitura tipada da configuracao
- `core_paths`: resolucao segura de caminhos
- `core_datas`: datas, timezone e linguagem natural simples para dias
- `memoria`: persistencia SQLite, FTS5 e dados canonicos do usuario
- `clima`: cliente Open-Meteo
- `fontes_noticias`: adaptadores de The News, RSS, HTML e interesses
- `noticias`: orquestracao, prioridade e ordenacao cronologica
- `painel`: snapshots usados pela GUI
- `gui`: dashboard NiceGUI
- `agenda_google`: OAuth local, leitura e criacao de eventos
- `llm`: cliente para provedores compativeis com Chat Completions
- `cli`: comandos Typer

## Fluxo de dados

1. `config.toml` define caminhos e integracoes habilitadas.
2. `Memoria` prepara o SQLite e migra dados canonicos antigos para tabelas estruturadas.
3. `painel` monta snapshots a partir de memoria, clima, noticias e agenda.
4. `gui` renderiza o estado inicial rapidamente e atualiza os dados depois.
5. `cli` reutiliza os mesmos servicos centrais para manter comportamento consistente.

## Dados persistidos

- notas e documentos canonicos em SQLite
- perfil pessoal e interesses em tabelas estruturadas
- indice textual FTS5 para busca
- token local do Google em pasta ignorada

## Fronteiras de privacidade

- `config.toml` aceita `llm.api_key`, mas o caminho mais seguro continua sendo `llm.api_key_env`
- tokens locais ficam fora de versionamento
- LLM e APIs externas so recebem dados quando o modulo correspondente e usado
- logs devem permanecer sem conteudo pessoal por padrao
