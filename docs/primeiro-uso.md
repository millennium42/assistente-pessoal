# Guia de primeiro uso

Este guia leva voce do zero ate uma V1 funcionando no dia a dia: terminal preparado, ambiente instalado, vault do Obsidian criado, comandos basicos testados, voz validada e primeiras configuracoes pessoais feitas.

## 0. O que esperar da V1

A V1 e um assistente de linha de comando. Ele nao tenta parecer um app completo ainda. A ideia e validar as partes mais importantes:

- salvar e buscar memoria em Markdown no Obsidian;
- ajudar nos estudos com notas, resumos simples e perguntas de revisao;
- ler noticias focadas em tecnologia, priorizando The News tecnologia e RSS tech;
- consultar previsao do tempo;
- procurar lancamentos musicais por artista;
- aceitar comandos por texto e por voz push-to-talk;
- funcionar mesmo sem LLM configurado.

Critica honesta: nesta primeira versao, voz e IA sao ferramentas, nao magia. Se o microfone, a rede ou o modelo falharem, o assistente deve continuar util pelos comandos locais.

## 1. Abrir o terminal certo

Use PowerShell no Windows e entre na pasta do projeto:

```powershell
cd "D:\milla\OneDrive\Documentos\Assistente de IA pessoal"
```

Confira se voce esta no lugar certo:

```powershell
dir
```

Voce deve ver arquivos como `README.md`, `pyproject.toml`, `src`, `docs` e `scripts`.

## 2. Preparar ferramentas do Windows

Rode primeiro uma verificacao:

```powershell
.\scripts\bootstrap_windows.ps1 -SomenteVerificar
```

Se alguma ferramenta estiver faltando, rode:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Esse script cuida de Python 3.12, uv, Git, FFmpeg, GitHub CLI, ambiente virtual `.venv` e instalacao do projeto em modo editavel.

Se algum comando recem-instalado nao for reconhecido, feche e abra o terminal. No Windows isso e normal: o PATH de uma sessao antiga nem sempre atualiza sozinho.

## 3. Instalar manualmente, se preferir

Se as ferramentas ja existem, voce pode preparar o projeto assim:

```powershell
uv venv
uv pip install -e ".[dev]"
```

Se `uv` nao for reconhecido, tente reiniciar o terminal. Se ainda nao funcionar, rode:

```powershell
.\scripts\bootstrap_windows.ps1
```

## 4. Verificar se a instalacao ficou saudavel

Rode:

```powershell
.\scripts\verificar.ps1
```

Resultado esperado:

- testes passando;
- lint passando;
- formatacao conferida.

Se falhar, leia a primeira mensagem de erro. Os problemas mais comuns sao `.venv` ausente, dependencias nao instaladas, terminal nao reiniciado depois do bootstrap ou comando rodado fora da pasta do projeto.

## 4.1. Como chamar o assistente

Depois da instalacao, o comando `assistente-pessoal` fica em `.venv\Scripts`. Se voce tentar rodar `assistente-pessoal init` sem ativar a venv, o PowerShell pode mostrar:

```text
assistente-pessoal : O termo 'assistente-pessoal' nao e reconhecido
```

Isso nao significa que a instalacao falhou. Use uma destas opcoes.

Opcao mais direta:

```powershell
.\.venv\Scripts\assistente-pessoal.exe --help
```

Ou ative a venv uma vez por terminal:

```powershell
.\.venv\Scripts\Activate.ps1
assistente-pessoal --help
```

Se a ativacao for bloqueada por politica do PowerShell, continue usando `.\.venv\Scripts\assistente-pessoal.exe`.

## 5. Criar a configuracao inicial

Rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe init
```

Isso cria `config.toml`, um vault dedicado em `vault/AssistentePessoal` e as pastas internas do vault:

```text
vault/AssistentePessoal/
  00_inbox/
  10_memoria/
  20_estudos/
  30_resumos/
  40_noticias/
  50_musica/
  90_logs/
  .assistente/
