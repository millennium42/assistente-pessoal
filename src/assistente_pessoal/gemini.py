"""Cliente enxuto para o endpoint GenerateContent do Gemini."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx

from assistente_pessoal.config import LLMConfig, ler_api_key

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODELO_PADRAO = "gemini-3.1-flash-lite"


class ClienteGemini:
    """Encapsula chamadas ao Gemini para respostas textuais ou JSON."""

    def __init__(self, config: LLMConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self._indisponivel_ate: datetime | None = None

    def disponivel(self) -> bool:
        """Considera o Gemini disponivel quando a chave de API existe."""
        return bool(self._ler_chave_api()) and not self._em_cooldown()

    def gerar_json(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        schema_hint: str | None = None,
    ) -> dict:
        """Solicita uma resposta JSON ao Gemini e converte para dicionario."""
        texto = self._post_generate_content(
            prompt,
            temperature=temperature,
            response_mime_type="application/json",
            schema_hint=schema_hint,
        )
        try:
            return json.loads(_extrair_json(texto))
        except json.JSONDecodeError as exc:
            self._marcar_indisponivel()
            raise ValueError("Gemini retornou JSON invalido.") from exc

    def gerar_texto(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        """Solicita uma resposta textual direta ao Gemini."""
        return self._post_generate_content(
            prompt,
            temperature=temperature,
            response_mime_type="text/plain",
        )

    def _post_generate_content(
        self,
        prompt: str,
        *,
        temperature: float,
        response_mime_type: str,
        schema_hint: str | None = None,
    ) -> str:
        """Executa a chamada HTTP ao Gemini e devolve o texto consolidado."""
        api_key = self._ler_chave_api()
        if not api_key:
            raise RuntimeError("Chave da API Gemini nao encontrada no ambiente.")
        url = f"{self._base_url().rstrip('/')}/models/{self._modelo().strip()}:generateContent"
        prompt_final = prompt
        if schema_hint:
            prompt_final = f"{prompt}\n\nEsquema esperado:\n{schema_hint}"
        with httpx.Client(timeout=self.timeout) as client:
            try:
                resposta = client.post(
                    url,
                    headers={"X-goog-api-key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt_final}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "response_mime_type": response_mime_type,
                        },
                    },
                )
                resposta.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {401, 403, 429} or exc.response.status_code >= 500:
                    self._indisponivel_ate = datetime.now() + timedelta(minutes=5)
                raise
            except httpx.TimeoutException:
                self._marcar_indisponivel()
                raise
            dados = resposta.json()
        candidatos = dados.get("candidates") or []
        if not candidatos:
            self._marcar_indisponivel()
            raise ValueError("Gemini nao retornou candidatos.")
        partes = candidatos[0].get("content", {}).get("parts") or []
        texto = "".join(
            parte.get("text", "") for parte in partes if isinstance(parte, dict)
        ).strip()
        if not texto:
            self._marcar_indisponivel()
            raise ValueError("Gemini retornou conteudo vazio.")
        return texto

    def _base_url(self) -> str:
        return self.config.base_url.strip() or GEMINI_BASE_URL

    def _modelo(self) -> str:
        return self.config.modelo.strip() or GEMINI_MODELO_PADRAO

    def _ler_chave_api(self) -> str:
        """Aceita a variavel configurada e faz fallback para GEMINI_API_KEY."""
        return ler_api_key(self.config.api_key_env, self.config.api_key) or ler_api_key(
            "GEMINI_API_KEY"
        )

    def _em_cooldown(self) -> bool:
        """Evita insistir no Gemini logo apos um rate limit."""
        return self._indisponivel_ate is not None and datetime.now() < self._indisponivel_ate

    def _marcar_indisponivel(self, minutos: int = 5) -> None:
        """Coloca o cliente em cooldown quando a resposta do Gemini nao e confiavel."""
        self._indisponivel_ate = datetime.now() + timedelta(minutes=minutos)


def _extrair_json(texto: str) -> str:
    """Aceita JSON puro ou cercado por fences Markdown."""
    conteudo = texto.strip()
    if conteudo.startswith("```"):
        linhas = conteudo.splitlines()
        if linhas:
            linhas = linhas[1:]
        if linhas and linhas[-1].strip() == "```":
            linhas = linhas[:-1]
        conteudo = "\n".join(linhas).strip()
    return conteudo
