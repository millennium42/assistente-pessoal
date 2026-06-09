# Seguranca e LGPD

Este documento descreve controles tecnicos do Assistente Pessoal. Ele nao e parecer juridico. Para uso com dados de terceiros, empresa ou operacao regulada, faca revisao juridica e ajuste avisos, contratos e bases legais.

## Referencias

- [Lei 13.709/2018 - LGPD](https://legis.senado.gov.br/norma/27457334)
- [ANPD](https://www.gov.br/anpd/pt-br)
- [Guia de seguranca da ANPD](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-publica-guia-de-seguranca-para-agentes-de-tratamento-de-pequeno-porte)
- [Guia de agentes de tratamento da ANPD](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/2021.05.27GuiaAgentesdeTratamento_Final.pdf)

## Postura tecnica

- Processar localmente por padrao.
- Minimizar dados expostos a UI.
- Redigir logs.
- Separar segredo de configuracao.
- Exigir opt-in antes de LLM externo.
- Permitir exportacao e limpeza de dados locais gerados.

## Dados pessoais

O assistente pode tratar:

- conteudo livre em memorias;
- notas de estudo;
- cidade, latitude, longitude e timezone;
- preferencias de noticias e musica;
- audio temporario de voz;
- logs tecnicos;
- chaves e tokens.

O mapa detalhado fica em [mapa-de-dados.md](mapa-de-dados.md) e no endpoint `/api/privacy/data-map`.

## Bases legais sugeridas

Para uso pessoal local, o padrao tecnico e tratar como execucao de servico solicitado pelo proprio titular. Para LLM externo, integracoes cloud ou dados de terceiros, o app exige consentimento explicito e granular.

Qualquer uso alem do pessoal deve revisar:

- controlador e operador;
- finalidade;
- necessidade;
- retencao;
- compartilhamento internacional;
- resposta a direitos do titular;
- encarregado, quando aplicavel.

## Controles implementados

- `.gitignore` cobre vault, config local, tokens, logs e credenciais do Google Agenda.
- API local nao habilita CORS aberto.
- API escuta por padrao em `127.0.0.1`.
- `/api/config/safe` redige nomes de variaveis de chave.
- `logs.redact_sensitive` remove chaves, tokens, Bearer e `client_secret`.
- Chaves de LLM sao lidas por variavel de ambiente.
- `/api/privacy/export` gera pacote de portabilidade.
- `/api/privacy/purge` remove caches e indices gerados sem apagar notas.
- CI roda secret scanning com Gitleaks.

## Riscos residuais

- O vault Markdown e legivel no disco. Use criptografia de disco se o computador for compartilhado.
- Se o usuario colar dado sensivel em memoria, ele sera salvo localmente.
- Provedores externos recebem dados quando o usuario autoriza.
- O endpoint do The News e RSS podem mudar.
- O sidecar desktop precisa assinar binarios e ajustar permissoes antes de distribuicao ampla.

## Incidente local de credencial

Se existir arquivo local como `googleAgenda.json` com `client_secret`, nao commite. Considere a credencial comprometida e rotacione no Google Cloud Console. Depois guarde credenciais fora do repositorio.
