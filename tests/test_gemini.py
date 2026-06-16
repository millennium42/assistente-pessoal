"""Testes do cliente Gemini usado nos insights do dashboard."""

import json
from datetime import datetime

from assistente_pessoal.config import LLMConfig
from assistente_pessoal.gemini import ClienteGemini


class RespostaGeminiFake:
    """Resposta HTTP fake do endpoint generateContent."""

    def raise_for_status(self) -> None:
        """Simula sucesso HTTP."""

    def json(self) -> dict:
        """Entrega um payload compativel com o Gemini."""
        texto = json.dumps(
            {
                "agenda": {"resumo": "Dia organizado", "bullets": ["Primeiro bloco"]},
                "noticias": {"resumo": "Feed amplo", "bullets": ["The News em alta"]},
                "clima": {
                    "resumo": "Leve casaco",
                    "bullets": ["Chance moderada de chuva"],
                },
            }
        )
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": texto}
                        ]
                    }
                }
            ]
        }


class ClientFake:
    """Cliente HTTP fake usado pelo ClienteGemini."""

    def __init__(self, *args, **kwargs) -> None:
        """Aceita os parametros do httpx.Client."""

    def __enter__(self) -> "ClientFake":
        return self

    def __exit__(self, *args) -> None:
        """Sai do contexto fake."""

    def post(self, *args, **kwargs) -> RespostaGeminiFake:
        return RespostaGeminiFake()


class RespostaRateLimitFake:
    """Resposta fake que simula rate limit do Gemini."""

    def __init__(self) -> None:
        self.request = __import__("httpx").Request(
            "POST",
            "https://generativelanguage.googleapis.com/test",
        )

    def raise_for_status(self) -> None:
        response = __import__("httpx").Response(429, request=self.request)
        raise __import__("httpx").HTTPStatusError(
            "rate limit",
            request=self.request,
            response=response,
        )

    def json(self) -> dict:
        return {}


class ClientRateLimitFake(ClientFake):
    """Cliente fake que devolve 429."""

    def post(self, *args, **kwargs) -> RespostaRateLimitFake:
        return RespostaRateLimitFake()


def test_gemini_desabilitado_sem_chave(monkeypatch) -> None:
    """Sem chave no ambiente o cliente nao fica disponivel."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    assert cliente.disponivel() is False


def test_gemini_gera_json(monkeypatch) -> None:
    """Consegue converter a resposta do Gemini para dicionario."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientFake)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    dados = cliente.gerar_json("Resuma meu dia")

    assert dados["agenda"]["resumo"] == "Dia organizado"
    assert dados["clima"]["bullets"] == ["Chance moderada de chuva"]


def test_gemini_entra_em_cooldown_apos_rate_limit(monkeypatch) -> None:
    """Depois de um 429, o cliente deve ficar temporariamente indisponivel."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientRateLimitFake)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    try:
        cliente.gerar_texto("oi")
    except Exception:
        pass

    assert cliente.disponivel() is False
    assert cliente._indisponivel_ate is not None
    assert cliente._indisponivel_ate > datetime.now()
