from assistente_pessoal.cambio import _float_ou_none


def test_float_ou_none() -> None:
    assert _float_ou_none("5.25") == 5.25
    assert _float_ou_none("invalid") is None
    assert _float_ou_none(None) is None
