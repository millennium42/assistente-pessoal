# Arquitetura

Esta versao separa o projeto em camadas pequenas para reduzir acoplamento entre interface, servicos e fontes externas.

## Principios

- Markdown primeiro: a memoria precisa continuar util fora do assistente
- configuracao previsivel: caminho relativo deve ser resolvido a partir do `config.toml`
- falha local e isolada: uma fonte de noticia ruim nao deve derrubar o restante
- privacidade por padrao: sem segredos em arquivo e sem logar conteudo pessoal por acidente

## Blocos principais

- `config`: leitura do `config.toml`, defaults e criacao do vault
- `core_paths`: resolucao de caminhos relativos e exibicao segura
- `core_datas`: datas, timezone e resolucao de `hoje|amanha|dia da semana`
- `memoria`: Markdown, SQLite FTS5, documentos fixos do dashboard
- `clima`: Open-Meteo com previsao por dia selecionado
- `fontes_noticias`: adaptadores de The News, RSS e HTML com JSON-LD
- `noticias`: orquestracao por prioridade
- `painel`: casos de uso consumidos pela GUI
- `gui`: dashboard local com NiceGUI
- `agenda_google`: OAuth local e leitura de eventos do Google Agenda
- `cli`: comandos Typer
- `roteador`: texto livre para clima, noticias, memoria e estudo

## Fluxo do Obsidian

1. `config.toml` define `vault_path`
2. se `vault_path` for relativo, ele e resolvido pela pasta do `config.toml`
3. `memoria` cria e indexa `.md` dentro do vault efetivo
4. `memoria info` mostra exatamente qual pasta deve ser aberta no Obsidian

Isso corrige o caso em que a pessoa executa o projeto em uma pasta, mas abre outro vault no Obsidian.

## Fluxo de noticias

1. `noticias` recebe `NoticiasConfig`
2. `ClienteNoticias` percorre `prioridades`
3. cada grupo usa o adaptador apropriado:
   - `TheNewsSource`
   - `RssNewsSource`
   - `HtmlJsonLdNewsSource`
4. os itens sao filtrados para o dia atual local
5. a interface recebe uma lista normalizada de `Noticia`

## Fluxo da GUI

1. `assistente-pessoal gui` carrega a configuracao
2. `DashboardService` monta um snapshot com clima, noticias e textos do vault
3. `gui` renderiza blocos editaveis
4. salvar agenda/plano escreve em arquivos fixos do vault

## Estrutura do vault

- `00_inbox`
- `10_memoria`
- `20_estudos`
- `30_resumos`
- `40_noticias`
- `50_musica`
- `60_planejamento`
- `61_agenda_local`
- `90_logs`
- `.assistente/index.sqlite3`
