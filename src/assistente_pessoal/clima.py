"""Consulta de previsao do tempo usando Open-Meteo."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from assistente_pessoal.config import LocalizacaoConfig


@dataclass(frozen=True)
class PrevisaoClima:
    """Resumo amigavel das condicoes atuais e da previsao diaria."""

    cidade: str
    temperatura: float | None
    sensacao: float | None
    vento: float | None
    resumo_diario: str


class ClienteClima:
    """Cliente HTTP pequeno para a API publica Open-Meteo."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define o timeout padrao para evitar CLI travada em rede lenta."""
        self.timeout = timeout

    def obter_previsao(self, localizacao: LocalizacaoConfig) -> PrevisaoClima:
        """Busca clima atual e dados diarios para a localizacao configurada."""
        parametros = {
            "latitude": localizacao.latitude,
            "longitude": localizacao.longitude,
            "timezone": localizacao.timezone,
            "current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 1,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resposta = client.get("https://api.open-meteo.com/v1/forecast", params=parametros)
            resposta.raise_for_status()
            dados = resposta.json()
        return montar_previsao(localizacao.cidade, dados)


def montar_previsao(cidade: str, dados: dict) -> PrevisaoClima:
    """Transforma a resposta JSON da Open-Meteo em objeto de dominio."""
    atual = dados.get("current", {})
    diario = dados.get("daily", {})
    maxima = _primeiro(diario.get("temperature_2m_max"))
    minima = _primeiro(diario.get("temperature_2m_min"))
    chuva = _primeiro(diario.get("precipitation_probability_max"))
    resumo = f"maxima {maxima} C, minima {minima} C, chance de chuva {chuva}%"
    return PrevisaoClima(
        cidade=cidade,
        temperatura=atual.get("temperature_2m"),
        sensacao=atual.get("apparent_temperature"),
        vento=atual.get("wind_speed_10m"),
        resumo_diario=resumo,
    )


def formatar_previsao(previsao: PrevisaoClima) -> str:
    """Formata a previsao em uma frase curta para CLI e voz."""
    return (
        f"Clima em {previsao.cidade}: {previsao.temperatura} C, sensacao "
        f"{previsao.sensacao} C, vento {previsao.vento} km/h; hoje: "
        f"{previsao.resumo_diario}."
    )


def _primeiro(valores: list | None) -> object:
    """Retorna o primeiro item de uma lista da API ou ``None``."""
    return valores[0] if valores else None
