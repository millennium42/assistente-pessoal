"""Cliente pequeno para provedores compativeis com Chat Completions."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from assistente_pessoal.config import LLMConfig, ler_api_key


@dataclass(frozen=True)
class RespostaLLM:
    """Resposta textual produzida por um modelo de linguagem."""

    texto: str
    modelo: str


class ClienteLLM:
    """Encapsula chamadas HTTP para um endpoint compativel com OpenAI."""

    def __init__(self, config: LLMConfig, timeout: float = 45.0) -> None:
        """Guarda a configuracao do provedor sem abrir conexoes antecipadamente."""
        self.config = config
        self.timeout = timeout

    def disponivel(self) -> bool:
        """Indica se o cliente tem base URL e modelo configurados."""
        return self.config.habilitado()

    def gerar(self, mensagem: str, contexto: str | None = None) -> RespostaLLM | None:
        """Gera uma resposta ou retorna ``None`` quando nao ha LLM configurado."""
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
        """Executa a requisicao HTTP de chat e extrai o texto principal."""
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
    """Descreve o que o assistente faz quando nao ha LLM configurado."""
    return (
        "Ainda nao ha LLM configurado. Posso executar comandos locais: clima, noticias, "
        "musica, memoria, estudo e voz push-to-talk."
    )
