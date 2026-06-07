"""Consulta de lancamentos musicais usando MusicBrainz."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta

import httpx


@dataclass(frozen=True)
class LancamentoMusical:
    """Lancamento musical normalizado a partir do MusicBrainz."""

    artista: str
    titulo: str
    data: str
    tipo: str
    link: str


class ClienteMusica:
    """Cliente para buscar release-groups recentes no MusicBrainz."""

    def __init__(self, user_agent: str, timeout: float = 20.0, intervalo: float = 1.0) -> None:
        """Configura identificacao e intervalo para respeitar a API publica."""
        self.user_agent = user_agent
        self.timeout = timeout
        self.intervalo = intervalo

    def listar_lancamentos(
        self,
        artistas: list[str],
        dias: int = 45,
        limite_por_artista: int = 5,
    ) -> list[LancamentoMusical]:
        """Busca lancamentos recentes para os artistas configurados."""
        if not artistas:
            return []
        resultados: list[LancamentoMusical] = []
        inicio = date.today() - timedelta(days=dias)
        fim = date.today() + timedelta(days=14)
        with httpx.Client(timeout=self.timeout, headers={"User-Agent": self.user_agent}) as client:
            for posicao, artista in enumerate(artistas):
                resultados.extend(
                    self._buscar_artista(client, artista, inicio, fim, limite_por_artista)
                )
                if posicao < len(artistas) - 1 and self.intervalo > 0:
                    time.sleep(self.intervalo)
        return resultados

    def _buscar_artista(
        self,
        client: httpx.Client,
        artista: str,
        inicio: date,
        fim: date,
        limite: int,
    ) -> list[LancamentoMusical]:
        """Executa a busca de release-groups de um unico artista."""
        consulta = f'artist:"{artista}" AND firstreleasedate:[{inicio} TO {fim}]'
        resposta = client.get(
            "https://musicbrainz.org/ws/2/release-group/",
            params={"query": consulta, "fmt": "json", "limit": limite},
        )
        resposta.raise_for_status()
        dados = resposta.json()
        return [normalizar_lancamento(artista, item) for item in dados.get("release-groups", [])]


def normalizar_lancamento(artista: str, item: dict) -> LancamentoMusical:
    """Converte um release-group do MusicBrainz para o formato da aplicacao."""
    identificador = item.get("id", "")
    return LancamentoMusical(
        artista=artista,
        titulo=item.get("title", "Sem titulo"),
        data=item.get("first-release-date", "data desconhecida"),
        tipo=item.get("primary-type", "tipo desconhecido"),
        link=f"https://musicbrainz.org/release-group/{identificador}" if identificador else "",
    )


def formatar_lancamentos(lancamentos: list[LancamentoMusical]) -> str:
    """Formata lancamentos musicais para CLI."""
    if not lancamentos:
        return "Nenhum lancamento recente encontrado para os artistas configurados."
    linhas = ["Lancamentos musicais encontrados:"]
    for indice, item in enumerate(lancamentos, start=1):
        linhas.append(
            f"{indice}. {item.artista} - {item.titulo} ({item.tipo}, {item.data}) {item.link}"
        )
    return "\n".join(linhas)
