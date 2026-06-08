"""Testes da leitura e priorizacao de noticias."""

from datetime import date, datetime

from assistente_pessoal.config import GrupoRssConfig, NoticiasConfig, TheNewsConfig
from assistente_pessoal.fontes_noticias import (
    InterestNewsSource,
    ItemFonteNoticia,
    TheNewsSource,
    extrair_artigos_json_ld,
    extrair_data_artigo_html,
    extrair_links_manchetes,
    noticia_parece_local,
)
from assistente_pessoal.noticias import (
    LIMITE_PADRAO_NOTICIAS,
    ClienteNoticias,
    Noticia,
    formatar_noticias,
    priorizar_noticias_por_interesses,
    rotulo_tempo_publicacao,
    texto_terminal_seguro,
)


class TheNewsFake:
    """Fonte fake para controlar um item recente do primeiro grupo."""

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


class TheNewsAntigoFake:
    """Fonte fake para garantir presenca do The News no recorte final."""

    def listar(self, config: TheNewsConfig, limite: int, timezone: str, data_referencia: date):
        """Entrega dois itens antigos do The News."""
        return [
            ItemFonteNoticia(
                titulo=f"The News antigo {indice}",
                link=f"https://thenews.test/antigo-{indice}",
                fonte="the news - mundo",
                publicado="hoje",
                publicado_em=datetime(2026, 6, 8, 8, indice),
                grupo="the_news",
            )
            for indice in range(2)
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
        """Devolve um item por grupo para testar a ordenacao final."""
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
        """Entrega Santa Maria como item mais antigo do recorte fake."""
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


class RssMuitosItensFake:
    """Fonte fake para validar limites altos sem depender de RSS externo."""

    def __init__(self) -> None:
        self.limites_recebidos: list[int] = []

    def listar(
        self,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ):
        """Devolve exatamente a quantidade solicitada."""
        self.limites_recebidos.append(limite)
        return [
            ItemFonteNoticia(
                titulo=f"Noticia {indice}",
                link=f"https://{grupo}.test/{indice}",
                fonte=grupo,
                publicado="2026-06-08",
                publicado_em=datetime(2026, 6, 8, 12, 0),
                grupo=grupo,
            )
            for indice in range(limite)
        ]


class InterestFake:
    """Fonte fake para noticias encontradas por interesses."""

    interesses_recebidos: list[str] = []

    def listar(
        self,
        interesses: list[str],
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ):
        """Entrega um item relacionado aos interesses informados."""
        self.interesses_recebidos = interesses
        return [
            ItemFonteNoticia(
                titulo="IA aplicada na educacao",
                link="https://interesses.test/ia",
                fonte="Portal de interesse",
                publicado="2026-06-08",
                publicado_em=datetime(2026, 6, 8, 11, 0),
                grupo="interesses",
            )
        ]


class RespostaTheNewsFake:
    """Resposta minima da API publica do The News."""

    def raise_for_status(self) -> None:
        """Simula resposta HTTP bem-sucedida."""

    def json(self) -> dict:
        """Retorna um artigo do dia com categoria propria."""
        return {
            "data": {
                "articles": [
                    {
                        "title": "Materia geral",
                        "slug": "materia-geral",
                        "publishedAt": "2026-06-08T09:02:00.000Z",
                        "publishedTimeAgo": "hoje",
                        "category": {"name": "Mundo", "slug": "mundo"},
                    }
                ]
            }
        }


class ClienteHttpTheNewsFake:
    """Cliente HTTP fake que registra parametros enviados ao The News."""

    params_recebidos: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        """Aceita os mesmos argumentos do httpx.Client."""

    def __enter__(self):
        """Suporta uso como context manager."""
        return self

    def __exit__(self, *args) -> None:
        """Fecha o context manager fake."""

    def get(self, url: str, params: dict, headers: dict) -> RespostaTheNewsFake:
        """Registra a chamada e devolve a resposta fake."""
        self.params_recebidos.append(params)
        return RespostaTheNewsFake()


class FeedInteresseFake:
    """Resultado minimo de um feed de busca por interesse."""

    entries = [
        {
            "title": "IA na educacao avanca em escolas",
            "link": "https://portal.test/ia-educacao",
            "published": "Mon, 08 Jun 2026 14:30:00 -0300",
            "source": {"title": "Portal Teste"},
        }
    ]


def test_organiza_noticias_por_publicacao_mais_recente() -> None:
    """Monta o feed final do item mais novo para o mais antigo."""
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
        "tech",
        "economia_global",
        "santa_maria",
    ]


