"""Testes do cliente LLM compativel com OpenAI."""

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
