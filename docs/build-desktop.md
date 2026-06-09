# Build Desktop

Esta pagina descreve o fluxo unico de distribuicao: aplicativo Windows gerado pelo Tauri, com backend Python empacotado como sidecar.

## Arquivos relevantes

- [build_setup.ps1](<D:\milla\OneDrive\Documentos\Assistente de IA pessoal\scripts\build_setup.ps1>)
- [build_sidecar.py](<D:\milla\OneDrive\Documentos\Assistente de IA pessoal\scripts\build_sidecar.py>)
- [tauri.conf.json](<D:\milla\OneDrive\Documentos\Assistente de IA pessoal\apps\desktop\src-tauri\tauri.conf.json>)
- [sidecar.ts](<D:\milla\OneDrive\Documentos\Assistente de IA pessoal\apps\desktop\src\sidecar.ts>)

## Fluxo

1. `build_setup.ps1` confere `uv`, `npm` e `cargo`.
2. O script sincroniza dependencias Python de desenvolvimento.
3. `npm install` prepara a GUI.
4. `build_sidecar.py` gera `dist-sidecar\assistente-pessoal-api.exe`.
5. O script tambem cria o nome de sidecar esperado pelo Tauri.
6. `npm run tauri:build` compila frontend, backend auxiliar e app desktop.
7. O `.exe` final aparece em `apps\desktop\src-tauri\target\release\bundle\nsis`.

## Comando

```powershell
.\scripts\build_setup.ps1
```

## Observacoes

- O app inicia a API local em `127.0.0.1:8777`.
- A GUI chama `http://127.0.0.1:8777/api` automaticamente quando roda dentro do Tauri.
- Em desenvolvimento web, o Vite encaminha `/api` para a API local.
- Credenciais locais nao entram no pacote final.
