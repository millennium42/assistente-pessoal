# Arquitetura

Esta versao separa o projeto em camadas pequenas para reduzir acoplamento entre interface, servicos e fontes externas.

## Principios

- Banco de dados relacional: armazenamento persistente, performatico e consultavel
- configuracao previsivel: caminho relativo deve ser resolvido a partir do `config.toml`
- falha local e isolada: uma fonte de noticia ruim nao deve derrubar o restante
- privacidade por padrao: sem segredos em arquivo e sem logar conteudo pessoal por acidente

## Blocos principais

- `config`: leitura do `config.toml` e definicao de caminhos
- `core_paths`: resolucao de caminhos relativos e exibicao segura
- `core_datas`: datas, timezone e resolucao de `hoje|amanha|dia da semana`
- `memoria`: armazenamento em banco de dados relacional SQLite
- `clima`: Open-Meteo com previsao por dia selecionado
- `fontes_noticias`: adaptadores de The News, RSS, HTML com JSON-LD e busca por interesses
- `noticias`: orquestracao por prioridade e ordenacao por horario de publicacao
- `painel`: casos de uso consumidos pela GUI
- `gui`: dashboard local com NiceGUI
- `agenda_google`: OAuth local, leitura e criacao de eventos do Google Agenda
- `cli`: comandos Typer
- `roteador`: texto livre para clima, noticias, memoria e estudo

## Fluxo do Banco de Dados

1. `config.toml` define `db_path`
2. se `db_path` for relativo, ele e resolvido pela pasta do `config.toml`
3. `memoria` usa banco de dados SQLite para salvar informacoes de forma centralizada
4. `memoria info` mostra exatamente o caminho absoluto do banco de dados em uso

## Fluxo de noticias

1. `noticias` recebe `NoticiasConfig`
2. `ClienteNoticias` percorre `prioridades`
3. cada grupo usa o adaptador apropriado:
   - `TheNewsSource`
   - `RssNewsSource`
   - `HtmlJsonLdNewsSource`
   - `InterestNewsSource`
4. interesses salvos tambem geram buscas RSS em portais indexados
5. os itens sao filtrados para o dia atual local e deduplicados
6. a lista final e ordenada do mais recente para o mais antigo
7. a interface recebe uma lista normalizada de `Noticia` com tempo relativo

## Fluxo da GUI

1. `assistente-pessoal gui` carrega a configuracao
2. o servidor NiceGUI sobe sem bloquear em chamadas externas
3. `gui` renderiza a estrutura inicial com estado vazio ou snapshot injetado em testes
4. `DashboardService` monta snapshots quando a tela atualiza dados
5. a visualizacao `Limpa` prioriza leitura rapida e esconde detalhes secundarios
6. a visualizacao `Detalhada` mostra grade mais densa, distribuicao de noticias e metricas extras
7. salvar agenda/plano atualiza registros no banco de dados
8. criar evento chama a Google Agenda configurada e recarrega o mes exibido

## Otimizacoes de qualidade

- O modelo `PrevisaoClima` mantem campos meteorologicos opcionais com defaults para
  preservar compatibilidade com testes e fakes.
- Escritas da memoria SQLite passam por uma rotina comum que sincroniza tabela
  principal e FTS5 no mesmo ponto.
- `memoria info` mostra apenas dados existentes no modelo atual do banco; o indice
  agora vive dentro do SQLite via FTS5.
- O cambio tenta endpoints conhecidos da AwesomeAPI em ordem e so retorna erro depois
  de esgotar os fallbacks.
- Chamadas JavaScript da GUI sao protegidas quando a arvore NiceGUI e montada em teste
  sem loop ativo.
