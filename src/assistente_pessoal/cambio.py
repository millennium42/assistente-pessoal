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
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resposta = client.get(url, headers={"User-Agent": "assistente-pessoal/0.1.0"})
                resposta.raise_for_status()
                dados = resposta.json()
        except (httpx.HTTPError, ValueError) as exc:
            return _cotacao_indisponivel(str(exc))

        item = dados.get("USDBRL") if isinstance(dados, dict) else None
        if not isinstance(item, dict):
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
