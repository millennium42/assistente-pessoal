# Mapa de Dados

O mapa de dados tambem esta versionado em `assistente_pessoal.domain.privacy.DATA_INVENTORY` e exposto em `/api/privacy/data-map`.

| Dado | Sensibilidade | Armazenamento | Compartilhamento |
| --- | --- | --- | --- |
| Memorias Markdown | Pessoal | Vault local + indice SQLite | Somente com opt-in de LLM |
| Notas de estudo | Pessoal | Vault local | Somente com opt-in de LLM |
| Localizacao de clima | Pessoal | `config.toml` local | Open-Meteo recebe coordenadas |
| Feeds RSS e artistas | Pessoal | `config.toml` local | RSS/MusicBrainz recebem consultas |
| Audio temporario | Sensivel | WAV temporario | Nenhum; transcricao local |
| Chaves e tokens | Segredo | Ambiente local | Usados apenas pelo backend |
| Logs tecnicos | Operacional | Console/arquivos locais | Nenhum por padrao |

## Portabilidade

Use:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8777/api/privacy/export?destino=exports"
```

O arquivo JSON contem:

- data de exportacao;
- configuracao segura;
- mapa de dados;
- conteudo Markdown do vault.

## Eliminacao local

Use:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8777/api/privacy/purge"
```

A rotina apaga caches e indices gerados. Ela nao apaga notas Markdown do usuario.
