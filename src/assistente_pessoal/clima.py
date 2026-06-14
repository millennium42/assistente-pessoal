"""Consulta de previsao do tempo usando Open-Meteo.

Fornece abstracao para buscar as condicoes climaticas atuais,
alem da previsao diaria e semanal para a regiao pre-configurada,
sem depender de chaves de API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from assistente_pessoal.config import LocalizacaoConfig
from assistente_pessoal.core_datas import hoje_local, resolver_dia_previsao


@dataclass(frozen=True)
class PrevisaoClima:
    """Resumo amigavel das condicoes atuais e da previsao diaria.

    Attributes:
        cidade: Nome da cidade pesquisada.
        data_alvo: Data a qual a previsao se refere.
        e_hoje: Booleano que indica se a data alvo e hoje.
        temperatura_referencia: Temperatura principal para exibicao.
        sensacao: Sensacao termica aparente (None se for previsao futura).
        vento: Velocidade do vento.
        maxima: Temperatura maxima prevista.
        minima: Temperatura minima prevista.
        chuva: Probabilidade maxima de chuva no dia.
        codigo_tempo: Codigo numerico (WMO) do clima.
    """

    cidade: str
    data_alvo: date
    e_hoje: bool
    temperatura_referencia: float | None = None
    sensacao: float | None = None
    vento: float | None = None
    direcao_vento: int | None = None
    umidade: float | None = None
    pressao: float | None = None
    maxima: float | None = None
    minima: float | None = None
    chuva: float | None = None
    uv_max: float | None = None
    nascer_sol: str | None = None
    por_sol: str | None = None
    codigo_tempo: int | None = None

    @property
    def erro(self) -> bool:
        """Indica se houve erro ou ausência de dados na previsao."""
        return self.temperatura_referencia is None and self.maxima is None and self.minima is None


@dataclass(frozen=True)
class ResumoClimaDia:
    """Faixa compacta usada pelo dashboard para os proximos dias.

    Attributes:
        data: O dia da previsao.
        maxima: Temperatura maxima prevista.
        minima: Temperatura minima prevista.
        chuva: Probabilidade maxima de chuva.
        codigo_tempo: Codigo numerico (WMO) do clima.
    """

    data: date
    maxima: float | None
    minima: float | None
    chuva: float | None
    codigo_tempo: int | None


class ClienteClima:
    """Cliente HTTP pequeno para a API publica Open-Meteo."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define o timeout padrao para evitar CLI travada em rede lenta.

        Args:
            timeout: Tempo maximo em segundos aguardando a API.
        """
        self.timeout = timeout

    def obter_previsao(
        self,
        localizacao: LocalizacaoConfig,
        dia: str | None = None,
        data_referencia: date | None = None,
    ) -> PrevisaoClima:
        """Busca clima atual e previsao do dia desejado para a localizacao configurada.

        Args:
            localizacao: Dados de latitude, longitude e cidade.
            dia: Dia desejado em linguagem natural ('hoje', 'amanha', etc.).
            data_referencia: Opcional. Data base para resolver o dia natural.

        Returns:
            Um objeto PrevisaoClima preenchido.
        """
        referencia = data_referencia or hoje_local(localizacao.timezone)
        data_alvo = resolver_dia_previsao(dia, localizacao.timezone, referencia=referencia)
        forecast_days = max((data_alvo - referencia).days + 1, 1)
        parametros = {
            "latitude": localizacao.latitude,
            "longitude": localizacao.longitude,
            "timezone": localizacao.timezone,
            "current": (
                "temperature_2m,apparent_temperature,wind_speed_10m,"
                "wind_direction_10m,relative_humidity_2m,surface_pressure,weather_code"
            ),
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset,weather_code"
            ),
            "forecast_days": min(max(forecast_days, 1), 16),
        }
        with httpx.Client(timeout=self.timeout) as client:
            dados = self._buscar_payload(client, parametros)
        return montar_previsao(localizacao.cidade, dados, data_alvo)

    def obter_resumo_semana(
        self,
        localizacao: LocalizacaoConfig,
        dias: int = 7,
    ) -> list[ResumoClimaDia]:
        """Busca a faixa diaria de maximas e minimas da proxima semana.

        Args:
            localizacao: Configurações de localização (lat, long, fuso).
            dias: Quantos dias no futuro buscar (limite 16).

        Returns:
            Lista de objetos ResumoClimaDia com clima resumido por dia.
        """
        parametros = {
            "latitude": localizacao.latitude,
            "longitude": localizacao.longitude,
            "timezone": localizacao.timezone,
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            ),
            "forecast_days": min(max(dias, 1), 16),
        }
        with httpx.Client(timeout=self.timeout) as client:
            dados = self._buscar_payload(client, parametros)
        return montar_resumo_semana(dados)

    def _buscar_payload(self, client: httpx.Client, parametros: dict) -> dict:
        """Centraliza a chamada a Open-Meteo para evitar duplicacao nos casos de uso.

        Args:
            client: O cliente httpx.
            parametros: Dicionario de query string.

        Returns:
            JSON parseado da resposta da API.
        """
        resposta = client.get("https://api.open-meteo.com/v1/forecast", params=parametros)
        resposta.raise_for_status()
        return resposta.json()


def montar_previsao(cidade: str, dados: dict, data_alvo: date) -> PrevisaoClima:
    """Transforma a resposta JSON da Open-Meteo em objeto de dominio.

    Args:
        cidade: O nome da cidade em texto amigavel.
        dados: Dicionario retornado pela API.
        data_alvo: A data em foco, para decidir se extrai os dados atuais.

    Returns:
        Um objeto PrevisaoClima empacotado.

    Raises:
        ValueError: Se a API nao retornou previsao para o dia pedido.
    """
    atual = dados.get("current", {})
    diario = dados.get("daily", {})
    indice = _indice_data(diario.get("time"), data_alvo.isoformat())
    if indice is None:
        raise ValueError(f"A API nao devolveu previsao para {data_alvo.isoformat()}.")
    maxima = _valor_na_posicao(diario.get("temperature_2m_max"), indice)
    minima = _valor_na_posicao(diario.get("temperature_2m_min"), indice)
    e_hoje = data_alvo == hoje_local(dados.get("timezone", "UTC"))
    temperatura_referencia = (
        atual.get("temperature_2m") if e_hoje else _temperatura_media(maxima, minima)
    )
    nascer = _valor_na_posicao(diario.get("sunrise"), indice)
    por = _valor_na_posicao(diario.get("sunset"), indice)
    if nascer:
        nascer = nascer.split("T")[-1][:5]
    if por:
        por = por.split("T")[-1][:5]

    return PrevisaoClima(
        cidade=cidade,
        data_alvo=data_alvo,
        e_hoje=e_hoje,
        temperatura_referencia=temperatura_referencia,
        sensacao=atual.get("apparent_temperature") if e_hoje else None,
        vento=atual.get("wind_speed_10m"),
        direcao_vento=atual.get("wind_direction_10m"),
        umidade=atual.get("relative_humidity_2m"),
        pressao=atual.get("surface_pressure"),
        maxima=maxima,
        minima=minima,
        chuva=_valor_na_posicao(diario.get("precipitation_probability_max"), indice),
        uv_max=_valor_na_posicao(diario.get("uv_index_max"), indice),
        nascer_sol=nascer,
        por_sol=por,
        codigo_tempo=_valor_na_posicao(diario.get("weather_code"), indice)
        if not e_hoje
        else atual.get("weather_code"),
    )


def formatar_previsao(previsao: PrevisaoClima) -> str:
    """Formata a previsao em uma frase curta para CLI.

    Args:
        previsao: Objeto PrevisaoClima com os dados completos.

    Returns:
        Texto formatado amigavel para humanos.
    """
    if previsao.erro:
        return f"Previsao indisponivel para {previsao.cidade} em {previsao.data_alvo.isoformat()}."
    return (
        f"Previsao para {previsao.cidade} em {previsao.data_alvo.isoformat()}: "
        f"temperatura prevista em torno de {previsao.temperatura_referencia} C, "
        f"maxima {previsao.maxima} C, minima {previsao.minima} C, "
        f"chance de chuva {previsao.chuva}% e vento {previsao.vento} km/h."
    )


def montar_resumo_semana(dados: dict) -> list[ResumoClimaDia]:
    """Converte a serie diaria da API em uma lista compacta para o dashboard.

    Args:
        dados: O JSON retornado pela Open-Meteo.

    Returns:
        Uma lista ordenadas de resumos diarios de clima.
    """
    diario = dados.get("daily", {})
    datas = diario.get("time") or []
    saida: list[ResumoClimaDia] = []
    for indice, valor_data in enumerate(datas):
        saida.append(
            ResumoClimaDia(
                data=date.fromisoformat(valor_data),
                maxima=_valor_na_posicao(diario.get("temperature_2m_max"), indice),
                minima=_valor_na_posicao(diario.get("temperature_2m_min"), indice),
                chuva=_valor_na_posicao(diario.get("precipitation_probability_max"), indice),
                codigo_tempo=_valor_na_posicao(diario.get("weather_code"), indice),
            )
        )
    return saida


def _indice_data(datas: list[str] | None, data_alvo: str) -> int | None:
    """Retorna a posicao do dia pedido dentro da serie diaria.

    Args:
        datas: Lista de datas devolvidas no pacote 'daily'.
        data_alvo: Data em string (ISO) procurada.

    Returns:
        Indice inteiro ou None se ausente.
    """
    if not datas:
        return None
    try:
        return datas.index(data_alvo)
    except ValueError:
        return None


def _valor_na_posicao(valores: list | None, indice: int) -> object:
    """Le um valor da serie diaria de forma tolerante a payload incompleto.

    Args:
        valores: Lista de valores ou None.
        indice: A posicao esperada baseada na data alvo.

    Returns:
        O valor na posicao, ou None em caso de falha.
    """
    if not valores:
        return None
    if indice >= len(valores):
        return None
    return valores[indice]


def _temperatura_media(maxima: float | None, minima: float | None) -> float | None:
    """Cria uma referencia termica simples para dias futuros sem usar o 'agora' de hoje.

    Args:
        maxima: Temperatura maxima.
        minima: Temperatura minima.

    Returns:
        A media arredondada a uma casa decimal, ou o valor existente se faltar um.
    """
    if maxima is None and minima is None:
        return None
    if maxima is None:
        return minima
    if minima is None:
        return maxima
    return round((maxima + minima) / 2, 1)
