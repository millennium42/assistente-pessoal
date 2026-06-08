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

## Clima

Escolha: Open-Meteo

Motivo:

- nao exige chave para o caso atual
- tem resposta simples
- funciona bem para hoje e proximos dias

Critica: nao tentamos transformar clima em motor de linguagem natural. O foco e previsao clara por data.

## Agenda

Escolha: agenda local no vault + Google Agenda para leitura e criacao de eventos

Motivo:

- reduz risco de privacidade
- mantem o planejamento local no vault
- adiciona visibilidade dos proximos eventos reais da conta Google
- usa escopo restrito a eventos, necessario para criar compromissos

Critica: a integracao cria eventos simples e lista o calendario configurado, mas nao tenta
substituir um cliente completo de agenda.

## LGPD

Escolhas:

- nenhuma chave em `config.toml`
- documentacao explicita do que sai da maquina
- evitar logs com conteudo pessoal
- manter o vault legivel, local e apagavel

Critica: LGPD nao se resolve com uma pagina de politica. A parte util aqui foi reduzir coleta, reduzir persistencia opaca e deixar integracoes externas opt-in.
