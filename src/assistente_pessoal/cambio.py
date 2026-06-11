"""Cotacoes de cambio usadas pelo dashboard.

Este modulo conecta-se a uma API publica (AwesomeAPI) para buscar a
cotacao atual do Dolar (USD) para Real (BRL) sem necessitar de chaves de API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx


@dataclass(frozen=True)
class CotacaoMoeda:
    """Cotacao normalizada entre duas moedas.

    Attributes:
        base: Moeda de origem (ex: 'USD').
        destino: Moeda de destino (ex: 'BRL').
        valor: Valor atual da cotacao (bid).
        variacao_percentual: Variacao nas ultimas 24h.
        maximo: Maior valor nas ultimas 24h.
        minimo: Menor valor nas ultimas 24h.
        horario: O timestamp em que a cotacao foi registrada.
        fonte: Nome do servico de onde a cotacao foi extraida.
        erro: Mensagem de erro caso a cotacao falhe.
    """

    base: str
    destino: str
    valor: float | None
    variacao_percentual: float | None
    maximo: float | None
    minimo: float | None
    horario: datetime | None
    fonte: str
    erro: str = ""


class ClienteCambio:
    """Consulta uma API publica de cambio com timeout curto para o painel."""

    def __init__(self, timeout: float = 6.0) -> None:
        """Inicializa o cliente.

        Args:
            timeout: Tempo limite em segundos para a requisicao de cambio.
        """
        self.timeout = timeout

    def obter_dolar_real(self, timezone: str = "America/Sao_Paulo") -> CotacaoMoeda:
        """Busca a cotacao USD/BRL mais recente disponivel.

        Args:
            timezone: O fuso horario a ser aplicado ao horario da cotacao.

        Returns:
            Objeto CotacaoMoeda preenchido com os dados ou contendo um erro.
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                candidatos = [
                    _buscar_cotacao(client, "https://economia.awesomeapi.com.br/json/last/USD-BRL"),
                    _buscar_cotacao(client, "https://economia.awesomeapi.com.br/json/USD-BRL"),
                ]
        except (httpx.HTTPError, ValueError) as exc:
            return _cotacao_indisponivel(str(exc))

        item = _escolher_item_mais_recente(candidatos, timezone)
        if item is None:
            return _cotacao_indisponivel("Resposta de cambio sem USDBRL.")

        horario = _extrair_horario(item, timezone)
        return CotacaoMoeda(
            base=item.get("code", "USD"),
            destino=item.get("codein", "BRL"),
            valor=_float_ou_none(item.get("bid")),
            variacao_percentual=_float_ou_none(item.get("pctChange")),
            maximo=_float_ou_none(item.get("high")),
            minimo=_float_ou_none(item.get("low")),
            horario=horario,
            fonte="AwesomeAPI",
        )


def _buscar_cotacao(client: httpx.Client, url: str) -> dict | None:
    """Busca uma resposta de cotacao e normaliza os formatos conhecidos da AwesomeAPI.

    Args:
        client: O cliente httpx ativo.
        url: O endpoint da API.

    Returns:
        Um dicionario com os dados da cotacao se existir, None caso contrario.
    """
    resposta = client.get(url, headers={"User-Agent": "assistente-pessoal/0.1.0"})
    resposta.raise_for_status()
    dados = resposta.json()
    if isinstance(dados, dict):
        item = dados.get("USDBRL")
        return item if isinstance(item, dict) else None
    if isinstance(dados, list) and dados and isinstance(dados[0], dict):
        return dados[0]
    return None


def _escolher_item_mais_recente(candidatos: list[dict | None], timezone: str) -> dict | None:
    """Escolhe a resposta com horario mais novo entre os endpoints consultados.

    Args:
        candidatos: Lista de dicionarios de cotacao.
        timezone: O fuso horario para converter os horarios.

    Returns:
        O dicionario correspondente a cotacao mais recente.
    """
    melhor_item: dict | None = None
    melhor_horario: datetime | None = None
    for item in candidatos:
        if not isinstance(item, dict):
            continue
        horario = _extrair_horario(item, timezone)
        if melhor_item is None:
            melhor_item = item
            melhor_horario = horario
            continue
        if horario is not None and (melhor_horario is None or horario > melhor_horario):
            melhor_item = item
            melhor_horario = horario
    return melhor_item


def _cotacao_indisponivel(erro: str) -> CotacaoMoeda:
    """Gera um objeto de cotacao padrao para representar falha.

    Args:
        erro: Mensagem de erro que motivou a falha.

    Returns:
        Objeto CotacaoMoeda em estado de erro.
    """
    return CotacaoMoeda(
        base="USD",
        destino="BRL",
        valor=None,
        variacao_percentual=None,
        maximo=None,
        minimo=None,
        horario=None,
        fonte="AwesomeAPI",
        erro=erro,
    )


def _float_ou_none(valor: object) -> float | None:
    """Tenta converter um valor para float de forma segura.

    Args:
        valor: Valor original retornado pela API.

    Returns:
        O valor em float, ou None se nao puder ser convertido.
    """
    try:
        return float(str(valor))
    except (TypeError, ValueError):
        return None


def _extrair_horario(item: dict, timezone: str) -> datetime | None:
    """Le o timestamp da cotacao retornado pela AwesomeAPI.

    Args:
        item: Dicionario com os dados.
        timezone: O timezone local alvo.

    Returns:
        Um objeto datetime, ou None se nao estiver disponivel.
    """
    fuso = ZoneInfo(timezone)
    timestamp = item.get("timestamp")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(int(str(timestamp)), tz=fuso)
        except (TypeError, ValueError, OSError):
            pass
    criado_em = item.get("create_date")
    if not criado_em:
        return None
    try:
        return datetime.strptime(str(criado_em), "%Y-%m-%d %H:%M:%S").replace(tzinfo=fuso)
    except ValueError:
        return None
