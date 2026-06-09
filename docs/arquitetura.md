# Arquitetura da V1

Este documento explica como a V1 foi desenhada e por que algumas escolhas foram feitas.

## Principios

- **Modularidade antes de brilho:** cada capacidade fica em um modulo proprio para poder ser trocada depois.
- **Memoria legivel por humanos:** o Obsidian guarda Markdown comum, entao a memoria nao fica presa ao assistente.
- **Falha graciosa:** rede, LLM e microfone podem falhar; os outros comandos devem continuar funcionando.
- **pt-BR como padrao:** mensagens, README, docstrings e comentarios importantes devem estar em portugues brasileiro.

## Modulos

- `cli`: comandos Typer e apresentacao no terminal.
- `config`: leitura de `config.toml`, `.env` e criacao inicial do vault.
- `memoria`: escrita de Markdown e indice SQLite FTS5.
- `estudos`: resumo local ou via LLM e perguntas de revisao.
- `noticias`: agregacao do The News tecnologia e RSS/Atom tech com `feedparser`.
- `adapters.google_calendar`: OAuth local e eventos pela API oficial do Google Agenda.
- `clima`: consulta Open-Meteo.
- `musica`: consulta MusicBrainz respeitando identificacao por User-Agent.
- `llm`: adaptador pequeno para endpoints compativeis com OpenAI.
- `voz`: gravacao push-to-talk e transcricao com `faster-whisper`.
- `roteador`: interpretacao simples de texto livre para comandos da V1.
- `api`: servidor local FastAPI usado pela GUI.
- `apps/desktop`: dashboard Tauri + React empacotado como aplicativo Windows.

## Fluxo de voz

1. `assistente-pessoal ouvir` grava audio curto.
2. `voz` salva WAV temporario e transcreve em CPU.
3. `roteador` recebe a transcricao como texto.
4. O modulo correspondente executa a acao.
5. O resultado volta em texto no terminal.

A V1 evita wake word porque o hardware atual e simples para escuta continua. Push-to-talk e menos magico, mas e mais honesto e testavel.

## Memoria

O vault dedicado evita misturar notas pessoais com arquivos gerados. A estrutura inicial e:

- `00_inbox`
- `10_memoria`
- `20_estudos`
- `30_resumos`
- `40_noticias`
- `50_musica`
- `90_logs`

O indice tecnico fica em `.assistente/index.sqlite3`. Ele pode ser apagado e recriado com `assistente-pessoal memoria reindexar`.

## IA

O LLM e opcional. Quando `base_url` e `modelo` estao vazios, o assistente responde com fallback e segue executando comandos locais.

O adaptador usa o formato `/chat/completions`, o que permite:

- provedores cloud compativeis com OpenAI;
- Ollama em `http://localhost:11434/v1`;
- outros servidores locais no futuro.

## GUI desktop

O dashboard da V1 fica em `apps/desktop`. Ele conversa com a API local em `127.0.0.1:8777` e expõe os cards centrais do assistente:

- memoria;
- estudo;
- clima atual e previsao futura;
- noticias;
- musica;
- chat;
- Google Agenda;
- privacidade.

No build final, o Tauri empacota a GUI e inicia a API como sidecar. Isso permite abrir o assistente como aplicativo, mantendo as regras de negocio nos modulos Python ja testados.

## Noticias e interesses

O dashboard carrega noticias em blocos de 100 itens. Quando uma materia e clicada ou salva, o backend cria uma nota em `40_noticias` com:

- trecho vindo da fonte RSS/API;
- link original;
- categoria;
- tags derivadas dos assuntos de interesse configurados;
- links internos do Obsidian para materias ja clicadas com termos em comum.

Isso cria um historico local de comportamento e interesses sem rastreamento externo.

## Fora do escopo atual

- Wake word.
- TTS neural.
- Busca vetorial/RAG.
- Automacoes recorrentes.
- Preferencias musicais vindas de servicos autenticados.
