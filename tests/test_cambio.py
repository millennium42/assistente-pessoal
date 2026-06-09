from datetime import datetime

from assistente_pessoal.cambio import _escolher_item_mais_recente


def test_escolher_item_mais_recente_prioriza_horario_mais_novo() -> None:
    antigo = {
        "code": "USD",
        "codein": "BRL",
        "bid": "5.1824",
        "pctChange": "0.10",
        "high": "5.22",
        "low": "5.13",
        "timestamp": "1780934864",
        "create_date": "2026-06-08 13:07:44",
    }
    novo = {
        "code": "USD",
        "codein": "BRL",
        "bid": "5.1843",
        "pctChange": "0.14",
        "high": "5.22",
        "low": "5.13",
        "timestamp": "1780938067",
        "create_date": "2026-06-08 14:01:07",
    }

    escolhido = _escolher_item_mais_recente([antigo, novo], "America/Sao_Paulo")

    assert escolhido == novo


def test_escolher_item_mais_recente_aceita_item_sem_horario_quando_for_unico() -> None:
    sem_horario = {
        "code": "USD",
        "codein": "BRL",
        "bid": "5.10",
        "pctChange": "0.00",
        "high": "5.11",
        "low": "5.09",
    }

    escolhido = _escolher_item_mais_recente([None, sem_horario], "America/Sao_Paulo")

    assert escolhido == sem_horario
