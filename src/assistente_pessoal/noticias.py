"""Leitura de noticias de tecnologia via The News, RSS ou Atom."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from time import struct_time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import httpx


@dataclass(frozen=True)
class Noticia:
    """Item de noticia normalizado para exibicao e memoria."""

    titulo: str
    link: str
    fonte: str
    publicado: str
    resumo: str = ""
    publicado_em: datetime | None = None

    def to_dict(self) -> dict[str, str]:
        """Serializa noticia para API e GUI."""
        return {
            "titulo": self.titulo,
            "link": self.link,
            "fonte": self.fonte,
            "publicado": self.publicado,
            "resumo": self.resumo,
        }


class ClienteNoticias:
    """Agrega noticias do The News tecnologia e de feeds RSS/Atom tech."""

    def __init__(self, timeout: float = 15.0) -> None:
        """Define timeout para fontes HTTP diretas, como o portal The News."""
        self.timeout = timeout

    def listar(
        self,
        urls: list[str],
        limite: int = 8,
        offset: int = 0,
        incluir_the_news_tecnologia: bool = True,
        timezone_local: str = "America/Sao_Paulo",
        data_referencia: date | None = None,
        assuntos_interesse: list[str] | None = None,
    ) -> list[Noticia]:
        """Coleta apenas noticias publicadas no dia local de referencia."""
        data_alvo = data_referencia or datetime.now(ZoneInfo(timezone_local)).date()
        quantidade_alvo = limite + offset
        noticias: list[Noticia] = []
        if incluir_the_news_tecnologia:
            noticias.extend(
                self._listar_the_news_tecnologia(
                    limite=quantidade_alvo,
                    timezone_local=timezone_local,
                    data_referencia=data_alvo,
                )
            )
        for url in urls:
            feed = feedparser.parse(url)
            fonte = feed.feed.get("title", url)
            for item in feed.entries[: max(quantidade_alvo * 3, 20)]:
                publicado_em = extrair_data_rss(item)
                if not publicado_no_dia(publicado_em, data_alvo, timezone_local):
                    continue
                noticias.append(
                    Noticia(
                        titulo=item.get("title", "Sem titulo"),
                        link=item.get("link", ""),
                        fonte=fonte,
                        publicado=_publicado(item),
                        resumo=_resumo(item),
                        publicado_em=publicado_em,
                    )
                )
                if len(noticias) >= quantidade_alvo:
                    break
            if len(noticias) >= quantidade_alvo:
                break
        ordenadas = priorizar_por_assuntos(noticias, assuntos_interesse or [])
        return ordenadas[offset : offset + limite]

    def _listar_the_news_tecnologia(
        self,
        limite: int,
        timezone_local: str,
        data_referencia: date,
    ) -> list[Noticia]:
        """Busca noticias de tecnologia do The News publicadas no dia local."""
        url = "https://api.waffle.com.br/api/public/articles"
        limite_busca = max(limite * 3, 20)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resposta = client.get(
                    url,
                    params={
                        "limit": limite_busca,
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
        noticias = []
        for artigo in artigos:
            publicado_em = extrair_data_iso(artigo.get("publishedAt"))
            if not publicado_no_dia(publicado_em, data_referencia, timezone_local):
                continue
            noticias.append(normalizar_the_news_artigo(artigo, publicado_em=publicado_em))
            if len(noticias) >= limite:
                break
        return noticias


def normalizar_the_news_artigo(artigo: dict, publicado_em: datetime | None = None) -> Noticia:
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
        resumo=artigo.get("excerpt") or artigo.get("description") or artigo.get("subtitle") or "",
        publicado_em=publicado_em,
    )


def formatar_noticias(noticias: list[Noticia]) -> str:
    """Formata uma lista de noticias em texto legivel."""
    if not noticias:
        return (
            "Nenhuma noticia de tecnologia publicada hoje foi encontrada nas fontes configuradas."
        )
    linhas = ["Noticias encontradas:"]
    for indice, noticia in enumerate(noticias, start=1):
        titulo = texto_terminal_seguro(noticia.titulo)
        fonte = texto_terminal_seguro(noticia.fonte)
        link = texto_terminal_seguro(noticia.link)
        linhas.append(f"{indice}. {titulo} ({fonte}) - {link}")
    return "\n".join(linhas)


def priorizar_por_assuntos(noticias: list[Noticia], assuntos: list[str]) -> list[Noticia]:
    """Ordena noticias por aderencia aos assuntos configurados, preservando fallback."""
    termos = [assunto.strip().lower() for assunto in assuntos if assunto.strip()]
    if not termos:
        return noticias

    def pontuar(noticia: Noticia) -> int:
        texto = f"{noticia.titulo} {noticia.fonte} {noticia.link}".lower()
        return sum(1 for termo in termos if termo in texto)

    ordenadas = sorted(enumerate(noticias), key=lambda item: (-pontuar(item[1]), item[0]))
    return [noticia for _indice, noticia in ordenadas]


def texto_terminal_seguro(texto: str) -> str:
    """Remove caracteres que quebram consoles Windows antigos em CP1252."""
    return texto.encode("cp1252", errors="ignore").decode("cp1252")


def extrair_data_iso(valor: str | None) -> datetime | None:
    """Converte datas ISO da API do The News para ``datetime`` com timezone."""
    if not valor:
        return None
    try:
        normalizado = valor.replace("Z", "+00:00")
        data = datetime.fromisoformat(normalizado)
    except ValueError:
        return None
    if data.tzinfo is None:
        return data.replace(tzinfo=UTC)
    return data


def extrair_data_rss(item: dict) -> datetime | None:
    """Extrai a data de publicacao de um item RSS/Atom."""
    publicado_parseado = item.get("published_parsed") or item.get("updated_parsed")
    if isinstance(publicado_parseado, struct_time):
        return datetime.fromtimestamp(calendar.timegm(publicado_parseado), tz=UTC)
    valor = item.get("published") or item.get("updated")
    if not valor:
        return None
    try:
        data = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None
    if data.tzinfo is None:
        return data.replace(tzinfo=UTC)
    return data


def publicado_no_dia(
    publicado_em: datetime | None,
    data_referencia: date,
    timezone_local: str,
) -> bool:
    """Confere se a publicacao caiu no dia local configurado."""
    if publicado_em is None:
        return False
    return publicado_em.astimezone(ZoneInfo(timezone_local)).date() == data_referencia


def _publicado(item: dict) -> str:
    """Extrai a data publicada de um item RSS com fallback previsivel."""
    valor = item.get("published") or item.get("updated")
    return valor or datetime.now().isoformat(timespec="seconds")


def _resumo(item: dict) -> str:
    """Extrai um trecho curto de RSS/Atom sem depender de scraping."""
    valor = item.get("summary") or item.get("description") or ""
    return texto_terminal_seguro(str(valor)).strip()
