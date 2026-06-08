"""Testes da leitura de noticias de tecnologia."""

from datetime import date
from types import SimpleNamespace

from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias, texto_terminal_seguro


def test_listar_noticias_com_feed_mockado(monkeypatch) -> None:
    """Garante que feeds RSS sao normalizados em itens de noticia do dia."""
    feed = SimpleNamespace(
        feed={"title": "Fonte Teste"},
        entries=[
            {
                "title": "Titulo",
                "link": "https://exemplo.test",
                "published": "Mon, 08 Jun 2026 12:00:00 +0000",
            }
        ],
    )
    monkeypatch.setattr("assistente_pessoal.noticias.feedparser.parse", lambda _url: feed)

    noticias = ClienteNoticias().listar(
        ["https://feed.test"],
        limite=1,
        incluir_the_news_tecnologia=False,
        data_referencia=date(2026, 6, 8),
    )

    assert noticias[0].titulo == "Titulo"
    assert "Fonte Teste" in formatar_noticias(noticias)


def test_listar_noticias_ignora_itens_de_outro_dia(monkeypatch) -> None:
    """Remove itens RSS que nao foram publicados no dia de referencia."""
    feed = SimpleNamespace(
        feed={"title": "Fonte Teste"},
        entries=[
            {
                "title": "Ontem",
                "link": "https://exemplo.test/ontem",
                "published": "Sun, 07 Jun 2026 12:00:00 +0000",
            }
        ],
    )
    monkeypatch.setattr("assistente_pessoal.noticias.feedparser.parse", lambda _url: feed)

    noticias = ClienteNoticias().listar(
        ["https://feed.test"],
        limite=1,
        incluir_the_news_tecnologia=False,
        data_referencia=date(2026, 6, 8),
    )

    assert noticias == []


class RespostaTheNewsFake:
    """Resposta fake da API publica usada pelo portal The News."""

    def raise_for_status(self) -> None:
        """Simula uma resposta HTTP sem erro."""

    def json(self) -> dict:
        """Retorna um artigo de tecnologia no formato esperado."""
        return {
            "data": {
                "articles": [
                    {
                        "title": "AI em pauta",
                        "slug": "ai-em-pauta",
                        "publishedAt": "2026-06-08T12:00:00.000Z",
                        "publishedTimeAgo": "hoje",
                    }
                ]
            }
        }


class ClientTheNewsFake:
    """Cliente HTTP fake para testar The News sem rede."""

    def __init__(self, *args, **kwargs) -> None:
        """Aceita os mesmos argumentos basicos de httpx.Client."""

    def __enter__(self) -> "ClientTheNewsFake":
        """Entra no contexto HTTP fake."""
        return self

    def __exit__(self, *args) -> None:
        """Sai do contexto HTTP fake."""

    def get(self, *args, **kwargs) -> RespostaTheNewsFake:
        """Retorna uma resposta fake para qualquer GET."""
        return RespostaTheNewsFake()


def test_listar_the_news_tecnologia(monkeypatch) -> None:
    """Prioriza artigos de tecnologia do The News quando a fonte esta ligada."""
    monkeypatch.setattr("assistente_pessoal.noticias.httpx.Client", ClientTheNewsFake)

    noticias = ClienteNoticias().listar(
        [],
        limite=1,
        incluir_the_news_tecnologia=True,
        data_referencia=date(2026, 6, 8),
    )

    assert noticias[0].fonte == "the news - tecnologia"
    assert noticias[0].titulo == "AI em pauta"
    assert "thenews.com.br" in noticias[0].link


def test_texto_terminal_seguro_remove_caracteres_incompativeis() -> None:
    """Remove caracteres que consoles Windows antigos nao conseguem imprimir."""
    texto = "Titulo " + chr(0x1F9EA) + " com acento"
    assert texto_terminal_seguro(texto) == "Titulo  com acento"
