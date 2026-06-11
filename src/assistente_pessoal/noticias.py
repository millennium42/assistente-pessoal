"""Orquestracao de noticias priorizadas para CLI e GUI.

Realiza o controle das multiplas fontes, coleta, mesclagem e deduplicacao.
Ordena as noticias combinadas respeitando a cronologia de publicacao e
as prioridades tematicas configuradas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from assistente_pessoal.config import NoticiasConfig
from assistente_pessoal.core_datas import hoje_local, normalizar_texto_ascii
from assistente_pessoal.fontes_noticias import (
    HtmlJsonLdNewsSource,
    InterestNewsSource,
    ItemFonteNoticia,
    RssNewsSource,
    TheNewsSource,
)

LIMITE_PADRAO_NOTICIAS = 100
LIMITE_INTERESSES_NOTICIAS = 50


@dataclass(frozen=True)
class Noticia:
    """Item de noticia normalizado para exibicao e memoria.

    Attributes:
        titulo: O manchete legivel.
        link: A url do link original.
        fonte: A origem (site/portal).
        publicado: String bruta da data de publicacao original.
        publicado_em: Objeto datetime para referenciar nas logicas de tempo.
        grupo: Grupo configurado onde foi pego (ex: 'tech', 'economia_global').
        interesse: Caso a noticia tenha vindo por via de pesquisa de palavra-chave.
    """

    titulo: str
    link: str
    fonte: str
    publicado: str
    publicado_em: datetime | None = None
    grupo: str = ""
    interesse: str = ""


class ClienteNoticias:
    """Coordena a coleta por grupos e entrega noticias em ordem cronologica."""

    def __init__(
        self,
        the_news_source: TheNewsSource | None = None,
        rss_source: RssNewsSource | None = None,
        html_source: HtmlJsonLdNewsSource | None = None,
        interest_source: InterestNewsSource | None = None,
    ) -> None:
        """Permite injetar fontes fake nos testes sem acoplar a infra a CLI.

        Args:
            the_news_source: Fonte de consumo do thenews.com.br.
            rss_source: Fonte generica de consumo RSS.
            html_source: Fonte focada em extração via JSON-LD.
            interest_source: Fonte de pesquisa do Google News.
        """
        self.the_news_source = the_news_source or TheNewsSource()
        self.rss_source = rss_source or RssNewsSource()
        self.html_source = html_source or HtmlJsonLdNewsSource()
        self.interest_source = interest_source or InterestNewsSource()

    def listar(
        self,
        config: NoticiasConfig,
        limite: int = LIMITE_PADRAO_NOTICIAS,
        data_referencia: date | None = None,
    ) -> list[Noticia]:
        """Busca noticias por prioridade de fonte e devolve do mais novo ao mais antigo.

        Args:
            config: A secao de configuracao voltada a noticias.
            limite: Quantidade total desejada.
            data_referencia: Dia alvo, padrao 'hoje local'.

        Returns:
            Lista final contendo os itens consolidados e ja limpos de duplicacao.
        """
        data_alvo = data_referencia or hoje_local(config.timezone)
        noticias: list[Noticia] = []
        limite_normalizado = max(limite, 1)
        for grupo in config.prioridades:
            itens = self._listar_grupo(grupo, config, limite_normalizado, data_alvo)
            noticias.extend(itens)
        noticias.extend(self._listar_interesses(config, limite_normalizado, data_alvo))
        noticias = deduplicar_noticias(noticias)
        noticias_ordenadas = ordenar_noticias_por_data(noticias, config.timezone)
        noticias_priorizadas = priorizar_noticias_por_interesses(
            noticias_ordenadas,
            config.interesses_busca,
        )
        return selecionar_noticias(noticias_priorizadas, limite_normalizado, config.timezone)

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

    def _listar_interesses(
        self,
        config: NoticiasConfig,
        limite: int,
        data_referencia: date,
    ) -> list[Noticia]:
        """Busca noticias em portais indexados usando as tags de interesse."""
        limite_interesses = min(limite, LIMITE_INTERESSES_NOTICIAS)
        itens = self.interest_source.listar(
            interesses=config.interesses_busca,
            limite=limite_interesses,
            timezone=config.timezone,
            data_referencia=data_referencia,
            apenas_dia_atual=config.apenas_dia_atual,
        )
        return [normalizar_item(item) for item in itens[:limite_interesses]]


def normalizar_item(item: ItemFonteNoticia) -> Noticia:
    """Converte o item interno da fonte para o tipo publico da aplicacao.

    Args:
        item: O item proveniente da camada de fontes.

    Returns:
        A noticia encapsulada no modelo de domínio de alto nível.
    """
    return Noticia(
        titulo=item.titulo,
        link=item.link,
        fonte=item.fonte,
        publicado=item.publicado,
        publicado_em=item.publicado_em,
        grupo=item.grupo,
        interesse=item.interesse,
    )


def ordenar_noticias_por_data(noticias: list[Noticia], timezone: str) -> list[Noticia]:
    """Ordena noticias da publicacao mais recente para a mais antiga.

    Args:
        noticias: Lista de dados.
        timezone: O fuso horario atual para preencher os que vierem timezone naive.

    Returns:
        Uma lista copiada em ordem descendente.
    """
    return sorted(
        noticias,
        key=lambda noticia: _timestamp_publicacao(noticia.publicado_em, timezone),
        reverse=True,
    )


def deduplicar_noticias(noticias: list[Noticia]) -> list[Noticia]:
    """Remove manchetes repetidas entre RSS, HTML local e buscas por interesse.

    Args:
        noticias: Lista total com possiveis duplicatas.

    Returns:
        Lista com itens unicos verificando a heuristica de titulo/link.
    """
    deduplicadas: list[Noticia] = []
    vistos: set[str] = set()
    for noticia in noticias:
        chave = _chave_noticia(noticia)
        if chave in vistos:
            continue
        vistos.add(chave)
        deduplicadas.append(noticia)
    return deduplicadas


def selecionar_noticias(noticias: list[Noticia], limite: int, timezone: str) -> list[Noticia]:
    """Recorta o feed preservando fontes prioritarias quando elas existem.

    Args:
        noticias: Todas as noticias recuperadas.
        limite: O numero alvo desejado na saída.
        timezone: String indicando o fuso de comparacao.

    Returns:
        Noticias selecionadas até o limite, com as essenciais garantidas primeiro.
    """
    grupos_preservados = {"the_news", "santa_maria", "interesses"}
    selecionadas = noticias[:limite]
    prioritarias = [noticia for noticia in noticias if noticia.grupo in grupos_preservados]
    faltantes = [noticia for noticia in prioritarias if noticia not in selecionadas]
    if not faltantes:
        return ordenar_noticias_por_data(selecionadas, timezone)

    preservadas = [
        noticia for noticia in selecionadas if noticia.grupo in grupos_preservados
    ]
    prioritarias_final = preservadas + faltantes
    if len(prioritarias_final) >= limite:
        return ordenar_noticias_por_data(prioritarias_final[:limite], timezone)

    outras = [
        noticia for noticia in selecionadas if noticia.grupo not in grupos_preservados
    ]
    vagas_outras = limite - len(prioritarias_final)
    return ordenar_noticias_por_data(prioritarias_final + outras[:vagas_outras], timezone)


def priorizar_noticias_por_interesses(
    noticias: list[Noticia],
    interesses: list[str],
) -> list[Noticia]:
    """Coloca noticias relacionadas aos interesses antes, preservando a recencia.

    Args:
        noticias: Lista inicial cronologicamente sorteada.
        interesses: Lista de palavras-chave do usuario.

    Returns:
        Noticias reordenadas privilegiando os termos buscados.
    """
    termos = [
        normalizar_texto_ascii(interesse).lower().strip()
        for interesse in interesses
        if interesse.strip()
    ]
    if not termos:
        return noticias
    return sorted(
        noticias,
        key=lambda noticia: _pontuacao_interesse(noticia, termos),
        reverse=True,
    )


def rotulo_tempo_publicacao(
    noticia: Noticia,
    timezone: str = "America/Sao_Paulo",
    agora: datetime | None = None,
) -> str:
    """Mostra a idade da noticia sem expor a data bruta da fonte.

    Args:
        noticia: O objeto de noticia avaliado.
        timezone: O fuso para conversao (para calcular diferencas temporais reais).
        agora: Parametro util para facilitar mock e freeze the time.

    Returns:
        String naturalizada tipo 'ha 5 minutos' ou 'agora'.
    """
    publicado_em = _normalizar_data_publicacao(noticia.publicado_em, timezone)
    if publicado_em is None:
        return "tempo indisponivel"
    agora_local = _normalizar_agora(agora, timezone)
    diferenca = agora_local - publicado_em
    segundos = max(int(diferenca.total_seconds()), 0)
    if segundos < 60:
        return "agora"
    minutos = segundos // 60
    if minutos < 60:
        return _rotulo_quantidade(minutos, "minuto", "minutos")
    horas = minutos // 60
    if horas < 24:
        return _rotulo_quantidade(horas, "hora", "horas")
    dias = horas // 24
    if dias < 7:
        return _rotulo_quantidade(dias, "dia", "dias")
    semanas = dias // 7
    if semanas < 5:
        return _rotulo_quantidade(semanas, "semana", "semanas")
    meses = dias // 30
    if meses < 12:
        return _rotulo_quantidade(max(meses, 1), "mes", "meses")
    anos = dias // 365
    return _rotulo_quantidade(max(anos, 1), "ano", "anos")


def formatar_noticias(
    noticias: list[Noticia],
    timezone: str = "America/Sao_Paulo",
    agora: datetime | None = None,
) -> str:
    """Formata uma lista de noticias em texto legivel.

    Args:
        noticias: A lista coletada.
        timezone: O fuso horario atual.
        agora: Instante artificial, util pra testar a variacao do tempo exibido.

    Returns:
        Texto amigavel de exibicao pronto pro stdout.
    """
    if not noticias:
        return "Nenhuma noticia publicada no dia atual foi encontrada nas fontes configuradas."
    linhas = ["Noticias encontradas:"]
    for indice, noticia in enumerate(ordenar_noticias_por_data(noticias, timezone), start=1):
        titulo = texto_terminal_seguro(noticia.titulo)
        fonte = texto_terminal_seguro(noticia.fonte)
        link = texto_terminal_seguro(noticia.link)
        grupo = texto_terminal_seguro(noticia.grupo.replace("_", " "))
        publicado = texto_terminal_seguro(
            rotulo_tempo_publicacao(noticia, timezone=timezone, agora=agora)
        )
        extras = [fonte, grupo, publicado]
        if noticia.interesse:
            interesse = texto_terminal_seguro(f"interesse: {noticia.interesse}")
            extras.insert(2, interesse)
        linhas.append(f"{indice}. {titulo} ({' | '.join(extras)}) - {link}")
    return "\n".join(linhas)


def texto_terminal_seguro(texto: str) -> str:
    """Remove caracteres que quebram consoles Windows antigos em CP1252.

    Args:
        texto: Texto que deve ser limpo de caracteres unicode complexos.

    Returns:
        Texto com codificacao reduzida onde o nao-suportado e dropado.
    """
    return texto.encode("cp1252", errors="ignore").decode("cp1252")


def _timestamp_publicacao(publicado_em: datetime | None, timezone: str) -> float:
    data = _normalizar_data_publicacao(publicado_em, timezone)
    if data is None:
        return float("-inf")
    return data.timestamp()


def _pontuacao_interesse(noticia: Noticia, termos: list[str]) -> int:
    universo = normalizar_texto_ascii(
        f"{noticia.titulo} {noticia.fonte} {noticia.grupo} {noticia.link}"
    ).lower()
    tokens_universo = set(re.findall(r"[a-z0-9]+", universo))
    pontuacao = 2 if noticia.grupo == "interesses" else 0
    for termo in termos:
        tokens_termo = re.findall(r"[a-z0-9]+", termo)
        if not tokens_termo:
            continue
        if len(tokens_termo) == 1:
            pontuacao += int(tokens_termo[0] in tokens_universo)
            continue
        if termo in universo:
            pontuacao += 4
            continue
        combina_termo = termo in universo or all(
            token in tokens_universo for token in tokens_termo
        )
        pontuacao += int(combina_termo)
    return pontuacao


def _chave_noticia(noticia: Noticia) -> str:
    titulo = normalizar_texto_ascii(noticia.titulo).lower().strip()
    titulo = re.sub(r"\s+", " ", titulo)
    if titulo:
        return titulo
    return noticia.link.strip().lower()


def _normalizar_data_publicacao(publicado_em: datetime | None, timezone: str) -> datetime | None:
    if publicado_em is None:
        return None
    fuso = ZoneInfo(timezone)
    if publicado_em.tzinfo is None:
        return publicado_em.replace(tzinfo=fuso)
    return publicado_em.astimezone(fuso)


def _normalizar_agora(agora: datetime | None, timezone: str) -> datetime:
    fuso = ZoneInfo(timezone)
    if agora is None:
        return datetime.now(fuso)
    if agora.tzinfo is None:
        return agora.replace(tzinfo=fuso)
    return agora.astimezone(fuso)


def _rotulo_quantidade(valor: int, singular: str, plural: str) -> str:
    unidade = singular if valor == 1 else plural
    return f"ha {valor} {unidade}"