def test_limite_alto_chega_ate_a_fonte_sem_teto_por_grupo() -> None:
    """Permite carregar muitos itens quando uma fonte tem volume suficiente."""
    rss = RssMuitosItensFake()
    config = NoticiasConfig(
        prioridades=["tech"],
        the_news=TheNewsConfig(habilitado=False),
        santa_maria=GrupoRssConfig(habilitado=False),
        tech=GrupoRssConfig(habilitado=True, rss=["https://tech.test"]),
        economia_global=GrupoRssConfig(habilitado=False),
    )
    cliente = ClienteNoticias(
        the_news_source=TheNewsFake(),
        rss_source=rss,
        html_source=HtmlFake(),
    )

    noticias = cliente.listar(config, limite=50, data_referencia=date(2026, 6, 8))

    assert len(noticias) == 50
    assert rss.limites_recebidos == [50]


def test_limite_padrao_de_noticias_e_100() -> None:
    """Mantem o dashboard e a CLI carregando ate 100 noticias por padrao."""
    assert LIMITE_PADRAO_NOTICIAS == 100


def test_cliente_noticias_busca_por_interesses_configurados() -> None:
    """Tags de interesse tambem disparam busca propria em portais de noticias."""
    interesses = InterestFake()
    config = NoticiasConfig(
        interesses_busca=["ia", "educacao"],
        prioridades=["tech"],
        the_news=TheNewsConfig(habilitado=False),
        santa_maria=GrupoRssConfig(habilitado=False),
        tech=GrupoRssConfig(habilitado=True, rss=["https://tech.test"]),
        economia_global=GrupoRssConfig(habilitado=False),
    )
    cliente = ClienteNoticias(
        the_news_source=TheNewsFake(),
        rss_source=RssFake(),
        html_source=HtmlFake(),
        interest_source=interesses,
    )

    noticias = cliente.listar(config, limite=5, data_referencia=date(2026, 6, 8))

    assert interesses.interesses_recebidos == ["ia", "educacao"]
    assert any(noticia.grupo == "interesses" for noticia in noticias)


def test_fonte_interesses_consulta_rss_de_noticias(monkeypatch) -> None:
    """Busca cada interesse em RSS de noticias e normaliza o portal retornado."""
    urls = []

    def parse_fake(url: str) -> FeedInteresseFake:
        urls.append(url)
        return FeedInteresseFake()

    monkeypatch.setattr("assistente_pessoal.fontes_noticias.feedparser.parse", parse_fake)

    noticias = InterestNewsSource().listar(
        ["ia educacao"],
        limite=5,
        timezone="America/Sao_Paulo",
        data_referencia=date(2026, 6, 8),
        apenas_dia_atual=True,
    )

    assert "news.google.com/rss/search" in urls[0]
    assert "ia+educacao" in urls[0]
    assert noticias[0].grupo == "interesses"
    assert noticias[0].fonte == "Portal Teste"


def test_recorte_final_preserva_the_news_mesmo_com_rss_mais_recente() -> None:
    """Nao deixa The News sumir quando outras fontes preenchem o limite."""
    rss = RssMuitosItensFake()
    config = NoticiasConfig(
        prioridades=["the_news", "tech"],
        santa_maria=GrupoRssConfig(habilitado=False),
        tech=GrupoRssConfig(habilitado=True, rss=["https://tech.test"]),
        economia_global=GrupoRssConfig(habilitado=False),
    )
    cliente = ClienteNoticias(
        the_news_source=TheNewsAntigoFake(),
        rss_source=rss,
        html_source=HtmlFake(),
    )

    noticias = cliente.listar(config, limite=50, data_referencia=date(2026, 6, 8))
    grupos = [noticia.grupo for noticia in noticias]

    assert len(noticias) == 50
    assert grupos.count("the_news") == 2
    assert grupos[-2:] == ["the_news", "the_news"]


