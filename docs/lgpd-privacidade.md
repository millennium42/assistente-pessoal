# Privacidade e LGPD

O projeto adota uma postura local-first, mas nao promete funcionamento totalmente offline. Sempre que uma integracao externa e usada, existe trafego de dados correspondente.

## O que permanece local

- banco SQLite com memoria e documentos canonicos
- configuracao estrutural do projeto
- agenda local e plano de estudos

## O que pode sair da maquina

- clima: coordenadas e timezone para a Open-Meteo
- noticias: consultas HTTP para The News, RSS, HTML e interesses
- chat: mensagem e contexto local para o endpoint LLM configurado
- Google Agenda: leitura e criacao de eventos via OAuth

## Diretrizes aplicadas no repositorio

- minimizacao de dados por padrao
- nenhuma chave em `config.toml`
- tokens e arquivos OAuth fora de versionamento
- transparencia documental sobre trafego externo
- controle local sobre o banco e sua exclusao

## Recomendacoes operacionais

- mantenha `config.toml` sem credenciais sensiveis
- guarde o arquivo OAuth apenas no ambiente local
- revise o contexto enviado a provedores LLM externos
- evite logs verbosos com conteudo pessoal

## Referencias

- [Lei 13.709/2018 - LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Perguntas frequentes da ANPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/perguntas-frequentes-anpd)
