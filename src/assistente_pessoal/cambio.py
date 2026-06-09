"""Cotacoes de cambio usadas pelo dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx


@dataclass(frozen=True)
class CotacaoMoeda:
    """Cotacao normalizada entre duas moedas."""

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
        self.timeout = timeout

    def obter_dolar_real(self, timezone: str = "America/Sao_Paulo") -> CotacaoMoeda:
        """Busca a cotacao USD/BRL mais recente disponivel."""
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
    """Busca uma resposta de cotacao e normaliza os formatos conhecidos da AwesomeAPI."""
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
    """Escolhe a resposta com horario mais novo entre os endpoints consultados."""
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
    try:
        return float(str(valor))
    except (TypeError, ValueError):
        return None


def _extrair_horario(item: dict, timezone: str) -> datetime | None:
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
