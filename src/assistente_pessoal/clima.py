"""Consulta de previsao do tempo usando Open-Meteo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from assistente_pessoal.config import LocalizacaoConfig
from assistente_pessoal.core_datas import hoje_local, resolver_dia_previsao


@dataclass(frozen=True)
class PrevisaoClima:
    """Resumo amigavel das condicoes atuais e da previsao diaria."""

    cidade: str
    data_alvo: date
    temperatura_atual: float | None
    sensacao: float | None
    vento: float | None
    maxima: float | None
    minima: float | None
    chuva: float | None


class ClienteClima:
    """Cliente HTTP pequeno para a API publica Open-Meteo."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define o timeout padrao para evitar CLI travada em rede lenta."""
        self.timeout = timeout

    def obter_previsao(
        self,
        localizacao: LocalizacaoConfig,
        dia: str | None = None,
        data_referencia: date | None = None,
    ) -> PrevisaoClima:
        """Busca clima atual e previsao do dia desejado para a localizacao configurada."""
        referencia = data_referencia or hoje_local(localizacao.timezone)
        data_alvo = resolver_dia_previsao(dia, localizacao.timezone, referencia=referencia)
        forecast_days = max((data_alvo - referencia).days + 1, 1)
        parametros = {
            "latitude": localizacao.latitude,
            "longitude": localizacao.longitude,
            "timezone": localizacao.timezone,
            "current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": min(max(forecast_days, 1), 16),
        }
        with httpx.Client(timeout=self.timeout) as client:
            resposta = client.get("https://api.open-meteo.com/v1/forecast", params=parametros)
            resposta.raise_for_status()
            dados = resposta.json()
        return montar_previsao(localizacao.cidade, dados, data_alvo)


def montar_previsao(cidade: str, dados: dict, data_alvo: date) -> PrevisaoClima:
    """Transforma a resposta JSON da Open-Meteo em objeto de dominio."""
    atual = dados.get("current", {})
    diario = dados.get("daily", {})
    indice = _indice_data(diario.get("time"), data_alvo.isoformat())
    if indice is None:
        raise ValueError(f"A API nao devolveu previsao para {data_alvo.isoformat()}.")
    return PrevisaoClima(
        cidade=cidade,
        data_alvo=data_alvo,
        temperatura_atual=atual.get("temperature_2m"),
        sensacao=atual.get("apparent_temperature"),
        vento=atual.get("wind_speed_10m"),
        maxima=_valor_na_posicao(diario.get("temperature_2m_max"), indice),
        minima=_valor_na_posicao(diario.get("temperature_2m_min"), indice),
        chuva=_valor_na_posicao(diario.get("precipitation_probability_max"), indice),
    )


def formatar_previsao(previsao: PrevisaoClima) -> str:
    """Formata a previsao em uma frase curta para CLI e voz."""
    return (
        f"Clima em {previsao.cidade} para {previsao.data_alvo.isoformat()}: "
        f"agora {previsao.temperatura_atual} C, sensacao {previsao.sensacao} C, "
        f"vento {previsao.vento} km/h; maxima {previsao.maxima} C, minima "
        f"{previsao.minima} C, chance de chuva {previsao.chuva}%."
    )


def _indice_data(datas: list[str] | None, data_alvo: str) -> int | None:
    """Retorna a posicao do dia pedido dentro da serie diaria."""
    if not datas:
        return None
    try:
        return datas.index(data_alvo)
    except ValueError:
        return None


def _valor_na_posicao(valores: list | None, indice: int) -> object:
    """Le um valor da serie diaria de forma tolerante a payload incompleto."""
    if not valores:
        return None
    if indice >= len(valores):
        return None
    return valores[indice]
