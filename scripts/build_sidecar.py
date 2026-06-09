"""Build do sidecar Python usado pelo desktop Tauri."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _windows_target_triple() -> str:
    """Retorna o alvo padrao usado pelo Tauri em builds Windows locais."""
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "x86_64-pc-windows-msvc"
    if machine in {"arm64", "aarch64"}:
        return "aarch64-pc-windows-msvc"
    return "i686-pc-windows-msvc"


def main() -> None:
    """Gera executavel local da API com PyInstaller."""
    raiz = Path(__file__).resolve().parents[1]
    dist = raiz / "dist-sidecar"
    shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir(exist_ok=True)
    nome = "assistente-pessoal-api"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--name",
            nome,
            "--distpath",
            str(dist),
            "--workpath",
            str(raiz / "build" / "pyinstaller"),
            "--specpath",
            str(raiz / "build" / "pyinstaller"),
            "src/assistente_pessoal/api/server.py",
        ],
        cwd=raiz,
        check=True,
    )
    if platform.system() == "Windows":
        base_exe = dist / f"{nome}.exe"
        tauri_exe = dist / f"{nome}-{_windows_target_triple()}.exe"
        shutil.copy2(base_exe, tauri_exe)
    shutil.rmtree(raiz / "build" / "pyinstaller", ignore_errors=True)


if __name__ == "__main__":
    main()
