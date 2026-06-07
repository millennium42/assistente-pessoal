"""Leitura de noticias por RSS ou Atom."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import feedparser


@dataclass(frozen=True)
class Noticia:
    """Item de noticia normalizado para exibicao e memoria."""

    titulo: str
    link: str
    fonte: str
    publicado: str


class ClienteNoticias:
    """Agrega noticias de feeds RSS/Atom configurados pelo usuario."""

    def listar(self, urls: list[str], limite: int = 8) -> list[Noticia]:
        """Coleta itens dos feeds informados e limita a quantidade final."""
        noticias: list[Noticia] = []
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


def formatar_noticias(noticias: list[Noticia]) -> str:
    """Formata uma lista de noticias em texto legivel."""
    if not noticias:
        return "Nenhuma noticia encontrada nas fontes configuradas."
    linhas = ["Noticias encontradas:"]
    for indice, noticia in enumerate(noticias, start=1):
        linhas.append(f"{indice}. {noticia.titulo} ({noticia.fonte}) - {noticia.link}")
    return "\n".join(linhas)


def _publicado(item: dict) -> str:
    """Extrai a data publicada de um item RSS com fallback previsivel."""
    valor = item.get("published") or item.get("updated")
    return valor or datetime.now().isoformat(timespec="seconds")
