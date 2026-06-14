# Decisoes tecnicas

Este documento registra o que foi escolhido e, mais importante, o que foi evitado.

## GUI

Escolha: `NiceGUI`

Motivo:

- continua Python puro
- e rapida para montar painel util
- evita o peso imediato de app desktop nativo

Critica: `PySide6` daria mais controle visual, mas colocaria layout, empacotamento e testes de desktop cedo demais.

### Revisao visual de 2026-06-13

Escolha: duas visualizacoes intencionalmente diferentes.

- `Limpa`: leitura executiva, cards maiores, detalhes secundarios ocultos e grafico
  semanal em destaque.
- `Detalhada`: painel operacional, grade tecnica, seis KPIs compactos, distribuicao
  de noticias visivel e metricas extras de clima abertas.

Motivo:

- evita que o mesmo layout tente servir dois ritmos de uso opostos
- melhora o tema claro com contraste previsivel
- mantem icones pequenos e controles discretos
- reduz a sensacao visual de painel carregado quando o usuario so quer um resumo

Decisao adicional: o servidor da GUI nao deve esperar clima, noticias, cambio ou agenda
antes de abrir a porta local. A tela sobe primeiro e os dados entram por atualizacao do
dashboard. Isso torna o comando `assistente-pessoal gui` mais responsivo e evita que uma
fonte externa lenta pareca uma falha da aplicacao.

## Memoria

Escolha: Banco de dados relacional (SQLite)

Motivo:

- garante integridade estrutural das memorias e relacionamentos
- centraliza as informacoes em um unico arquivo
- suporta operacoes de busca (FTS5) nativamente
- GUI e CLI compartilham a mesma conexao com o banco

Critica: o usuario perde a visao imediata via pastas do sistema operacional (como havia com arquivos soltos), mas o banco ainda e um arquivo unico e local (SQLite), que pode ser lido com ferramentas simples. A prioridade atual e desempenho, estruturacao e confiabilidade.

Atualizacao de qualidade:

- a gravacao de notas e documentos fixos usa uma rotina comum para manter a tabela
  `documentos` e o indice FTS5 sincronizados
- o comando `memoria info` foi alinhado ao modelo atual, removendo a referencia a um
  arquivo de indice separado que nao existe mais

## Noticias

Escolha: orquestrador com grupos de prioridade e exibicao cronologica

Prioridade de coleta:

1. The News
2. Santa Maria
3. tech
4. economia global

Motivo:

- deixa o comportamento explicito
- evita um modulo monolitico de noticias
- permite trocar uma fonte fragil sem reescrever o restante
- mostra o feed final do mais recente ao mais antigo, com tempo relativo em vez de data bruta

Critica: Santa Maria por midia local e o grupo menos estavel do sistema. A estrategia foi isolar parsing HTML em um adaptador proprio e aceitar falha graciosa.

Atualizacao de qualidade: a ordenacao/importacao foi normalizada pelo formatador do
projeto, sem alterar a regra de negocio.

## Clima

Escolha: Open-Meteo

Motivo:

- nao exige chave para o caso atual
- tem resposta simples
- funciona bem para hoje e proximos dias

Critica: nao tentamos transformar clima em motor de linguagem natural. O foco e previsao clara por data.

Atualizacao de qualidade: os campos extras de clima agora sao opcionais por padrao, o
que preserva compatibilidade com fakes de teste e evita quebra quando a API nao traz
um bloco secundario.

## Agenda

Escolha: agenda local no banco + Google Agenda para leitura e criacao de eventos

Motivo:

- reduz risco de privacidade
- mantem o planejamento local salvo de forma rapida no banco
- adiciona visibilidade dos proximos eventos reais da conta Google
- usa escopo restrito a eventos, necessario para criar compromissos

Critica: a integracao cria eventos simples e lista o calendario configurado, mas nao tenta
substituir um cliente completo de agenda.

## Cambio

Escolha: AwesomeAPI com fallback entre endpoints conhecidos.

Motivo:

- mantem dependencia simples e sem chave de API
- evita falha quando um endpoint retorna formato indisponivel temporariamente
- concentra a politica de fallback em uma funcao pequena e testavel

## LGPD

Escolhas:

- nenhuma chave em `config.toml`
- documentacao explicita do que sai da maquina
- evitar logs com conteudo pessoal
- manter o banco de dados legivel, local e apagavel

Critica: LGPD nao se resolve com uma pagina de politica. A parte util aqui foi reduzir coleta, reduzir persistencia opaca e deixar integracoes externas opt-in.
