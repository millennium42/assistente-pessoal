"""Casos de uso compartilhados por CLI, API e desktop."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from assistente_pessoal.adapters.google_calendar import GoogleCalendarAdapter
from assistente_pessoal.application.privacy import (
    data_map,
    export_privacy_bundle,
    purge_generated_data,
    safe_config,
)
from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import AppConfig
from assistente_pessoal.estudos import criar_nota_estudo
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.musica import ClienteMusica, formatar_lancamentos
from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias


@dataclass
class AssistenteService:
    """Orquestra capacidades do assistente sem depender de UI especifica."""

    config: AppConfig

    @cached_property
    def memoria(self) -> MemoriaObsidian:
        """Cria o adaptador de memoria uma vez por instancia de servico."""
        return MemoriaObsidian(self.config.vault_path, self.config.localizacao.timezone)

    @cached_property
    def calendar(self) -> GoogleCalendarAdapter:
        """Cria o adaptador de Google Agenda uma vez por instancia de servico."""
        return GoogleCalendarAdapter()

    def health(self) -> dict[str, str | bool]:
        """Retorna status operacional minimo sem expor dados sensiveis."""
        return {
            "status": "ok",
            "version": "0.2.0",
            "vault_configurado": bool(self.config.vault_path),
            "llm_configurado": self.config.llm.habilitado(),
        }

    def dashboard(self) -> dict:
        """Monta um painel inicial local-first sem chamar APIs externas automaticamente."""
        recentes = self.memoria.listar_notas(limite=5)
        calendar = self.calendar.status()
        return {
            "health": self.health(),
            "localizacao": {
                "cidade": self.config.localizacao.cidade,
                "timezone": self.config.localizacao.timezone,
            },
            "memorias_recentes": [item.to_dict() for item in recentes],
            "google_calendar": calendar,
            "cards": {
                "clima_atual": {
                    "enabled": True,
                    "requires_user_action": True,
                },
                "clima_futuro": {
                    "enabled": True,
                    "requires_user_action": True,
                    "source": "weather.futuro",
                },
                "noticias": {
                    "enabled": True,
                    "requires_user_action": True,
                },
                "musica": {
                    "enabled": True,
                    "requires_user_action": True,
                },
                "memoria": {
                    "enabled": True,
                    "recent_items": len(recentes),
                },
                "estudo": {
                    "enabled": True,
                    "requires_user_action": True,
                },
                "chat": {
                    "enabled": True,
                    "requires_opt_in_for_external_llm": True,
                },
                "google_calendar": {
                    "enabled": True,
                    "configured": calendar["configured"],
                    "connected": calendar["connected"],
                },
                "privacidade": {
                    "enabled": True,
                    "local_first": True,
                },
            },
            "privacidade": {
                "modo": "local-first",
                "envio_llm_exige_opt_in": True,
            },
        }

    def listar_memorias(self, limite: int = 20) -> list[dict[str, str]]:
        """Lista memorias recentes do vault."""
        return [item.to_dict() for item in self.memoria.listar_notas(limite=limite)]

    def salvar_memoria(self, titulo: str, conteudo: str, tags: list[str] | None = None) -> dict:
        """Salva memoria local em Markdown."""
        caminho = self.memoria.salvar_nota(titulo, conteudo, tags=tags)
        return {"titulo": titulo, "caminho": str(caminho)}

    def apagar_memoria(self, caminho: Path) -> dict[str, str | bool]:
        """Apaga uma nota dentro do vault e reconstrui o indice."""
        apagado = self.memoria.apagar_nota(caminho)
        return {"apagado": apagado, "caminho": str(caminho)}

    def clima(self) -> dict[str, str | list[dict[str, str]]]:
        """Consulta clima por acao explicita do usuario."""
        previsao = ClienteClima().obter_previsao(self.config.localizacao)
        return {
            "texto": formatar_previsao(previsao),
            "cidade": previsao.cidade,
            "futuro": [item.to_dict() for item in previsao.proximos_dias[1:]],
        }

    def noticias(self, limite: int = 8, offset: int = 0) -> dict:
        """Consulta noticias por acao explicita do usuario."""
        itens = ClienteNoticias().listar(
            self.config.fontes.rss,
            limite=limite,
            offset=offset,
            incluir_the_news_tecnologia=self.config.fontes.incluir_the_news_tecnologia,
            timezone_local=self.config.localizacao.timezone,
            assuntos_interesse=self.config.fontes.assuntos_interesse,
        )
        return {
            "texto": formatar_noticias(itens),
            "quantidade": str(len(itens)),
            "itens": [item.to_dict() for item in itens],
            "offset": offset,
            "assuntos_interesse": self.config.fontes.assuntos_interesse,
        }

    def registrar_interesse_noticia(
        self,
        titulo: str,
        link: str,
        fonte: str = "",
        resumo: str = "",
        publicado: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, str]:
        """Salva noticia clicada no Obsidian para monitorar interesses locais."""
        classificacao = _classificar_noticia(
            titulo=titulo,
            link=link,
            fonte=fonte,
            resumo=resumo,
            assuntos=self.config.fontes.assuntos_interesse,
            extras=tags or [],
        )
        relacionadas = _noticias_relacionadas(
            pasta=self.config.vault_path / "40_noticias",
            titulo=titulo,
            link=link,
            tags=classificacao.tags,
        )
        conteudo = _conteudo_noticia_obsidian(
            fonte=fonte,
            link=link,
            resumo=resumo,
            publicado=publicado,
            categoria=classificacao.categoria,
            assuntos=classificacao.assuntos,
            relacionadas=relacionadas,
        )
        caminho = self.memoria.salvar_nota(
            titulo=titulo,
            conteudo=conteudo,
            pasta="40_noticias",
            tags=classificacao.tags,
        )
        return {"titulo": titulo, "caminho": str(caminho)}

    def musica(self, dias: int = 45) -> dict[str, str]:
        """Consulta lancamentos musicais configurados."""
        cliente = ClienteMusica(self.config.fontes.musicbrainz_user_agent)
        lancamentos = cliente.listar_lancamentos(self.config.fontes.artistas, dias=dias)
        return {"texto": formatar_lancamentos(lancamentos), "quantidade": str(len(lancamentos))}

    def criar_estudo(self, tema: str, conteudo: str, perguntas: int = 5) -> dict[str, str]:
        """Cria nota de estudo sem enviar dados para LLM externo por padrao."""
        llm = ClienteLLM(self.config.llm)
        caminho = criar_nota_estudo(self.memoria, tema, conteudo, llm, perguntas)
        return {"caminho": str(caminho), "tema": tema}

    def chat(self, mensagem: str, permitir_llm_externo: bool = False) -> dict[str, str | bool]:
        """Responde chat e exige opt-in antes de chamar provedor externo."""
        memoria = self.memoria
        contexto = "\n".join(
            f"{item.titulo}: {item.trecho}" for item in memoria.buscar(mensagem, limite=3)
        )
        llm = ClienteLLM(self.config.llm)
        if llm.disponivel() and not permitir_llm_externo:
            return {
                "texto": (
                    "LLM externo configurado, mas o envio esta bloqueado por privacidade. "
                    "Confirme o opt-in para enviar mensagem e contexto local ao provedor."
                ),
                "llm_usado": False,
                "opt_in_necessario": True,
            }
        resposta = llm.gerar(mensagem, contexto=contexto) if permitir_llm_externo else None
        if resposta:
            return {"texto": resposta.texto, "llm_usado": True, "modelo": resposta.modelo}
        return {"texto": resposta_fallback(), "llm_usado": False}

    def config_segura(self) -> dict:
        """Retorna configuracao redigida."""
        return safe_config(self.config)

    def mapa_de_dados(self) -> list[dict[str, str]]:
        """Retorna inventario LGPD."""
        return data_map()

    def exportar_privacidade(self, destino: Path) -> dict[str, str]:
        """Exporta dados locais portaveis."""
        arquivo = export_privacy_bundle(self.config, destino)
        return {"arquivo": str(arquivo)}

    def limpar_dados_gerados(self) -> dict[str, list[str]]:
        """Remove caches e indices gerados sem apagar notas Markdown."""
        return purge_generated_data(self.config)

    def calendar_status(self) -> dict:
        """Retorna status seguro do Google Agenda."""
        return self.calendar.status()

    def calendar_auth_url(self) -> str:
        """Gera URL OAuth para iniciar autenticacao do Google Agenda."""
        return self.calendar.authorization_url()

    def complete_calendar_auth(self, code: str) -> None:
        """Completa autenticacao OAuth local do Google Agenda."""
        self.calendar.complete_authorization(code)

    def calendar_events(self, limite: int = 5) -> list[dict[str, str]]:
        """Lista proximos eventos do Google Agenda conectado."""
        return [item.to_dict() for item in self.calendar.upcoming_events(limite=limite)]

    def criar_evento_agenda(
        self,
        titulo: str,
        inicio: str,
        fim: str | None = None,
        descricao: str = "",
    ) -> dict[str, str]:
        """Cria evento no Google Agenda usando a API oficial."""
        evento = self.calendar.create_event(
            titulo=titulo,
            inicio=inicio,
            fim=fim,
            descricao=descricao,
            timezone=self.config.localizacao.timezone,
        )
        return evento.to_dict()


@dataclass(frozen=True)
class NewsClassification:
    """Classificacao local de noticia clicada."""

    categoria: str
    assuntos: list[str]
    tags: list[str]


def _classificar_noticia(
    titulo: str,
    link: str,
    fonte: str,
    resumo: str,
    assuntos: list[str],
    extras: list[str],
) -> NewsClassification:
    """Classifica noticia por categoria e assuntos configurados."""
    texto = f"{titulo} {link} {fonte} {resumo}".lower()
    assuntos_encontrados = [assunto for assunto in assuntos if assunto.lower() in texto]
    categoria = _categoria_noticia(fonte, link, assuntos_encontrados)
    tags = ["noticia", "interesse-monitorado", f"categoria-{categoria}", *extras]
    tags.extend(assuntos_encontrados)
    return NewsClassification(
        categoria=categoria,
        assuntos=assuntos_encontrados,
        tags=sorted({_tag_obsidian(tag) for tag in tags if tag.strip()}),
    )


def _categoria_noticia(fonte: str, link: str, assuntos: list[str]) -> str:
    """Escolhe uma categoria estavel para organizar noticias salvas."""
    texto = f"{fonte} {link}".lower()
    if "tecnologia" in texto or "tech" in texto:
        return "tecnologia"
    if assuntos:
        return _tag_obsidian(assuntos[0])
    return "geral"


def _conteudo_noticia_obsidian(
    fonte: str,
    link: str,
    resumo: str,
    publicado: str,
    categoria: str,
    assuntos: list[str],
    relacionadas: list[str],
) -> str:
    """Monta corpo da nota salva no Obsidian para uma noticia clicada."""
    assuntos_texto = ", ".join(assuntos) if assuntos else "sem assunto configurado detectado"
    relacionadas_texto = "\n".join(f"- {item}" for item in relacionadas) or "- Nenhuma ainda."
    trecho = resumo.strip() or "Sem trecho disponivel pela fonte. O titulo e o link foram salvos."
    return f"""Fonte: {fonte or "desconhecida"}
