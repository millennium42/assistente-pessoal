# Privacidade e LGPD

O projeto adota uma postura local-first, mas nao promete funcionamento totalmente offline. Sempre que uma integracao externa e usada, existe trafego de dados correspondente.

A partir da versão `0.3.3`, o Gemini é o motor cognitivo obrigatório. Interações do dia a dia serão interpretadas e enviadas ao provedor de IA.

## O que permanece local

- banco SQLite com memoria e documentos canonicos
- configuracao estrutural do projeto
- perfil, interesses, anotacoes e documentos locais do assistente

## O que pode sair da maquina

- clima: coordenadas e timezone para a Open-Meteo
- noticias: consultas HTTP para The News, RSS, HTML e interesses
- chat: toda a intenção de roteamento depende de payloads JSON estruturados pelo Gemini
- memória viva: sinais, interesses e comportamentos aprendidos podem ser processados pela API antes de serem persistidos
- Google Agenda: leitura e criacao de eventos via OAuth

## Diretrizes aplicadas no repositorio

- minimizacao de dados por padrao
- prompts do dashboard limitados e cacheados para reduzir reenvio desnecessario de contexto
- preferencia por segredo fora de versionamento
- tokens e arquivos OAuth fora de versionamento
- transparencia documental sobre trafego externo
- controle local sobre o banco e sua exclusao

## Recomendacoes operacionais

- prefira `llm.api_key_env` ou `GEMINI_API_KEY` quando nao quiser guardar a chave no arquivo
- guarde o arquivo OAuth apenas no ambiente local
- revise o contexto enviado a provedores LLM externos
- evite logs verbosos com conteudo pessoal

## Referencias

- [Lei 13.709/2018 - LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Perguntas frequentes da ANPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/perguntas-frequentes-anpd)
