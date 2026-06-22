"""Testes do cliente Gemini usado nos insights do dashboard."""

import json
from datetime import datetime

import httpx

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
        return {"candidates": [{"content": {"parts": [{"text": texto}]}}]}


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


class ClientCapturaPayload(ClientFake):
    """Cliente fake que preserva o JSON enviado ao Gemini."""

    payloads: list[dict] = []

    def post(self, *args, **kwargs) -> RespostaGeminiFake:
        self.payloads.append(kwargs["json"])
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


class RespostaAuthFake:
    """Resposta fake que simula erro de autenticacao no Gemini."""

    def __init__(self, status_code: int) -> None:
        self.request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        response = httpx.Response(self.status_code, request=self.request)
        raise httpx.HTTPStatusError("auth error", request=self.request, response=response)

    def json(self) -> dict:
        return {}


class ClientAuthFake(ClientFake):
    """Cliente fake que devolve 401 ou 403."""

    def __init__(self, status_code: int) -> None:
        super().__init__()
        self.status_code = status_code

    def post(self, *args, **kwargs) -> RespostaAuthFake:
        return RespostaAuthFake(self.status_code)


class ClientServerErrorFake(ClientFake):
    """Cliente fake que devolve erro 503 do Gemini."""

    def post(self, *args, **kwargs) -> RespostaAuthFake:
        return RespostaAuthFake(503)


class ClientTimeoutFake(ClientFake):
    """Cliente fake que simula timeout do Gemini."""

    def post(self, *args, **kwargs):
        raise httpx.ReadTimeout("timeout")


class RespostaJsonInvalidoFake:
    """Resposta fake com texto nao parseavel como JSON."""

    def raise_for_status(self) -> None:
        """Simula sucesso HTTP."""

    def json(self) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": "{invalido"}]}}]}


class ClientJsonInvalidoFake(ClientFake):
    """Cliente fake que devolve JSON invalido no corpo textual."""

    def post(self, *args, **kwargs) -> RespostaJsonInvalidoFake:
        return RespostaJsonInvalidoFake()


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


def test_gemini_envia_limite_de_tokens_e_mime_type_oficial(monkeypatch) -> None:
    """Limita o tamanho da resposta para evitar gasto desnecessario de tokens."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    ClientCapturaPayload.payloads = []
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientCapturaPayload)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    cliente.gerar_json("Resuma meu dia", max_output_tokens=321)

    generation_config = ClientCapturaPayload.payloads[0]["generationConfig"]
    assert generation_config["maxOutputTokens"] == 321
    assert generation_config["responseMimeType"] == "application/json"


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


def test_gemini_entra_em_cooldown_apos_erro_401(monkeypatch) -> None:
    """Erros de autenticacao tambem bloqueiam a operacao do app temporariamente."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr(
        "assistente_pessoal.gemini.httpx.Client",
        lambda *args, **kwargs: ClientAuthFake(401),
    )
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    try:
        cliente.gerar_texto("oi")
    except httpx.HTTPStatusError:
        pass

    assert cliente.disponivel() is False


def test_gemini_entra_em_cooldown_apos_timeout(monkeypatch) -> None:
    """Timeout do Gemini deve empurrar o app de volta para estado bloqueado."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientTimeoutFake)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    try:
        cliente.gerar_texto("oi")
    except httpx.TimeoutException:
        pass

    assert cliente.disponivel() is False


def test_gemini_entra_em_cooldown_apos_erro_503(monkeypatch) -> None:
    """Erros 5xx do Gemini devem bloquear novas tentativas temporariamente."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientServerErrorFake)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    try:
        cliente.gerar_texto("oi")
    except httpx.HTTPStatusError:
        pass

    assert cliente.disponivel() is False


def test_gemini_entra_em_cooldown_apos_json_invalido(monkeypatch) -> None:
    """Resposta textual invalida tambem desabilita a operacao estruturada."""
    monkeypatch.setenv("GEMINI_API_KEY", "teste")
    monkeypatch.setattr("assistente_pessoal.gemini.httpx.Client", ClientJsonInvalidoFake)
    cliente = ClienteGemini(LLMConfig(api_key_env="GEMINI_API_KEY"))

    try:
        cliente.gerar_json("oi")
    except ValueError:
        pass

    assert cliente.disponivel() is False
