"""Testes do cliente de clima com HTTP mockado."""

from datetime import date

from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import LocalizacaoConfig


class RespostaFake:
    """Resposta HTTP falsa com os metodos usados pelo cliente."""

    def raise_for_status(self) -> None:
        """Simula resposta sem erro HTTP."""

    def json(self) -> dict:
        """Devolve payload minimo da Open-Meteo."""
        return {
            "current": {
                "temperature_2m": 20.0,
                "apparent_temperature": 19.0,
                "wind_speed_10m": 12.0,
            },
            "daily": {
                "time": ["2026-06-08", "2026-06-09", "2026-06-10"],
                "temperature_2m_max": [25.0, 26.0, 27.0],
                "temperature_2m_min": [14.0, 15.0, 16.0],
                "precipitation_probability_max": [30, 10, 70],
            },
        }


class ClientFake:
    """Context manager que substitui httpx.Client nos testes."""

    def __init__(self, *args, **kwargs) -> None:
        """Aceita argumentos para imitar a assinatura de httpx.Client."""

    def __enter__(self) -> "ClientFake":
        """Entra no contexto HTTP falso."""
        return self

    def __exit__(self, *args) -> None:
        """Sai do contexto HTTP falso."""

    def get(self, *args, **kwargs) -> RespostaFake:
        """Retorna uma resposta fake para qualquer GET."""
        return RespostaFake()


def test_cliente_clima_formata_previsao(monkeypatch) -> None:
    """Verifica a transformacao da resposta de clima em texto final."""
    monkeypatch.setattr("assistente_pessoal.clima.httpx.Client", ClientFake)

    previsao = ClienteClima().obter_previsao(
        LocalizacaoConfig(cidade="Teste"), dia="amanha", data_referencia=date(2026, 6, 8)
    )

    assert "Teste" in formatar_previsao(previsao)
    assert previsao.temperatura_atual == 20.0
    assert previsao.maxima == 26.0


def test_cliente_clima_aceita_dia_da_semana(monkeypatch) -> None:
    """Converte nomes de dia em datas futuras de forma previsivel."""
    monkeypatch.setattr("assistente_pessoal.clima.httpx.Client", ClientFake)

    previsao = ClienteClima().obter_previsao(
        LocalizacaoConfig(cidade="Teste"),
        dia="quarta",
        data_referencia=date(2026, 6, 8),
    )

    assert previsao.data_alvo.isoformat() == "2026-06-10"
