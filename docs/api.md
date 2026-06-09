# API Local

Base padrao:

```text
http://127.0.0.1:8777/api
```

Docs interativas:

```text
http://127.0.0.1:8777/api/docs
```

## Endpoints

### `GET /api/health`

Retorna status, versao e flags seguras.

### `GET /api/dashboard`

Retorna dados locais para tela inicial. Nao chama APIs externas automaticamente.

### `GET /api/memories`

Lista notas recentes.

Parametro:

- `limite`: 1 a 100.

### `POST /api/memories`

Payload:

```json
{
  "titulo": "Plano de estudo",
  "conteudo": "Revisar calculo toda segunda.",
  "tags": ["estudo"]
}
```

### `DELETE /api/memories?caminho=...`

Apaga apenas Markdown dentro do vault configurado.

### `GET /api/weather`

Consulta Open-Meteo por acao explicita.

### `GET /api/news`

Consulta The News e RSS configurados por acao explicita.

Parametros:

- `limite`: 1 a 100. O dashboard usa 100 na carga inicial.
- `offset`: deslocamento para carregar blocos seguintes.

Retorna `texto`, `itens`, `offset` e `assuntos_interesse`.

### `POST /api/news/interest`

Registra uma noticia clicada ou salva como nota em `40_noticias` no vault do Obsidian.

Payload:

```json
{
  "titulo": "Materia relevante",
  "link": "https://exemplo.test/materia",
  "fonte": "Fonte",
  "resumo": "Trecho copiado pela fonte RSS/API.",
  "publicado": "2026-06-09T12:00:00",
  "tags": ["dashboard"]
}
```

A nota criada inclui categoria, assuntos detectados, trecho e links internos para materias relacionadas.

### `GET /api/music`

Consulta MusicBrainz por acao explicita.

### `POST /api/study-notes`

Cria nota de estudo local.

### `POST /api/chat`

Payload:

```json
{
  "mensagem": "resuma minhas memorias sobre calculo",
  "permitir_llm_externo": false
}
```

Se LLM estiver configurado e `permitir_llm_externo` for `false`, a API retorna aviso de opt-in necessario e nao envia dados.

### `GET /api/config/safe`

Retorna configuracao redigida. Nunca usar `config.toml` bruto no renderer.

### `GET /api/privacy/data-map`

Retorna inventario LGPD.

### `POST /api/privacy/export`

Gera pacote JSON de portabilidade.

### `POST /api/privacy/purge`

Remove caches e indices gerados.

### `GET /api/google-calendar/status`

Retorna se `googleAgenda.json` existe e se a agenda esta conectada.

### `GET /api/google-calendar/auth/start`

Inicia OAuth local usando a API oficial do Google Agenda.

### `GET /api/google-calendar/events`

Lista proximos eventos do calendario primario.

### `POST /api/google-calendar/events`

Cria evento no calendario primario.

Payload:

```json
{
  "titulo": "Revisar calculo",
  "inicio": "2026-06-09T19:00",
  "fim": "2026-06-09T20:00",
  "descricao": "Criado pelo Assistente Pessoal."
}
```
