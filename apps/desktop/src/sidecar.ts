export async function startSidecarIfDesktop(): Promise<void> {
  if (!("__TAURI_INTERNALS__" in window)) return;
  const { Command } = await import("@tauri-apps/plugin-shell");
  const command = Command.sidecar("assistente-pessoal-api", [
    "--host",
    "127.0.0.1",
    "--port",
    "8777",
  ]);
  await command.spawn();
}
