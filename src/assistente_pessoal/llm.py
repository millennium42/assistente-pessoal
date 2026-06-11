"""Cliente pequeno para provedores compativeis com Chat Completions.

Fornece uma interface simplificada para comunicar com modelos de linguagem
(LLMs) usando a API padrao da OpenAI, permitindo integrar ferramentas locais
(como Ollama) ou servicos remotos.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from assistente_pessoal.config import LLMConfig, ler_api_key


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
    """Encapsula chamadas HTTP para um endpoint compativel com OpenAI."""

    def __init__(self, config: LLMConfig, timeout: float = 45.0) -> None:
        """Inicializa o cliente LLM.

        Args:
            config: Objeto com a configuracao do modelo, base_url, etc.
            timeout: Tempo limite em segundos para aguardar a resposta da API.
        """
        self.config = config
        self.timeout = timeout

    def disponivel(self) -> bool:
        """Verifica se ha informacoes suficientes (URL e modelo) para chamada.

        Returns:
            True se o cliente estiver pronto para uso, False caso contrario.
        """
        return self.config.habilitado()

    def gerar(self, mensagem: str, contexto: str | None = None) -> RespostaLLM | None:
        """Envia uma mensagem ao LLM e retorna a resposta gerada.

        Args:
            mensagem: A mensagem do usuario a ser processada.
            contexto: Informacao opcional de contexto (dados, historico) para o prompt.

        Returns:
            Um objeto RespostaLLM com a resposta textual, ou None se o LLM nao estiver configurado.
        """
        if not self.disponivel():
            return None
        mensagens = [
            {
                "role": "system",
                "content": (
                    "Voce e um assistente pessoal em pt-BR. Seja direto, util e explique "
                    "quando estiver usando memoria ou fontes externas."
                ),
            }
        ]
        if contexto:
            mensagens.append({"role": "system", "content": f"Contexto local:\n{contexto}"})
        mensagens.append({"role": "user", "content": mensagem})
        resposta = self._post_chat(mensagens)
        return RespostaLLM(texto=resposta, modelo=self.config.modelo)

    def _post_chat(self, mensagens: list[dict[str, str]]) -> str:
        """Executa a requisicao HTTP de chat para a API do provedor e extrai o conteudo.

        Args:
            mensagens: Lista de dicionarios contendo o historico do chat.

        Returns:
            A string com a resposta gerada pelo modelo.

        Raises:
            httpx.HTTPStatusError: Caso ocorra erro na comunicacao com a API.
        """
        base_url = self.config.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        api_key = ler_api_key(self.config.api_key_env) or "ollama"
        with httpx.Client(timeout=self.timeout) as client:
            resposta = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": self.config.modelo, "messages": mensagens, "temperature": 0.3},
            )
            resposta.raise_for_status()
            dados = resposta.json()
        return dados["choices"][0]["message"]["content"].strip()


def resposta_fallback() -> str:
    """Mensagem de fallback padrao quando a geracao por LLM nao e possivel.

    Returns:
        Um texto explicando as capacidades locais disponiveis sem IA.
    """
    return (
        "Ainda nao ha LLM configurado. Posso executar comandos locais: clima, noticias, "
        "memoria e agenda."
    )
