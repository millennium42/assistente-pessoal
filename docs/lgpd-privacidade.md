# Privacidade e LGPD

Este projeto e local por padrao, mas nao e "offline por definicao". Algumas funcoes usam servicos externos quando habilitadas.

## O que fica local

- banco de dados relacional (SQLite) centralizando as informacoes
- plano de estudos e agenda local armazenados no banco
- configuracao estrutural do `config.toml`

## O que pode sair da maquina

- clima: coordenadas e timezone para a Open-Meteo
- noticias: requisicoes HTTP para The News, feeds RSS, paginas locais configuradas e buscas RSS por interesses
- musica: nomes de artistas para o MusicBrainz
- chat: mensagem e contexto local para o endpoint LLM configurado
- Google Agenda: leitura e criacao de eventos no calendario configurado via OAuth

## Escolhas praticas alinhadas com LGPD

- minimizacao: nao salvamos chaves de API em arquivo
- transparencia: o README explica quais modulos usam rede
- controle do titular: o banco de dados e local e pode ser completamente inspecionado e apagado
- segregacao: agenda local e planejamento ficam isolados na estrutura do banco
- reducao de privilegio: Google Agenda usa escopo restrito a eventos

## Recomendacoes de uso

- nao comite `config.toml` com informacoes privadas
- nao comite o arquivo de credenciais OAuth do Google nem o token local
- prefira um banco de dados local isolado no ambiente do projeto ao inves de mesclar com bancos de dados de producao
- revise o conteudo enviado a provedores LLM externos
- nao use logs verbosos em producao com conteudo de notas pessoais

## Fontes de referencia

- [Lei 13.709/2018 - LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Perguntas frequentes da ANPD](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/perguntas-frequentes-anpd)
- [Guia de Boas Praticas - LGPD](https://www.gov.br/governodigital/pt-br/privacidade-e-seguranca/guias/guia_lgpd.pdf)
