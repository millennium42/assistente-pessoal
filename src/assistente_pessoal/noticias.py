"""Orquestracao de noticias priorizadas para CLI, voz e GUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from assistente_pessoal.config import NoticiasConfig
from assistente_pessoal.core_datas import hoje_local
from assistente_pessoal.fontes_noticias import (
    HtmlJsonLdNewsSource,
    ItemFonteNoticia,
    RssNewsSource,
    TheNewsSource,
)


@dataclass(frozen=True)
class Noticia:
    """Item de noticia normalizado para exibicao e memoria."""

    titulo: str
    link: str
    fonte: str
    publicado: str
    publicado_em: datetime | None = None
    grupo: str = ""


class ClienteNoticias:
    """Coordena a coleta de noticias por grupos de prioridade configurados."""

    def __init__(
        self,
        the_news_source: TheNewsSource | None = None,
        rss_source: RssNewsSource | None = None,
        html_source: HtmlJsonLdNewsSource | None = None,
    ) -> None:
        """Permite injetar fontes fake nos testes sem acoplar a infra a CLI."""
        self.the_news_source = the_news_source or TheNewsSource()
        self.rss_source = rss_source or RssNewsSource()
        self.html_source = html_source or HtmlJsonLdNewsSource()

    def listar(
        self,
        config: NoticiasConfig,
        limite: int = 8,
        data_referencia: date | None = None,
    ) -> list[Noticia]:
        """Busca noticias respeitando a ordem de prioridade definida no config."""
        data_alvo = data_referencia or hoje_local(config.timezone)
        noticias: list[Noticia] = []
        restantes = max(limite, 1)
        for grupo in config.prioridades:
            if restantes <= 0:
                break
            itens = self._listar_grupo(grupo, config, restantes, data_alvo)
            noticias.extend(itens)
            restantes = limite - len(noticias)
        return noticias[:limite]

    def _listar_grupo(
        self,
        grupo: str,
        config: NoticiasConfig,
        limite: int,
        data_referencia: date,
    ) -> list[Noticia]:
        """Despacha cada grupo para o adaptador apropriado mantendo a camada publica enxuta."""
        itens: list[ItemFonteNoticia]
        if grupo == "the_news":
            itens = self.the_news_source.listar(
                config.the_news,
                limite=limite,
                timezone=config.timezone,
                data_referencia=data_referencia,
            )
        elif grupo == "santa_maria":
            itens = []
            itens.extend(
                self.html_source.listar(
                    grupo=grupo,
                    config=config.santa_maria,
                    limite=limite,
                    timezone=config.timezone,
                    data_referencia=data_referencia,
                    apenas_dia_atual=config.apenas_dia_atual,
                )
            )
            if len(itens) < limite and config.santa_maria.rss:
                itens.extend(
                    self.rss_source.listar(
                        grupo=grupo,
                        config=config.santa_maria,
                        limite=limite - len(itens),
                        timezone=config.timezone,
                        data_referencia=data_referencia,
                        apenas_dia_atual=config.apenas_dia_atual,
                    )
                )
        elif grupo == "tech":
            itens = self.rss_source.listar(
                grupo=grupo,
                config=config.tech,
                limite=limite,
                timezone=config.timezone,
                data_referencia=data_referencia,
                apenas_dia_atual=config.apenas_dia_atual,
            )
        elif grupo == "economia_global":
            itens = self.rss_source.listar(
                grupo=grupo,
                config=config.economia_global,
                limite=limite,
                timezone=config.timezone,
                data_referencia=data_referencia,
                apenas_dia_atual=config.apenas_dia_atual,
            )
            if len(itens) < limite and config.economia_global.urls:
                itens.extend(
                    self.html_source.listar(
                        grupo=grupo,
                        config=config.economia_global,
                        limite=limite - len(itens),
                        timezone=config.timezone,
                        data_referencia=data_referencia,
                        apenas_dia_atual=config.apenas_dia_atual,
                    )
                )
        else:
            itens = []
        return [normalizar_item(item) for item in itens[:limite]]


def normalizar_item(item: ItemFonteNoticia) -> Noticia:
    """Converte o item interno da fonte para o tipo publico da aplicacao."""
    return Noticia(
        titulo=item.titulo,
        link=item.link,
        fonte=item.fonte,
        publicado=item.publicado,
        publicado_em=item.publicado_em,
        grupo=item.grupo,
    )


def formatar_noticias(noticias: list[Noticia]) -> str:
    """Formata uma lista de noticias em texto legivel."""
    if not noticias:
        return "Nenhuma noticia publicada no dia atual foi encontrada nas fontes configuradas."
    linhas = ["Noticias encontradas:"]
    for indice, noticia in enumerate(noticias, start=1):
        titulo = texto_terminal_seguro(noticia.titulo)
        fonte = texto_terminal_seguro(noticia.fonte)
        link = texto_terminal_seguro(noticia.link)
        grupo = texto_terminal_seguro(noticia.grupo.replace("_", " "))
        linhas.append(f"{indice}. {titulo} ({fonte} | {grupo}) - {link}")
    return "\n".join(linhas)


def texto_terminal_seguro(texto: str) -> str:
    """Remove caracteres que quebram consoles Windows antigos em CP1252."""
    return texto.encode("cp1252", errors="ignore").decode("cp1252")