def test_recorte_final_preserva_santa_maria_mesmo_com_rss_mais_recente() -> None:
    """Nao deixa a cobertura local sumir quando RSS geral preenche o limite."""
    rss = RssMuitosItensFake()
    config = NoticiasConfig(
        prioridades=["tech", "santa_maria"],
        the_news=TheNewsConfig(habilitado=False),
        santa_maria=GrupoRssConfig(
            habilitado=True,
            modo="midia_local",
            urls=["https://local.test"],
        ),
        tech=GrupoRssConfig(habilitado=True, rss=["https://tech.test"]),
        economia_global=GrupoRssConfig(habilitado=False),
    )
    cliente = ClienteNoticias(
        the_news_source=TheNewsFake(),
        rss_source=rss,
        html_source=HtmlFake(),
    )

    noticias = cliente.listar(config, limite=50, data_referencia=date(2026, 6, 8))
    grupos = [noticia.grupo for noticia in noticias]

    assert len(noticias) == 50
    assert grupos.count("santa_maria") == 1
    assert grupos.count("tech") == 49
    assert grupos[-1] == "santa_maria"


def test_the_news_sem_categoria_nao_envia_filtro(monkeypatch) -> None:
    """Categoria vazia deve buscar todas as editorias do The News."""
    ClienteHttpTheNewsFake.params_recebidos = []
    monkeypatch.setattr("assistente_pessoal.fontes_noticias.httpx.Client", ClienteHttpTheNewsFake)

    noticias = TheNewsSource().listar(
        TheNewsConfig(categoria=""),
        limite=10,
        timezone="America/Sao_Paulo",
        data_referencia=date(2026, 6, 8),
    )

    assert "category" not in ClienteHttpTheNewsFake.params_recebidos[0]
    assert noticias[0].fonte == "the news - Mundo"


def test_the_news_com_categoria_envia_filtro(monkeypatch) -> None:
    """Categoria preenchida continua permitindo filtro explicito."""
    ClienteHttpTheNewsFake.params_recebidos = []
    monkeypatch.setattr("assistente_pessoal.fontes_noticias.httpx.Client", ClienteHttpTheNewsFake)

    TheNewsSource().listar(
        TheNewsConfig(categoria="tecnologia"),
        limite=10,
        timezone="America/Sao_Paulo",
        data_referencia=date(2026, 6, 8),
    )

    assert ClienteHttpTheNewsFake.params_recebidos[0]["category"] == "tecnologia"


def test_texto_terminal_seguro_remove_caracteres_incompativeis() -> None:
    """Remove caracteres que consoles Windows antigos nao conseguem imprimir."""
    texto = "Titulo " + chr(0x1F9EA) + " com acento"
    assert texto_terminal_seguro(texto) == "Titulo  com acento"


def test_formatar_noticias_sem_itens() -> None:
    """Explica claramente quando nao ha nada no dia atual."""
    assert "Nenhuma noticia" in formatar_noticias([])


def test_rotulo_tempo_publicacao_prefere_minutos_e_horas() -> None:
    """Exibe a idade da noticia no escopo mais curto que continua legivel."""
    noticia_minutos = Noticia(
        titulo="Minutos",
        link="https://noticias.test/minutos",
        fonte="Fonte",
        publicado="2026-06-08T12:45:00-03:00",
        publicado_em=datetime(2026, 6, 8, 12, 45),
        grupo="tech",
    )
    noticia_horas = Noticia(
        titulo="Horas",
        link="https://noticias.test/horas",
        fonte="Fonte",
        publicado="2026-06-08T10:00:00-03:00",
        publicado_em=datetime(2026, 6, 8, 10, 0),
        grupo="tech",
    )
    agora = datetime(2026, 6, 8, 13, 0)

    assert rotulo_tempo_publicacao(noticia_minutos, agora=agora) == "ha 15 minutos"
    assert rotulo_tempo_publicacao(noticia_horas, agora=agora) == "ha 3 horas"


