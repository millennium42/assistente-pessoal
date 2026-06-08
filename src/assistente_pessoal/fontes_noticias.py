"""Adaptadores de fontes de noticias usados pelo orquestrador."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from urllib.parse import urljoin

import feedparser
import httpx

from assistente_pessoal.config import GrupoRssConfig, TheNewsConfig
from assistente_pessoal.core_datas import extrair_data_iso, extrair_data_rss, publicado_no_dia


@dataclass(frozen=True)
class ItemFonteNoticia:
    """Noticia normalizada no nivel das fontes."""

    titulo: str
    link: str
    fonte: str
    publicado: str
    publicado_em: datetime | None
    grupo: str


class TheNewsSource:
    """Le artigos do The News usando a API publica consumida pelo proprio portal."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout conservador para nao travar a aplicacao."""
        self.timeout = timeout

    def listar(
        self,
        config: TheNewsConfig,
        limite: int,
        timezone: str,
        data_referencia: date,
    ) -> list[ItemFonteNoticia]:
        """Busca artigos da categoria configurada filtrados pelo dia local."""
        if not config.habilitado:
            return []
        url = "https://api.waffle.com.br/api/public/articles"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resposta = client.get(
                    url,
                    params={
                        "limit": max(limite * 3, 20),
                        "category": config.categoria,
                        "page": 1,
                        "isAds": "false",
                    },
                    headers={"User-Agent": "assistente-pessoal/0.1.0"},
                )
                resposta.raise_for_status()
                dados = resposta.json()
        except (httpx.HTTPError, ValueError):
            return []
        artigos = dados.get("data", {}).get("articles", [])
        noticias: list[ItemFonteNoticia] = []
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
            noticias.append(
                ItemFonteNoticia(
                    titulo=artigo.get("title", "Sem titulo"),
                    link=link
                    or f"https://www.thenews.com.br/pt-BR/portal/categories/{config.categoria}",
                    fonte=f"the news - {config.categoria}",
                    publicado=artigo.get("publishedTimeAgo") or artigo.get("publishedAt") or "",
                    publicado_em=publicado_em,
                    grupo="the_news",
                )
            )
            if len(noticias) >= limite:
                break
        return noticias


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
        """Busca noticias publicadas no periodo desejado a partir de feeds."""
        if not config.habilitado or not config.rss:
            return []
        noticias: list[ItemFonteNoticia] = []
        for url in config.rss:
            feed = feedparser.parse(url)
            fonte = feed.feed.get("title", config.titulo_fonte or url)
            for item in feed.entries[: max(limite * 3, 20)]:
                publicado_em = extrair_data_rss(item)
                if apenas_dia_atual and not publicado_no_dia(
                    publicado_em, data_referencia, timezone
                ):
                    continue
                noticias.append(
                    ItemFonteNoticia(
                        titulo=item.get("title", "Sem titulo"),
                        link=item.get("link", ""),
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


class HtmlJsonLdNewsSource:
    """Extrai noticias de paginas HTML que expoem JSON-LD de artigos."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout conservador para consultas HTML."""
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
        """Busca artigos em paginas HTML a partir de blocos JSON-LD."""
        if not config.habilitado or not config.urls:
            return []
        noticias: list[ItemFonteNoticia] = []
        vistos: set[tuple[str, str]] = set()
        for url in config.urls:
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    resposta = client.get(url, headers={"User-Agent": "assistente-pessoal/0.1.0"})
                    resposta.raise_for_status()
                    html = resposta.text
            except httpx.HTTPError:
                continue
            for artigo in extrair_artigos_json_ld(html):
                titulo = str(
                    artigo.get("headline") or artigo.get("title") or artigo.get("name") or ""
                ).strip()
                link = str(
                    artigo.get("url") or artigo.get("mainEntityOfPage") or artigo.get("@id") or url
                ).strip()
                if not titulo:
                    continue
                link = urljoin(url, link)
                publicado_em = extrair_data_iso(
                    artigo.get("datePublished") or artigo.get("dateModified")
                )
                if apenas_dia_atual and not publicado_no_dia(
                    publicado_em, data_referencia, timezone
                ):
                    continue
                chave = (titulo.lower(), link)
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
                if len(noticias) >= limite:
                    return noticias
        return noticias


def extrair_artigos_json_ld(html: str) -> list[dict]:
    """Varre scripts JSON-LD e devolve apenas objetos com cara de artigo."""
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


def _coletar_artigos(dado: object) -> list[dict]:
    """Percorre estruturas JSON-LD aninhadas em busca de itens do tipo artigo."""
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
