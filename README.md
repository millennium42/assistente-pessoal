# Assistente Pessoal V1 com GUI

Assistente pessoal local-first em pt-BR, com o dashboard da V1 dentro de um aplicativo Windows.

O alvo do projeto e simples: manter as capacidades ja validadas da V1 e entrega-las em uma GUI desktop empacotada como `.exe`.

## O que entra no app

- Dashboard React dinamico, responsivo e minimalista, com dark/light mode e leitura visual estilo painel analitico.
- Cards de memoria, estudo, clima, noticias, musica, chat, Google Agenda e privacidade local.
- Backend FastAPI local iniciado como sidecar do Tauri.
- Modulos da V1 preservados: `memoria`, `estudos`, `clima`, `noticias`, `musica`, `voz`, `roteador` e `llm`.
- Configuracao local em `config.toml`.
- Vault Markdown legivel no Obsidian, com tags, assuntos e links internos.
- Google Agenda via API oficial, com leitura e criacao de eventos.
- Noticias carregadas em blocos de 100; ao clicar/salvar, a noticia vira nota no Obsidian com trecho, categoria, tags e links para materias relacionadas.

## O que fica fora do app

- `config.toml`, `.env`, tokens, credenciais e `googleAgenda.json`.
- Vault do usuario e indices locais.
- Qualquer chave de API real.

`googleAgenda.json` e uma credencial opcional do backend. Ele deve ficar local, fora de artefatos publicos e fora do frontend.

## Desenvolvimento

Prepare o ambiente:

```powershell
.\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto
```

Esse bootstrap verifica Python, uv, Node.js, Rust/Cargo, Git, FFmpeg e GitHub CLI.

Rode a API local:

```powershell
uv run assistente-pessoal-api --host 127.0.0.1 --port 8777
```

Em outro terminal, rode a GUI web de desenvolvimento:

```powershell
cd apps\desktop
npm install
npm run dev
```

## Gerar o `.exe`

```powershell
.\scripts\build_setup.ps1
```

O script gera o sidecar Python com PyInstaller e chama o build do Tauri. O instalador final fica em:

```text
apps\desktop\src-tauri\target\release\bundle\nsis\
```

## Qualidade

```powershell
.\scripts\verificar_app.ps1
```

Ou, separadamente:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Seguranca e LGPD

O assistente segue local-first, redacao de segredos em logs, opt-in para LLM externo e exportacao/purge local de dados. Esta documentacao tecnica nao substitui revisao juridica.

Leituras principais:

- [Arquitetura da V1](docs/arquitetura.md)
- [Guia de uso](docs/uso.md)
- [Build desktop](docs/build-desktop.md)
- [Seguranca e LGPD](docs/seguranca-lgpd.md)
- [Mapa de dados](docs/mapa-de-dados.md)
