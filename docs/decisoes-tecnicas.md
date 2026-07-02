# Decisoes tecnicas

Este documento resume as escolhas centrais da versao `0.3.3`.

## Interface

Escolha: `NiceGUI`

Motivo:

- mantem o projeto em Python de ponta a ponta
- acelera iteracao do dashboard local
- simplifica distribuicao e testes em comparacao com uma GUI desktop nativa

## Memoria

Escolha: SQLite com FTS5 + Memoria Adaptativa

Motivo:

- persistencia local simples de inspecionar
- busca textual nativa
- estrutura adequada para perfil pessoal, interesses e documentos canonicos

## Noticias

Escolha: orquestracao por grupos com adaptadores separados

Motivo:

- troca de fontes sem reescrever o modulo inteiro
- isolamento de falhas
- feed final mais previsivel

## Clima

Escolha: Open-Meteo

Motivo:

- API simples
- sem chave obrigatoria para o caso atual
- boa aderencia ao uso local por dia

## Agenda

Escolha: Google Agenda opcional como calendario operacional

Motivo:

- evita duplicar calendarios manuais e operacionais
- reduz ambiguidade sobre onde um compromisso deve viver
- mantem criacao e leitura de eventos reais quando habilitado

## LLM

Escolha: Gemini como cerebro obrigatorio

Motivo:

- centraliza decisao, curadoria, memoria adaptativa e orquestracao do chat
- evita divergencia entre heuristicas locais e comportamento da assistente
- usa `gemini-3.1-flash-lite` como modelo padrao
- limita respostas com `maxOutputTokens` e usa `responseMimeType` oficial no payload
- corta contexto longo antes do prompt para conter uso de tokens

## Cache cognitivo

Escolha: TTL proprio para insights do dashboard

Motivo:

- evita chamar o Gemini a cada refresh automatico da interface
- preserva atualizacao imediata quando perfil, interesses, noticias salvas, agenda ou contexto mudam pela APPA
- mantem os caches externos separados dos insights narrativos

## Privacidade

Escolhas:

- configuracao sem chaves gravadas em arquivo
- arquivos OAuth e tokens mantidos fora de versionamento
- integracoes externas sempre tratadas como opt-in
- base local como fonte principal de memoria e contexto