```

Se voce quiser outro local para o vault:

```powershell
.\.venv\Scripts\assistente-pessoal.exe init --vault "D:\Notas\AssistentePessoal"
```

## 6. Abrir o vault no Obsidian

No Obsidian:

1. Abra o Obsidian.
2. Escolha abrir um vault existente.
3. Selecione `vault/AssistentePessoal` ou o caminho que voce passou em `--vault`.
4. Confirme que as pastas do assistente aparecem na barra lateral.

O assistente grava Markdown comum. Voce pode editar as notas pelo Obsidian, mas evite apagar a pasta `.assistente` enquanto estiver usando a busca. Se apagar, rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria reindexar
```

## 7. Primeiro teste de memoria

Salve uma memoria:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Plano de estudo" "Quero revisar calculo toda segunda e fazer questoes curtas."
```

Busque a memoria:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria buscar calculo
```

Abra o Obsidian e confira se uma nota apareceu em `10_memoria`.

Se a busca nao encontrar nada, rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria reindexar
.\.venv\Scripts\assistente-pessoal.exe memoria buscar calculo
```

## 8. Primeiro teste de estudo

Crie uma nota de estudo com conteudo direto:

```powershell
.\.venv\Scripts\assistente-pessoal.exe estudar "Algebra linear" --conteudo "Vetores, bases, matrizes, determinantes e transformacoes lineares."
```

Depois abra o Obsidian e veja a nota em `20_estudos`.

Sem LLM configurado, o assistente usa um resumo local simples. Isso e proposital: a V1 nao deve depender de IA externa para funcionar.

## 9. Primeiro teste de clima

Rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe clima
```

O clima usa os dados em `config.toml`:

```toml
[localizacao]
cidade = "Santa Maria, RS"
latitude = -29.6868
longitude = -53.8149
timezone = "America/Sao_Paulo"
```

Para outra cidade, edite `cidade`, `latitude`, `longitude` e `timezone`.

## 10. Primeiro teste de noticias

Rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe noticias --limite 5
```

As fontes ficam em `config.toml`:

```toml
[fontes]
incluir_the_news_tecnologia = true
rss = [
  "https://tecnoblog.net/feed/",
  "https://www.canaltech.com.br/rss/",
  "https://olhardigital.com.br/feed/",
]
```

O The News entra pela categoria publica de tecnologia do portal. Os RSS complementares sao focados em tecnologia. Voce pode adicionar outros feeds RSS de tecnologia, faculdade, ciencia ou musica, mas evite colocar sites sem RSS: a V1 nao faz scraping generico.

## 11. Primeiro teste de musica

Edite `config.toml` e adicione artistas:

```toml
[fontes]
artistas = [
  "Radiohead",
  "Milton Nascimento",
]
musicbrainz_user_agent = "assistente-pessoal/0.1.0 (contato: seu-email-ou-github)"
```

Depois rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe musica
```

Critica honesta: MusicBrainz e aberto e coerente com o projeto, mas nem sempre e tao polido quanto Spotify. Para a V1, isso e aceitavel porque evita OAuth e dependencia de plataforma fechada.

## 12. Primeiro teste de chat sem LLM

Rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe chat "o que voce consegue fazer?"
```

Sem LLM configurado, a resposta esperada e um fallback explicando os comandos locais. Isso nao e erro: o assistente deve continuar util mesmo sem IA externa.

## 13. Configurar LLM opcional

Para Ollama local:

```toml
[llm]
base_url = "http://localhost:11434/v1"
modelo = "llama3.2:3b"
api_key_env = "OPENAI_API_KEY"
```

Para um provedor cloud compativel com OpenAI:

```toml
[llm]
base_url = "https://api.exemplo.com/v1"
modelo = "modelo-escolhido"
api_key_env = "OPENAI_API_KEY"
```

Configure a variavel de ambiente:

```powershell
$env:OPENAI_API_KEY="sua-chave"
.\.venv\Scripts\assistente-pessoal.exe chat "resuma minhas memorias sobre calculo"
```

Para salvar a chave de forma persistente, use um mecanismo seguro do seu sistema ou um arquivo `.env` local. Nunca commite `.env`.

## 14. Primeiro teste de voz

Rode:

```powershell
.\.venv\Scripts\assistente-pessoal.exe ouvir
```

Fale algo curto:

- "qual e o clima?"
- "buscar calculo"
- "memorizar revisar algebra linear"
- "noticias"
- "lancamentos de musica"

O assistente grava pelo tempo configurado:

```toml
[voz]
modelo_whisper = "tiny"
idioma = "pt"
duracao_segundos = 6
taxa_amostragem = 16000
```

Na primeira execucao, o modelo de transcricao pode demorar porque precisa baixar arquivos. Isso e esperado.

## 15. Ajustar a voz se ficar ruim

Se cortar sua fala, aumente:

```toml
duracao_segundos = 10
```

Se estiver lento, mantenha:

```toml
modelo_whisper = "tiny"
```

Se quiser tentar mais qualidade:

```toml
modelo_whisper = "base"
```

Critica honesta: modelos maiores podem ficar lentos nesta maquina. Teste com calma antes de transformar isso em padrao.

## 16. Fluxo diario recomendado

Um uso simples para faculdade:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria salvar "Aula de hoje" "Professor falou de derivadas parciais e gradiente."
.\.venv\Scripts\assistente-pessoal.exe estudar "Derivadas parciais" --conteudo "Derivadas parciais medem variacao em uma direcao mantendo outras variaveis constantes."
.\.venv\Scripts\assistente-pessoal.exe memoria buscar gradiente
.\.venv\Scripts\assistente-pessoal.exe clima
.\.venv\Scripts\assistente-pessoal.exe noticias --limite 3
```

Depois, revise as notas no Obsidian.

## 17. Validar antes de mexer no codigo

Sempre que alterar o projeto:

```powershell
.\scripts\verificar.ps1
```

Se algo quebrar, corrija antes de publicar.

## 18. Publicar alteracoes no GitHub

O repo publico da V1 e:

```text
https://github.com/millennium42/assistente-pessoal
```

Para autenticar:

```powershell
gh auth login
```

Para publicar a branch atual:

```powershell
.\scripts\publicar_github.ps1 -Owner millennium42 -Repo assistente-pessoal
```

Depois confira o CI:

```text
https://github.com/millennium42/assistente-pessoal/actions
```

## 19. Problemas comuns

### `assistente-pessoal` nao e reconhecido

Rode:

```powershell
uv pip install -e ".[dev]"
```

Ou use:

```powershell
.\.venv\Scripts\assistente-pessoal.exe --help
```

### `python`, `uv`, `git`, `ffmpeg` ou `gh` nao aparecem

Reinicie o terminal. Se continuar:

```powershell
.\scripts\bootstrap_windows.ps1 -SomenteVerificar
```

### Voz nao grava

Confira permissao de microfone do Windows, microfone padrao do sistema, se outro app esta segurando o dispositivo e se `sounddevice` foi instalado no ambiente.

### Transcricao demora

Isso pode acontecer na primeira execucao ou com modelo maior. Comece com `tiny`.

### Noticias nao aparecem

Confira se os feeds RSS em `config.toml` abrem no navegador. Alguns sites mudam feeds com frequencia.

### Musica nao retorna resultados

Teste nomes oficiais dos artistas no MusicBrainz. Alguns nomes precisam estar exatamente como cadastrados.

### Busca no Obsidian ficou estranha

Reconstrua o indice:

```powershell
.\.venv\Scripts\assistente-pessoal.exe memoria reindexar
```

## 20. O que nao fazer na V1

- Nao coloque suas notas pessoais inteiras no vault sem pensar: comece com um vault dedicado.
- Nao dependa de LLM para tudo: os comandos locais precisam continuar uteis.
- Nao aumente o modelo de voz antes de medir desempenho.
- Nao adicione scraping de sites como primeira solucao para noticias.
- Nao transforme a V1 em app desktop antes de validar o fluxo pelo terminal.

Essas restricoes nao sao falta de ambicao. Sao o que mantem a primeira versao simples o bastante para evoluir.