Link: {link or "sem link"}
Publicado: {publicado or "sem data"}
Categoria: {categoria}
Assuntos: {assuntos_texto}

## Trecho copiado

{trecho}

## Materias relacionadas

{relacionadas_texto}

## Sinal local

Noticia clicada ou salva no dashboard. Use esta nota para observar interesses recorrentes
sem rastreamento externo.
"""


def _noticias_relacionadas(pasta: Path, titulo: str, link: str, tags: list[str]) -> list[str]:
    """Encontra noticias ja salvas com termos ou tags em comum."""
    if not pasta.exists():
        return []
    termos = set(_termos_relevantes(f"{titulo} {link} {' '.join(tags)}"))
    relacionadas: list[tuple[int, str]] = []
    for caminho in sorted(pasta.glob("*.md")):
        texto = caminho.read_text(encoding="utf-8")
        if link and link in texto:
            continue
        score = len(termos.intersection(_termos_relevantes(texto)))
        if score <= 0:
            continue
        titulo_existente = _titulo_markdown(texto) or caminho.stem
        relacionadas.append((score, f"[[{caminho.stem}|{titulo_existente}]]"))
    relacionadas.sort(key=lambda item: item[0], reverse=True)
    return [link_obsidian for _score, link_obsidian in relacionadas[:5]]


def _termos_relevantes(texto: str) -> list[str]:
    """Extrai termos simples para relacionar materias sem modelo externo."""
    ignorar = {
        "para",
        "com",
        "sem",
        "uma",
        "por",
        "que",
        "das",
        "dos",
        "noticia",
        "interesse",
        "monitorado",
    }
    termos = re.findall(r"[a-zA-Z0-9À-ÿ]{4,}", texto.lower())
    return [termo for termo in termos if termo not in ignorar]


def _titulo_markdown(texto: str) -> str:
    """Extrai o primeiro H1 de uma nota Markdown."""
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip()
    return ""


def _tag_obsidian(valor: str) -> str:
    """Normaliza tag para front matter do Obsidian."""
    return valor.strip().lower().replace(" ", "-")
