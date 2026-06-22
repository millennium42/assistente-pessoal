"""Cliente enxuto que delega todas as respostas ao Gemini."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from assistente_pessoal.config import LLMConfig
from assistente_pessoal.gemini import ClienteGemini


@dataclass(frozen=True)
class RespostaLLM:
    """Resposta textual produzida por um modelo de linguagem.

    Attributes:
        texto: O conteudo da resposta gerada.
        modelo: O nome do modelo que gerou a resposta.
    """

    texto: str
    modelo: str


class ClienteLLM:
    """Camada fina mantida por compatibilidade sobre o cliente Gemini."""

    def __init__(self, config: LLMConfig, timeout: float = 45.0) -> None:
        """Inicializa o cliente LLM.

        Args:
            config: Objeto com a configuracao do Gemini.
            timeout: Tempo limite em segundos para aguardar a resposta da API.
        """
        self.config = config
        self.timeout = timeout
        self.gemini = ClienteGemini(config, timeout=timeout)

    def disponivel(self) -> bool:
        """Verifica se o Gemini esta pronto para responder."""
        return self.gemini.disponivel()

    def gerar(self, mensagem: str, contexto: str | None = None) -> RespostaLLM | None:
        """Envia uma mensagem ao LLM e retorna a resposta gerada.

        Args:
            mensagem: A mensagem do usuario a ser processada.
            contexto: Informacao opcional de contexto (dados, historico) para o prompt.

        Returns:
            Um objeto RespostaLLM com a resposta textual, ou None se o Gemini nao
            estiver configurado.
        """
        if not self.disponivel():
            return None
        try:
            resposta = self._gerar_via_gemini(mensagem, contexto=contexto)
            return RespostaLLM(texto=resposta, modelo=self.gemini._modelo())
        except httpx.HTTPStatusError as exc:
            return RespostaLLM(
                texto=_mensagem_erro_http_llm(exc),
                modelo=self.gemini._modelo(),
            )
        except httpx.HTTPError:
            return RespostaLLM(
                texto=(
                    "Nao consegui falar com o provedor de IA agora por um problema de rede. "
                    "Tente novamente em instantes."
                ),
                modelo=self.gemini._modelo(),
            )

    def _gerar_via_gemini(self, mensagem: str, contexto: str | None = None) -> str:
        """Envia a mensagem ao Gemini com um prompt curto de assistente pessoal."""
        prompt = (
            "Voce e um assistente pessoal em pt-BR. "
            "Seja direto, util e explique quando estiver usando memoria ou fontes externas.\n\n"
        )
        if contexto:
            prompt += f"Contexto local:\n{contexto}\n\n"
        prompt += f"Mensagem do usuario:\n{mensagem}"
        return self.gemini.gerar_texto(prompt, temperature=0.3)


def resposta_fallback() -> str:
    """Mensagem de fallback padrao quando a geracao por LLM nao e possivel.

    Returns:
        Um texto explicando as capacidades locais disponiveis sem IA.
    """
    return (
        "A APPA 0.3.2 exige o modelo Gemini (LLM) operante. O sistema esta bloqueado ate "
        "que a chave GEMINI_API_KEY seja configurada e validada."
    )


def _mensagem_erro_http_llm(exc: httpx.HTTPStatusError) -> str:
    """Traduz erros HTTP do provedor em mensagens amigaveis para a CLI."""
    status = exc.response.status_code
    if status == 429:
        return (
            "O provedor de IA atingiu o limite de uso agora (429 - muitas requisicoes). "
            "Espere um pouco e tente novamente."
        )
    if 500 <= status <= 599:
        return "O provedor de IA falhou temporariamente. Tente novamente em instantes."
    if status in {401, 403}:
        return (
            "A autenticacao da IA falhou. Confira a API key configurada e as permissoes da conta."
        )
    return f"Nao consegui completar a consulta de IA agora (HTTP {status})."
