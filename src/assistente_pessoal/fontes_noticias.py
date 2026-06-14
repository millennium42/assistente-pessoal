"""Adaptadores de fontes de noticias usados pelo orquestrador.

Fornece adaptadores para diferentes tipos de fontes de noticias, como
API The News, feeds RSS/Atom padrão, pesquisas de interesse do Google News,
e sites HTML que incluem metadata JSON-LD (NewsArticle).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from urllib.parse import quote_plus, urljoin
from zoneinfo import ZoneInfo

import feedparser
import httpx

from assistente_pessoal import USER_AGENT
from assistente_pessoal.config import GrupoRssConfig, TheNewsConfig
from assistente_pessoal.core_datas import (
    extrair_data_iso,
    extrair_data_rss,
    normalizar_texto_ascii,
    publicado_no_dia,
)

PORTAIS_LOCAIS_CONFIAVEIS = (
    "diariosm.com.br",
    "bei.net.br",
)

THE_NEWS_CATEGORIAS_GERAIS = (
    "brasil",
    "mundo",
    "negocios",
    "economia",
    "tecnologia",
    "esportes",
    "variedades",
)


@dataclass(frozen=True)
class ItemFonteNoticia:
    """Noticia normalizada no nivel das fontes.

    Attributes:
        titulo: Titulo extraido.
        link: URL da noticia original.
        fonte: Nome do portal/agregador.
        publicado: String bruta da data de publicacao.
        publicado_em: Data e hora parseada.
        grupo: Chave do grupo que originou a noticia.
        interesse: Opcional. A palavra-chave se originada de interesse.
    """

    titulo: str
    link: str
    fonte: str
    publicado: str
    publicado_em: datetime | None
    grupo: str
    interesse: str = ""


class TheNewsSource:
    """Le artigos do The News usando a API publica consumida pelo proprio portal."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout conservador para nao travar a aplicacao.

        Args:
            timeout: Tempo maximo de espera em segundos.
        """
        self.timeout = timeout

    def listar(
        self,
        config: TheNewsConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
    ) -> list[ItemFonteNoticia]:
        """Busca artigos do The News filtrados pelo dia local.

        Args:
            config: A configuracao TheNewsConfig.
            limite: Numero maximo de resultados esperados.
            timezone: Fuso horario para bater dias.
            data_referencia: A data do dia buscado.

        Returns:
            Lista de noticias extraidas.
        """
        if not config.habilitado:
            return []
        url = "https://api.waffle.com.br/api/public/articles"
        categoria = config.categoria.strip()
        categorias = (categoria,) if categoria else ("", *THE_NEWS_CATEGORIAS_GERAIS)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                artigos = []
                for categoria_consulta in categorias:
                    params: dict[str, object] = {
                        "limit": max(limite * 3, 30),
                        "page": 1,
                        "isAds": "false",
                    }
                    if categoria_consulta:
                        params["category"] = categoria_consulta
                    resposta = client.get(
                        url,
                        params=params,
                        headers={"User-Agent": USER_AGENT},
                    )
                    resposta.raise_for_status()
                    dados = resposta.json()
                    artigos.extend(dados.get("data", {}).get("articles", []))
        except (httpx.HTTPError, ValueError):
            return []
        noticias: list[ItemFonteNoticia] = []
        vistos: set[str] = set()
        for artigo in artigos:
            publicado_em = extrair_data_iso(artigo.get("publishedAt"))
            if not publicado_no_dia(publicado_em, data_referencia, timezone):
                continue
            link = artigo.get("url") or artigo.get("canonicalUrl")
            slug = artigo.get("slug", "")
            if not link and slug:
                link = f"https://www.thenews.com.br/pt-BR/portal/news/{slug}"
            if link:
                link = urljoin("https://www.thenews.com.br", link)
            categoria_artigo = artigo.get("category") or {}
            categoria_nome = categoria_artigo.get("name") or categoria or "geral"
            categoria_slug = categoria_artigo.get("slug") or categoria
            chave = _chave_noticia(artigo.get("title", ""), link or slug)
            if chave in vistos:
                continue
            vistos.add(chave)
            link_categoria = "https://www.thenews.com.br/pt-BR/portal"
            if categoria_slug:
                link_categoria = (
                    f"https://www.thenews.com.br/pt-BR/portal/categories/{categoria_slug}"
                )
            noticias.append(
                ItemFonteNoticia(
                    titulo=artigo.get("title", "Sem titulo"),
                    link=link or link_categoria,
                    fonte=f"the news - {categoria_nome}",
                    publicado=artigo.get("publishedTimeAgo") or artigo.get("publishedAt") or "",
                    publicado_em=publicado_em,
                    grupo="the_news",
                )
            )
        return ordenar_itens_por_publicacao(noticias)[:limite]


class RssNewsSource:
    """Le feeds RSS/Atom e padroniza os itens para o dominio da aplicacao."""

    def listar(
        self,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ) -> list[ItemFonteNoticia]:
        """Busca noticias publicadas no periodo desejado a partir de feeds.

        Args:
            grupo: Identificador do grupo (ex: 'tech').
            config: A configuracao contendo as URLs dos feeds.
            limite: Limite maximo global de retorno.
            timezone: Fuso horario de verificacao.
            data_referencia: Data desejada para a publicacao.
            apenas_dia_atual: Filtrar apenas itens deste dia.

        Returns:
            Lista com as noticias do feed.
        """
        if not config.habilitado or not config.rss:
            return []
        noticias: list[ItemFonteNoticia] = []
        for url in config.rss:
            feed = feedparser.parse(url)
            fonte = feed.feed.get("title", config.titulo_fonte or url)
            for item in feed.entries[: max(limite * 3, 20)]:
                titulo = item.get("title", "Sem titulo")
                link = item.get("link", "")
                if config.palavras_chave and not noticia_parece_local(
                    titulo,
                    link,
                    config.palavras_chave,
                ):
                    continue
                publicado_em = extrair_data_rss(item)
                if apenas_dia_atual and not publicado_no_dia(
                    publicado_em, data_referencia, timezone
                ):
                    continue
                noticias.append(
                    ItemFonteNoticia(
                        titulo=titulo,
                        link=link,
                        fonte=fonte,
                        publicado=item.get("published") or item.get("updated") or "",
                        publicado_em=publicado_em,
                        grupo=grupo,
                    )
                )
                if len(noticias) >= limite:
                    break
            if len(noticias) >= limite:
                break
        return noticias


class InterestNewsSource:
    """Busca noticias por tags de interesse em agregadores RSS de portais."""

    def listar(
        self,
        interesses: list[str],
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ) -> list[ItemFonteNoticia]:
        """Consulta Google News RSS por interesse e devolve itens recentes.

        Args:
            interesses: Tags de termos livres a buscar.
            limite: Quantidade total esperada.
            timezone: Fuso para validacao de datas.
            data_referencia: Dia da consulta.
            apenas_dia_atual: Retornar somente os itens desse dia.

        Returns:
            Uma lista de noticias mesclada de diferentes queries.
        """
        termos = [" ".join(interesse.split()) for interesse in interesses if interesse.strip()]
        if not termos:
            return []
        noticias: list[ItemFonteNoticia] = []
        vistos: set[str] = set()
        limite_por_termo = max(8, min(24, limite // max(len(termos), 1) + 4))
        for termo in termos[:12]:
            url = _url_google_news_interesse(termo)
            feed = feedparser.parse(url)
            for item in feed.entries[: max(limite_por_termo * 2, 16)]:
                titulo = item.get("title", "Sem titulo")
                link = item.get("link", "")
                publicado_em = extrair_data_rss(item)
                if apenas_dia_atual and not publicado_no_dia(
                    publicado_em,
                    data_referencia,
                    timezone,
                ):
                    continue
                chave = _chave_noticia(titulo, link)
                if chave in vistos:
                    continue
                vistos.add(chave)
                noticias.append(
                    ItemFonteNoticia(
                        titulo=titulo,
                        link=link,
                        fonte=_fonte_interesse(item, termo),
                        publicado=item.get("published") or item.get("updated") or "",
                        publicado_em=publicado_em,
                        grupo="interesses",
                        interesse=termo,
                    )
                )
                if len(noticias) >= limite:
                    break
            if len(noticias) >= limite:
                break
        return ordenar_itens_por_publicacao(noticias)[:limite]


class HtmlJsonLdNewsSource:
    """Extrai noticias de paginas HTML que expoem JSON-LD de artigos."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout conservador para consultas HTML.

        Args:
            timeout: Tempo para timeout em segundos.
        """
        self.timeout = timeout

    def listar(
        self,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
    ) -> list[ItemFonteNoticia]:
        """Busca artigos em paginas HTML a partir de blocos JSON-LD.

        Args:
            grupo: O id deste grupo de fontes (ex: 'santa_maria').
            config: A configuracao com as URLs.
            limite: Limite maximo.
            timezone: Fuso horario para comparacao de tempo.
            data_referencia: Dia atual de referencia.
            apenas_dia_atual: Ignorar noticias fora do dia de referencia.

        Returns:
            As noticias raspadas da home via JSON-LD ou fallback visual.
        """
        if not config.habilitado or not config.urls:
            return []
        noticias: list[ItemFonteNoticia] = []
        vistos: set[str] = set()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for url in config.urls:
                try:
                    resposta = client.get(
                        url,
                        headers={"User-Agent": USER_AGENT},
                    )
                    resposta.raise_for_status()
                    html = resposta.text
                except httpx.HTTPError:
                    continue
                for artigo in extrair_artigos_json_ld(html):
                    titulo = str(
                        artigo.get("headline") or artigo.get("title") or artigo.get("name") or ""
                    ).strip()
                    link = str(
                        artigo.get("url")
                        or artigo.get("mainEntityOfPage")
                        or artigo.get("@id")
                        or url
                    ).strip()
                    if not titulo:
                        continue
                    link = urljoin(url, link)
                    if grupo == "santa_maria" and not noticia_parece_local(
                        titulo,
                        link,
                        config.palavras_chave,
                    ):
                        continue
                    publicado_em = extrair_data_iso(
                        artigo.get("datePublished") or artigo.get("dateModified")
                    )
                    if apenas_dia_atual and not publicado_no_dia(
                        publicado_em, data_referencia, timezone
                    ):
                        continue
                    chave = _chave_noticia(titulo, link)
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    noticias.append(
                        ItemFonteNoticia(
                            titulo=titulo,
                            link=link,
                            fonte=config.titulo_fonte or grupo.replace("_", " "),
                            publicado=str(
                                artigo.get("datePublished") or artigo.get("dateModified") or ""
                            ),
                            publicado_em=publicado_em,
                            grupo=grupo,
                        )
                    )
                noticias.extend(
                    self._listar_por_manchetes_html(
                        client=client,
                        grupo=grupo,
                        config=config,
                        limite=limite,
                        timezone=timezone,
                        data_referencia=data_referencia,
                        apenas_dia_atual=apenas_dia_atual,
                        origem=url,
                        html=html,
                        vistos=vistos,
                    )
                )
        return ordenar_itens_por_publicacao(noticias)[:limite]

    def _listar_por_manchetes_html(
        self,
        client: httpx.Client,
        grupo: str,
        config: GrupoRssConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
        apenas_dia_atual: bool,
        origem: str,
        html: str,
        vistos: set[str],
    ) -> list[ItemFonteNoticia]:
        """Usa manchetes clicaveis da home quando o site nao publica JSON-LD util."""
        noticias: list[ItemFonteNoticia] = []
        candidatos = extrair_links_manchetes(html, origem)
        for titulo, link in candidatos[: max(min(limite * 2, 36), 16)]:
            if grupo == "santa_maria" and not noticia_parece_local(
                titulo,
                link,
                config.palavras_chave,
            ):
                continue
            try:
                resposta_artigo = client.get(
                    link,
                    headers={"User-Agent": USER_AGENT},
                )
                resposta_artigo.raise_for_status()
            except httpx.HTTPError:
                continue
            publicado_em, publicado = extrair_data_artigo_html(resposta_artigo.text, timezone)
            if apenas_dia_atual and not publicado_no_dia(publicado_em, data_referencia, timezone):
                continue
            chave = _chave_noticia(titulo, link)
            if chave in vistos:
                continue
            vistos.add(chave)
            noticias.append(
                ItemFonteNoticia(
                    titulo=titulo,
                    link=link,
                    fonte=config.titulo_fonte or grupo.replace("_", " "),
                    publicado=publicado,
                    publicado_em=publicado_em,
                    grupo=grupo,
                )
            )
            if len(noticias) >= limite:
                break
        return ordenar_itens_por_publicacao(noticias)[:limite]


def extrair_artigos_json_ld(html: str) -> list[dict]:
    """Varre scripts JSON-LD e devolve apenas objetos com cara de artigo.

    Args:
        html: Corpo bruto HTML.

    Returns:
        Lista com as entidades JSON-LD de artigos da pagina.
    """
    artigos: list[dict] = []
    padrao = re.compile(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for trecho in padrao.findall(html):
        bruto = unescape(trecho).strip()
        if not bruto:
            continue
        try:
            dado = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        artigos.extend(_coletar_artigos(dado))
    return artigos


def extrair_links_manchetes(html: str, base_url: str) -> list[tuple[str, str]]:
    """Extrai links de manchetes visiveis quando a home nao oferece JSON-LD aproveitavel.

    Args:
        html: Corpo HTML da home.
        base_url: O endereço raiz de onde o HTML foi baixado.

    Returns:
        Uma lista de tuplas contendo (titulo_limpo, url_absoluta).
    """
    encontrados: list[tuple[str, str]] = []
    vistos: set[str] = set()
    padrao = re.compile(
        r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for href, conteudo in padrao.findall(html):
        titulo = re.sub(r"<[^>]+>", " ", conteudo)
        titulo = re.sub(r"\s+", " ", unescape(titulo)).strip(" -\n\r\t>")
        if len(titulo) < 30:
            continue
        link = urljoin(base_url, href.strip())
        if link in vistos or "/noticias/" not in link and "/plantao/" not in link:
            continue
        vistos.add(link)
        encontrados.append((titulo, link))
    return encontrados


def extrair_data_artigo_html(html: str, timezone: str) -> tuple[datetime | None, str]:
    """Le datas comuns de paginas jornalisticas brasileiras sem depender de JSON-LD.

    Args:
        html: O conteudo do artigo.
        timezone: O fuso para conversao local.

    Returns:
        Tupla com o datetime parseado e a string de origem.
    """
    candidatos_meta = [
        r'article:published_time"\s+content="([^"]+)"',
        r'article:modified_time"\s+content="([^"]+)"',
        r'datetime="([^"]+)"',
    ]
    for padrao in candidatos_meta:
        encontrados = re.findall(padrao, html, flags=re.IGNORECASE)
        for valor in encontrados:
            data = extrair_data_iso(valor)
            if data:
                return data, valor
    encontrado_texto = re.search(
        r"(Atualizado em|Publicado em)\s*:?\s*(\d{2}/\d{2}/\d{4})(?:\s+(\d{2}:\d{2}))?",
        html,
        flags=re.IGNORECASE,
    )
    if encontrado_texto:
        data_texto = encontrado_texto.group(2)
        hora_texto = encontrado_texto.group(3) or "00:00"
        valor = f"{data_texto} {hora_texto}"
        return datetime.strptime(valor, "%d/%m/%Y %H:%M").replace(tzinfo=ZoneInfo(timezone)), valor
    return None, ""


def noticia_parece_local(titulo: str, link: str, palavras_chave: list[str]) -> bool:
    """Aplica um filtro simples para reduzir ruido em fontes locais mistas.

    Args:
        titulo: Titulo da noticia.
        link: Link da noticia.
        palavras_chave: Lista de palavras de verificação.

    Returns:
        True se a noticia condiz com o escopo local, False senão.
    """
    link_normalizado = link.lower()
    if any(portal in link_normalizado for portal in PORTAIS_LOCAIS_CONFIAVEIS):
        return True
    if not palavras_chave:
        return True
    universo = normalizar_texto_ascii(f"{titulo} {link}").lower()
    return any(normalizar_texto_ascii(palavra).lower() in universo for palavra in palavras_chave)


def _url_google_news_interesse(termo: str) -> str:
    """Prepara a URL de feed de um termo no Google News.

    Args:
        termo: Expressao do assunto procurado.

    Returns:
        A url gerada para consumo via RSS.
    """
    consulta = quote_plus(f"{termo} when:1d")
    return f"https://news.google.com/rss/search?q={consulta}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def _fonte_interesse(item: object, termo: str) -> str:
    fonte = ""
    if isinstance(item, dict):
        origem = item.get("source") or {}
        if isinstance(origem, dict):
            fonte = str(origem.get("title") or "").strip()
    if not fonte:
        fonte = f"busca: {termo}"
    return fonte


def ordenar_itens_por_publicacao(itens: list[ItemFonteNoticia]) -> list[ItemFonteNoticia]:
    """Mantem fontes HTML e API na ordem mais recente possivel.

    Args:
        itens: Lista base.

    Returns:
        Lista ordenada decrescentemente por publicacao.
    """
    return sorted(
        itens,
        key=lambda item: item.publicado_em.timestamp() if item.publicado_em else float("-inf"),
        reverse=True,
    )


def _chave_noticia(titulo: object, link: object = "") -> str:
    titulo_normalizado = normalizar_texto_ascii(str(titulo)).lower().strip()
    titulo_normalizado = re.sub(r"\s+", " ", titulo_normalizado)
    if titulo_normalizado:
        return titulo_normalizado
    return str(link).strip().lower()


def _coletar_artigos(dado: object) -> list[dict]:
    """Percorre estruturas JSON-LD aninhadas em busca de itens do tipo artigo.

    Args:
        dado: Object dict (json tree).

    Returns:
        Lista com dados que correspondem a tipos jornalisticos de noticia.
    """
    encontrados: list[dict] = []
    if isinstance(dado, list):
        for item in dado:
            encontrados.extend(_coletar_artigos(item))
        return encontrados
    if not isinstance(dado, dict):
        return encontrados
    tipo = str(dado.get("@type", "")).lower()
    if tipo in {"newsarticle", "article", "blogposting"}:
        encontrados.append(dado)
    if "@graph" in dado:
        encontrados.extend(_coletar_artigos(dado["@graph"]))
    for chave in ("itemListElement", "mainEntity", "mainEntityOfPage"):
        if chave in dado:
            encontrados.extend(_coletar_artigos(dado[chave]))
    return encontrados
