# Arquitetura

O projeto foi organizado para manter responsabilidades pequenas, configuracao previsivel e um fluxo claro entre coleta local de dados e decisao centralizada no Gemini.

## Principios

- local-first para memoria e configuracao sensivel
- Gemini obrigatorio para a camada cognitiva
- Google Agenda como integracao opt-in
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
- `painel`: snapshots usados pela GUI com processamento 100% LLM
- `gui`: dashboard NiceGUI
- `agenda_google`: OAuth local, leitura e criacao de eventos
- `llm`: thin-wrapper que delega respostas ao Gemini
- `cli`: comandos Typer

## Fluxo de dados

1. `config.toml` define caminhos, Gemini e integracoes habilitadas.
2. `Memoria` prepara o SQLite e migra dados canonicos antigos para tabelas estruturadas.
3. `painel` monta snapshots a partir de memoria, clima, noticias e agenda, separando agenda de hoje e agenda futura.
4. `gui` renderiza o estado inicial e bloqueia chat e automacoes quando o Gemini nao esta operante.
5. `cli` reutiliza os mesmos servicos centrais para manter comportamento consistente.

## Dados persistidos

- notas e documentos canonicos em SQLite
- perfil pessoal, interesses e memoria_comportamental em tabelas estruturadas
- indice textual FTS5 para busca
- token local do Google em pasta ignorada

## Fronteiras de privacidade

- `config.toml` aceita `llm.api_key`, mas o caminho mais seguro continua sendo `llm.api_key_env`
- tokens locais ficam fora de versionamento
- LLM e APIs externas so recebem dados quando o modulo correspondente e usado
- logs devem permanecer sem conteudo pessoal por padrao
