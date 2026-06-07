"""Testes da leitura de noticias por RSS."""

from types import SimpleNamespace

from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias


def test_listar_noticias_com_feed_mockado(monkeypatch) -> None:
    """Garante que feeds RSS sao normalizados em itens de noticia."""
    feed = SimpleNamespace(
        feed={"title": "Fonte Teste"},
        entries=[{"title": "Titulo", "link": "https://exemplo.test", "published": "hoje"}],
    )
    monkeypatch.setattr("assistente_pessoal.noticias.feedparser.parse", lambda _url: feed)

    noticias = ClienteNoticias().listar(["https://feed.test"], limite=1)

    assert noticias[0].titulo == "Titulo"
    assert "Fonte Teste" in formatar_noticias(noticias)
