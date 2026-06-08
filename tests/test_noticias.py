"""Testes da leitura e priorizacao de noticias."""

from datetime import date, datetime

from assistente_pessoal.config import GrupoRssConfig, NoticiasConfig, TheNewsConfig
from assistente_pessoal.fontes_noticias import ItemFonteNoticia, extrair_artigos_json_ld
from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias, texto_terminal_seguro


class TheNewsFake:
    """Fonte fake para controlar a prioridade do primeiro grupo."""

    def listar(self, config: TheNewsConfig, limite: int, timezone: str, data_referencia: date):
        """Entrega um unico item do The News."""
        return [
            ItemFonteNoticia(
                titulo="The News primeiro",
                link="https://thenews.test/1",
                fonte="the news - tecnologia",
                publicado="hoje",
                publicado_em=datetime(2026, 6, 8, 12, 0),
                grupo="the_news",
            )
        ]


class RssFake:
    """Fonte fake para feeds RSS agrupados."""

    def listar(
        self,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ):
        """Devolve um item por grupo para testar a ordem de montagem."""
        titulo = {
            "tech": "Tech depois",
            "economia_global": "Economia por ultimo",
            "santa_maria": "Santa Maria via RSS",
        }[grupo]
        return [
            ItemFonteNoticia(
                titulo=titulo,
                link=f"https://{grupo}.test/1",
                fonte=grupo,
                publicado="2026-06-08",
                publicado_em=datetime(2026, 6, 8, 10, 0),
                grupo=grupo,
            )
        ]


class HtmlFake:
    """Fonte fake para HTML local/economico."""

    def listar(
        self,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ):
        """Entrega Santa Maria antes de tech quando a prioridade assim exigir."""
        if grupo != "santa_maria":
            return []
        return [
            ItemFonteNoticia(
                titulo="Santa Maria no meio",
                link="https://santamaria.test/1",
                fonte="santa maria - midia local",
                publicado="2026-06-08",
                publicado_em=datetime(2026, 6, 8, 9, 0),
                grupo="santa_maria",
            )
        ]


def test_prioriza_grupos_na_ordem_configurada() -> None:
    """Monta o feed final respeitando a prioridade The News > Santa Maria > Tech > Economia."""
    config = NoticiasConfig(
        the_news=TheNewsConfig(habilitado=True),
        santa_maria=GrupoRssConfig(
            habilitado=True, modo="midia_local", urls=["https://local.test"]
        ),
        tech=GrupoRssConfig(habilitado=True, rss=["https://tech.test"]),
        economia_global=GrupoRssConfig(habilitado=True, rss=["https://economia.test"]),
    )
    cliente = ClienteNoticias(
        the_news_source=TheNewsFake(),
        rss_source=RssFake(),
        html_source=HtmlFake(),
    )

    noticias = cliente.listar(config, limite=4, data_referencia=date(2026, 6, 8))

    assert [noticia.grupo for noticia in noticias] == [
        "the_news",
        "santa_maria",
        "tech",
        "economia_global",
    ]


def test_texto_terminal_seguro_remove_caracteres_incompativeis() -> None:
    """Remove caracteres que consoles Windows antigos nao conseguem imprimir."""
    texto = "Titulo " + chr(0x1F9EA) + " com acento"
    assert texto_terminal_seguro(texto) == "Titulo  com acento"


def test_formatar_noticias_sem_itens() -> None:
    """Explica claramente quando nao ha nada no dia atual."""
    assert "Nenhuma noticia" in formatar_noticias([])


def test_extrair_artigos_json_ld() -> None:
    """Coleta artigos de um HTML com JSON-LD, base da midia local e economia global."""
    html = """
    <html><head>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"NewsArticle","headline":"Titulo local",
       "url":"/noticia","datePublished":"2026-06-08T09:00:00-03:00"}
      </script>
    </head></html>
    """

    artigos = extrair_artigos_json_ld(html)

    assert artigos[0]["headline"] == "Titulo local"
