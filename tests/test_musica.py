"""Testes do cliente MusicBrainz com HTTP mockado."""

from assistente_pessoal.musica import ClienteMusica, formatar_lancamentos


class RespostaFake:
    """Resposta falsa do MusicBrainz."""

    def raise_for_status(self) -> None:
        """Simula status HTTP valido."""

    def json(self) -> dict:
        """Retorna um release-group minimo."""
        return {
            "release-groups": [
                {
                    "id": "abc",
                    "title": "Album Teste",
                    "first-release-date": "2026-06-01",
                    "primary-type": "Album",
                }
            ]
        }


class ClientFake:
    """Cliente HTTP falso para MusicBrainz."""

    def __init__(self, *args, **kwargs) -> None:
        """Aceita argumentos do construtor real."""

    def __enter__(self) -> "ClientFake":
        """Entra no contexto HTTP falso."""
        return self

    def __exit__(self, *args) -> None:
        """Sai do contexto HTTP falso."""

    def get(self, *args, **kwargs) -> RespostaFake:
        """Retorna resposta falsa para qualquer busca."""
        return RespostaFake()


def test_listar_lancamentos(monkeypatch) -> None:
    """Busca lancamentos por artista sem chamar a rede."""
    monkeypatch.setattr("assistente_pessoal.musica.httpx.Client", ClientFake)

    lancamentos = ClienteMusica("teste/0.1", intervalo=0).listar_lancamentos(["Artista"])

    assert lancamentos[0].titulo == "Album Teste"
    assert "Artista" in formatar_lancamentos(lancamentos)
