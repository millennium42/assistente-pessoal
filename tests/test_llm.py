"""Testes do cliente LLM compativel com OpenAI."""

import httpx

from assistente_pessoal.config import LLMConfig
from assistente_pessoal.llm import ClienteLLM, resposta_fallback


class RespostaFake:
    """Resposta HTTP fake do endpoint de chat."""

    def raise_for_status(self) -> None:
        """Nao levanta erro para simular sucesso."""

    def json(self) -> dict:
        """Retorna uma estrutura compativel com Chat Completions."""
        return {"choices": [{"message": {"content": "Resposta teste"}}]}


class ClientFake:
    """Cliente HTTP fake usado pelo ClienteLLM."""

    def __init__(self, *args, **kwargs) -> None:
        """Aceita argumentos do httpx.Client."""

    def __enter__(self) -> "ClientFake":
        """Entra no contexto HTTP fake."""
        return self

    def __exit__(self, *args) -> None:
        """Sai do contexto HTTP fake."""

    def post(self, *args, **kwargs) -> RespostaFake:
        """Retorna resposta fake para POST."""
        return RespostaFake()


def test_llm_desabilitado_retorna_none() -> None:
    """Sem base URL/modelo, o cliente nao chama rede."""
    assert ClienteLLM(LLMConfig()).gerar("oi") is None
    assert "LLM" in resposta_fallback()


def test_llm_gera_resposta(monkeypatch) -> None:
    """Com configuracao minima, o cliente extrai texto da resposta HTTP."""
    monkeypatch.setattr("assistente_pessoal.llm.httpx.Client", ClientFake)
    cliente = ClienteLLM(LLMConfig(base_url="http://localhost:11434/v1", modelo="teste"))

    resposta = cliente.gerar("oi")

    assert resposta is not None
    assert resposta.texto == "Resposta teste"


def test_llm_usa_gemini_quando_chat_completions_nao_esta_configurado(monkeypatch) -> None:
    """Sem base_url/modelo, o chat ainda funciona se Gemini estiver disponivel."""
    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini.disponivel",
        lambda self: True,
    )
    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini.gerar_texto",
        lambda self, prompt, temperature=0.3: "Resposta Gemini",
    )
    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini._modelo",
        lambda self: "gemini-3.5-flash",
    )
    cliente = ClienteLLM(LLMConfig())

    resposta = cliente.gerar("oi", contexto="memoria local")

    assert resposta is not None
    assert resposta.texto == "Resposta Gemini"
    assert resposta.modelo == "gemini-3.5-flash"


def test_llm_trata_rate_limit_do_gemini_sem_traceback(monkeypatch) -> None:
    """Quando Gemini responde 429, a CLI deve receber uma mensagem amigavel."""
    def gerar_rate_limit(self, prompt, temperature=0.3):
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limit", request=request, response=response)

    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini.disponivel",
        lambda self: True,
    )
    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini.gerar_texto",
        gerar_rate_limit,
    )
    monkeypatch.setattr(
        "assistente_pessoal.llm.ClienteGemini._modelo",
        lambda self: "gemini-3.5-flash",
    )
    cliente = ClienteLLM(LLMConfig())

    resposta = cliente.gerar("oi")

    assert resposta is not None
    assert "429" in resposta.texto
    assert "muitas requisicoes" in resposta.texto
