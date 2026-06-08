"""Leitura de noticias de tecnologia via The News, RSS ou Atom."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import feedparser
import httpx


@dataclass(frozen=True)
class Noticia:
    """Item de noticia normalizado para exibicao e memoria."""

    titulo: str
    link: str
    fonte: str
    publicado: str


class ClienteNoticias:
    """Agrega noticias do The News tecnologia e de feeds RSS/Atom tech."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout para fontes HTTP diretas, como o portal The News."""
        self.timeout = timeout

    def listar(
        self,
        urls: list[str],
        limite: int = 8,
        incluir_the_news_tecnologia: bool = True,
    ) -> list[Noticia]:
        """Coleta noticias priorizando The News tecnologia e feeds RSS tech."""
        noticias: list[Noticia] = []
        if incluir_the_news_tecnologia:
            noticias.extend(self._listar_the_news_tecnologia(limite=limite))
        for url in urls:
            feed = feedparser.parse(url)
            fonte = feed.feed.get("title", url)
            for item in feed.entries[:limite]:
                noticias.append(
                    Noticia(
                        titulo=item.get("title", "Sem titulo"),
                        link=item.get("link", ""),
                        fonte=fonte,
                        publicado=_publicado(item),
                    )
                )
        return noticias[:limite]

    def _listar_the_news_tecnologia(self, limite: int) -> list[Noticia]:
        """Busca a categoria tecnologia do The News via API publica usada pelo portal."""
        url = "https://api.waffle.com.br/api/public/articles"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resposta = client.get(
                    url,
                    params={
                        "limit": limite,
                        "category": "tecnologia",
                        "page": 1,
                        "isAds": "false",
                    },
                    headers={"User-Agent": "assistente-pessoal/0.1.0"},
                )
                resposta.raise_for_status()
                dados = resposta.json()
        except (httpx.HTTPError, ValueError):
            # The News nao oferece RSS publico; se a API mudar, os RSS tech continuam funcionando.
            return []
        artigos = dados.get("data", {}).get("articles", [])
        return [normalizar_the_news_artigo(artigo) for artigo in artigos[:limite]]


def normalizar_the_news_artigo(artigo: dict) -> Noticia:
    """Converte um artigo do The News para o formato comum de noticia."""
    slug = artigo.get("slug", "")
    link = artigo.get("url") or artigo.get("canonicalUrl")
    if not link and slug:
        link = f"https://www.thenews.com.br/pt-BR/portal/news/{slug}"
    if link:
        link = urljoin("https://www.thenews.com.br", link)
    return Noticia(
        titulo=artigo.get("title", "Sem titulo"),
        link=link or "https://www.thenews.com.br/pt-BR/portal/categories/tecnologia",
        fonte="the news - tecnologia",
        publicado=artigo.get("publishedTimeAgo") or artigo.get("publishedAt") or _publicado({}),
    )


def formatar_noticias(noticias: list[Noticia]) -> str:
    """Formata uma lista de noticias em texto legivel."""
    if not noticias:
        return "Nenhuma noticia encontrada nas fontes configuradas."
    linhas = ["Noticias encontradas:"]
    for indice, noticia in enumerate(noticias, start=1):
        titulo = texto_terminal_seguro(noticia.titulo)
        fonte = texto_terminal_seguro(noticia.fonte)
        link = texto_terminal_seguro(noticia.link)
        linhas.append(f"{indice}. {titulo} ({fonte}) - {link}")
    return "\n".join(linhas)


def texto_terminal_seguro(texto: str) -> str:
    """Remove caracteres que quebram consoles Windows antigos em CP1252."""
    return texto.encode("cp1252", errors="ignore").decode("cp1252")


def _publicado(item: dict) -> str:
    """Extrai a data publicada de um item RSS com fallback previsivel."""
    valor = item.get("published") or item.get("updated")
    return valor or datetime.now().isoformat(timespec="seconds")
