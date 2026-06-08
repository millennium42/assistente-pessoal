# Decisoes tecnicas

Este documento registra o que foi escolhido e, mais importante, o que foi evitado.

## GUI

Escolha: `NiceGUI`

Motivo:

- continua Python puro
- e rapida para montar painel util
- evita o peso imediato de app desktop nativo

Critica: `PySide6` daria mais controle visual, mas colocaria layout, empacotamento e testes de desktop cedo demais.

## Memoria

Escolha: Obsidian + Markdown + SQLite FTS5

Motivo:

- o usuario continua dono dos arquivos
- busca local continua simples e rebuildavel
- GUI e CLI compartilham o mesmo vault

Critica: ainda nao ha busca semantica real. Isso e aceitavel porque a prioridade agora e confiabilidade, nao sofisticao de RAG.

## Noticias

Escolha: orquestrador com grupos de prioridade

Ordem:

1. The News
2. Santa Maria
3. tech
4. economia global

Motivo:

- deixa o comportamento explicito
- evita um modulo monolitico de noticias
- permite trocar uma fonte fragil sem reescrever o restante

Critica: Santa Maria por midia local e o grupo menos estavel do sistema. A estrategia foi isolar parsing HTML em um adaptador proprio e aceitar falha graciosa.

## Clima

Escolha: Open-Meteo

Motivo:

- nao exige chave para o caso atual
- tem resposta simples
- funciona bem para hoje e proximos dias

Critica: nao tentamos transformar clima em motor de linguagem natural. O foco e previsao clara por data.

## Agenda

Escolha: agenda local no vault, sem Google Agenda nesta fase

Motivo:

- reduz risco de privacidade
- evita OAuth, tokens e escopos cedo
- mantem a funcionalidade diaria que realmente importa: registrar planejamento

Critica: isso nao substitui uma agenda em nuvem. E uma camada local de organizacao, nao sincronizacao.

## LGPD

Escolhas:

- nenhuma chave em `config.toml`
- documentacao explicita do que sai da maquina
- evitar logs com conteudo pessoal
- manter o vault legivel, local e apagavel

Critica: LGPD nao se resolve com uma pagina de politica. A parte util aqui foi reduzir coleta, reduzir persistencia opaca e deixar integracoes externas opt-in.
