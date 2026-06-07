"""Gravacao push-to-talk e transcricao local de voz."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

from assistente_pessoal.config import VozConfig


def ouvir_e_transcrever(config: VozConfig) -> str:
    """Grava um trecho curto de audio e devolve a transcricao em texto."""
    caminho_audio = gravar_audio_temporario(config)
    try:
        return transcrever_audio(caminho_audio, config)
    finally:
        caminho_audio.unlink(missing_ok=True)


def gravar_audio_temporario(config: VozConfig) -> Path:
    """Grava audio do microfone em WAV temporario usando sounddevice."""
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Dependencias de audio indisponiveis. Instale o projeto com `uv pip install -e .`."
        ) from exc

    audio = sd.rec(
        int(config.duracao_segundos * config.taxa_amostragem),
        samplerate=config.taxa_amostragem,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    amostras = np.clip(audio.flatten(), -1.0, 1.0)
    pcm16 = (amostras * 32767).astype("<i2").tobytes()
    arquivo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    caminho = Path(arquivo.name)
    arquivo.close()
    with wave.open(str(caminho), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(config.taxa_amostragem)
        wav.writeframes(pcm16)
    return caminho


def transcrever_audio(caminho_audio: Path, config: VozConfig) -> str:
    """Transcreve um arquivo de audio usando faster-whisper em CPU."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper nao esta instalado. Rode `uv pip install -e .` antes de usar voz."
        ) from exc

    modelo = WhisperModel(config.modelo_whisper, device="cpu", compute_type="int8")
    segmentos, _info = modelo.transcribe(str(caminho_audio), language=config.idioma)
    return " ".join(segmento.text.strip() for segmento in segmentos).strip()
