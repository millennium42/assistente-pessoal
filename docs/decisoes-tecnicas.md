# Decisoes tecnicas e criticas da V1

Este documento registra as escolhas da V1 e as alternativas consideradas. Ele existe para impedir que o projeto vire uma colecao de tecnologias bonitas, mas pouco uteis.

## Interface inicial

Escolha da V1: **CLI com Typer e Rich**.

Opcoes consideradas:

- CLI: simples, testavel, rapida de evoluir e adequada para validar comandos.
- Web local: melhor para visualizar, mas aumenta complexidade de audio, estado e frontend.
- Desktop: mais confortavel para uso diario, mas pesado demais para uma primeira versao.

Critica: uma interface bonita cedo demais esconderia problemas basicos de produto. Primeiro precisamos provar que os comandos sao uteis, que a memoria funciona e que a voz nao atrapalha.

## Voz

Escolha da V1: **push-to-talk com faster-whisper em CPU**.

Opcoes consideradas:

- `faster-whisper`: bom equilibrio entre qualidade, desempenho e projeto aberto.
- APIs cloud de fala: mais simples e precisas, mas piores para privacidade e custo.
- Wake word local: mais natural, mas consome CPU e tende a ser fragil em ambiente real.

Critica: wake word parece "assistente de verdade", mas no hardware atual provavelmente geraria friccao. Push-to-talk e menos glamouroso, so que permite uma V1 confiavel.

## Memoria

Escolha da V1: **vault dedicado do Obsidian + Markdown + SQLite FTS5**.

Opcoes consideradas:

- Obsidian/Markdown: transparente, editavel e facil de versionar.
- Banco relacional puro: mais estruturado, mas menos humano.
- Vector DB: mais poderoso para busca semantica, mas desnecessario antes de validar o uso.

Critica: usar vector DB na V1 seria uma solucao sofisticada para um problema ainda pequeno. SQLite FTS5 e suficiente, local e facil de reconstruir.

## IA/LLM

Escolha da V1: **adaptador pequeno para endpoint compativel com OpenAI, opcional**.

Opcoes consideradas:

- Ollama local: bom para privacidade, mas lento nesta maquina sem GPU dedicada.
- API cloud: melhor qualidade, mas adiciona custo e dependencia externa.
- Sem LLM: mais robusto, mas limita estudo e conversa.
- LiteLLM: conveniente, mas evitado na V1 por risco recente de cadeia de suprimentos.

Critica: tentar fazer "IA local completa" nesta maquina seria vender uma experiencia pior do que a promessa. A arquitetura hibrida permite comecar util agora e trocar o motor depois.

## Noticias

Escolha da V1: **The News tecnologia como fonte prioritaria + RSS/Atom tech com feedparser**.

Opcoes consideradas:

- RSS/Atom: aberto, simples e sem scraping agressivo.
- API publica usada pelo portal The News: atende ao pedido de incluir The News, mas e uma integracao especifica e pode mudar.
- APIs pagas de noticias: mais completas, mas desnecessarias para V1.
- Scraping de sites: fragil, possivelmente contra termos de uso e mais dificil de manter.

Critica: The News nao anunciou RSS publico nas rotas comuns testadas. Por isso a V1 usa o endpoint publico consumido pelo proprio portal para a categoria tecnologia e mantem RSS tech como base resiliente. Se essa API mudar, os feeds de tecnologia continuam funcionando.

## Clima

Escolha da V1: **Open-Meteo**.

Opcoes consideradas:

- Open-Meteo: sem chave para uso basico, documentado e simples.
- OpenWeatherMap: conhecido, mas geralmente envolve chave e limites de conta.
- Servicos nacionais: podem ser bons, mas dificultam generalizacao.

Critica: clima nao deve virar o centro do projeto. Uma API simples, com JSON claro e sem chave, e a escolha mais sensata.

## Musica

Escolha da V1: **MusicBrainz para lancamentos por artista configurado**.

Opcoes consideradas:

- MusicBrainz: aberto e coerente com o projeto.
- Spotify: melhor experiencia comercial, mas exige app, OAuth e integra uma plataforma fechada.
- ListenBrainz: interessante para preferencias futuras, mas pede mais configuracao para uma V1.

Critica: Spotify seria mais chamativo, mas tambem puxaria a V1 para OAuth e dependencia de plataforma. MusicBrainz e menos polido, porem mais aberto.

## Gerenciador de projeto

Escolha da V1: **uv + pyproject.toml**.

Opcoes consideradas:

- uv: rapido, moderno e reduz a bagunca de ambiente.
- pip + venv manual: universal, mas mais verboso e facil de errar.
- Poetry: bom, porem mais pesado para este escopo.

Critica: o ambiente inicial estava sem Python e sem Git. Precisavamos de um fluxo reproducivel, nao de instrucoes soltas.

## Qualidade

Escolha da V1: **pytest + ruff + CI no GitHub Actions**.

Opcoes consideradas:

- pytest: direto e maduro para testes.
- unittest: padrao da linguagem, mas menos ergonomico para este projeto.
- ruff: lint e formatacao rapidos em uma ferramenta so.

Critica: qualidade nao e luxo aqui. Como o assistente vai tocar arquivos pessoais e integracoes externas, testes e lint precisam existir desde o inicio.