def test_formatar_noticias_omite_data_bruta() -> None:
    """Mostra tempo relativo em vez da data original da fonte."""
    noticia = Noticia(
        titulo="Materia recente",
        link="https://noticias.test/recentes",
        fonte="Fonte",
        publicado="2026-06-08T12:30:00-03:00",
        publicado_em=datetime(2026, 6, 8, 12, 30),
        grupo="tech",
    )

    texto = formatar_noticias([noticia], agora=datetime(2026, 6, 8, 13, 0))

    assert "ha 30 minutos" in texto
    assert "2026-06-08" not in texto
    assert "12:30" not in texto


def test_formatar_noticias_tambem_ordena_por_publicacao() -> None:
    """Garante ordem cronologica mesmo quando o formatador recebe uma lista solta."""
    antiga = Noticia(
        titulo="Antiga",
        link="https://noticias.test/antiga",
        fonte="Fonte",
        publicado="2026-06-08T09:00:00-03:00",
        publicado_em=datetime(2026, 6, 8, 9, 0),
        grupo="tech",
    )
    nova = Noticia(
        titulo="Nova",
        link="https://noticias.test/nova",
        fonte="Fonte",
        publicado="2026-06-08T12:00:00-03:00",
        publicado_em=datetime(2026, 6, 8, 12, 0),
        grupo="tech",
    )

    texto = formatar_noticias([antiga, nova], agora=datetime(2026, 6, 8, 13, 0))

    assert texto.index("Nova") < texto.index("Antiga")


def test_interesses_priorizam_noticias_relacionadas() -> None:
    """Tags de interesse sobem no feed sem apagar noticias fora do perfil."""
    generica = Noticia(
        titulo="Mercado abre em alta",
        link="https://noticias.test/mercado",
        fonte="Fonte",
        publicado="",
        publicado_em=datetime(2026, 6, 8, 12, 0),
        grupo="economia_global",
    )
    relacionada = Noticia(
        titulo="Nova ferramenta de IA para pesquisa",
        link="https://noticias.test/ia",
        fonte="Fonte",
        publicado="",
        publicado_em=datetime(2026, 6, 8, 9, 0),
        grupo="tech",
    )

    noticias = priorizar_noticias_por_interesses([generica, relacionada], ["ia"])

    assert noticias == [relacionada, generica]


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


def test_extrair_links_manchetes_do_html() -> None:
    """Recupera manchetes clicaveis quando a home local nao traz JSON-LD util."""
    html = """
    <a href="/noticias/geral/exemplo-local.123">Titulo local de Santa Maria com detalhes</a>
    <a href="/plantao/exemplo-plantao.456">Outra manchete local grande o suficiente para entrar</a>
    <a href="/curto">curto</a>
    """

    links = extrair_links_manchetes(html, "https://diariosm.com.br/")

    assert links[0][1] == "https://diariosm.com.br/noticias/geral/exemplo-local.123"
    assert len(links) == 2


def test_extrair_data_artigo_html_textual() -> None:
    """Aproveita a data textual comum em paginas locais para manter o filtro do dia atual."""
    html = "<span>Atualizado em: 08/06/2026 07:37</span>"

    publicado_em, publicado = extrair_data_artigo_html(html, "America/Sao_Paulo")

    assert publicado == "08/06/2026 07:37"
    assert publicado_em is not None
    assert publicado_em.date().isoformat() == "2026-06-08"


def test_noticia_parece_local() -> None:
    """Evita ruído de paginas locais mistas com conteudo fora de Santa Maria."""
    palavras = ["santa maria", "ufsm", "itaara"]

    assert noticia_parece_local("Acidente em Santa Maria", "https://x.test", palavras)
    assert not noticia_parece_local("Mega-Sena acumula", "https://x.test", palavras)
    assert noticia_parece_local(
        "Mega-Sena acumula",
        "https://diariosm.com.br/noticias/geral/exemplo.123",
        palavras,
    )
    assert noticia_parece_local(
        "Plantao regional",
        "https://bei.net.br/plantao/exemplo.456",
        palavras,
    )
    assert noticia_parece_local(
        "Obra avanca na região central",
        "https://x.test",
        ["regiao central"],
    )
