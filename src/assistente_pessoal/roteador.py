"""Roteador simples de intencoes em texto livre para o assistente atual."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from assistente_pessoal.agenda_chat import AssistenteAgendaChat
from assistente_pessoal.agenda_google import ClienteGoogleAgenda
from assistente_pessoal.config import AppConfig, renderizar_toml
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.memoria import Memoria

PREFIXOS_MEMORIA = ("memorizar ", "anotar ", "lembrar ", "salvar ")
PREFIXOS_BUSCA = ("buscar ", "procurar ", "pesquisar ", "encontrar ")


@dataclass(frozen=True)
class RespostaRoteador:
    """Resposta do roteador com metadados para a interface atualizar blocos afetados."""

    texto: str
    agenda_alterada: bool = False
    agenda_referencia: date | None = None
    anotacoes_alteradas: bool = False


class RoteadorComandos:
    """Converte frases curtas em chamadas aos modulos do assistente."""

    def __init__(
        self,
        config: AppConfig,
        memoria: Memoria | None = None,
        llm: ClienteLLM | None = None,
        google_agenda: ClienteGoogleAgenda | None = None,
        agenda_chat: AssistenteAgendaChat | None = None,
    ) -> None:
        """Cria clientes sob demanda a partir da configuracao da aplicacao."""
        self.config = config
        self.memoria = memoria or Memoria(config.db_path, config.localizacao.timezone)
        self.llm = llm or ClienteLLM(config.llm)
        self.google_agenda = google_agenda or ClienteGoogleAgenda(config.google_agenda)
        self.agenda_chat = agenda_chat or AssistenteAgendaChat(
            self.google_agenda,
            self.config.localizacao.timezone,
        )

    def executar(self, texto: str) -> str:
        """Executa a melhor acao conhecida para um texto livre."""
        return self.executar_interacao(texto).texto

    def executar_interacao(self, texto: str) -> RespostaRoteador:
        """Processa a intencao com retorno estruturado do Gemini e aplica as acoes na memoria."""
        comando = texto.strip()
        if not comando:
            return RespostaRoteador("Nao ouvi nenhum comando.")

        gemini_cli = getattr(self.llm, "gemini", self.llm)
        if not hasattr(gemini_cli, "disponivel") or not gemini_cli.disponivel():
            return RespostaRoteador(resposta_fallback())

        contexto = _contexto_memoria(self.memoria, comando)
        contexto_agenda = self.agenda_chat.contexto_para_llm()
        schema = json.dumps(
            {
                "acao": "criar|atualizar|reforcar|ignorar|responder",
                "destino": (
                    "perfil_pessoal|anotacoes|noticias_relevantes|agenda_google|"
                    "memoria_comportamental|conversa"
                ),
                "conteudo": "texto extraido ou inferido",
                "campos_estruturados": {
                    "tipo_comportamento": "habito|preferencia|interesse",
                    "interesses": ["texto"],
                    "fonte_noticia": "texto opcional",
                    "link_noticia": "url opcional",
                    "agenda": {
                        "acao": (
                            "criar|atualizar_ultimo|atualizar_existente|"
                            "cancelar|perguntar|ignorar"
                        ),
                        "alvo": "titulo ou descricao curta do evento alvo",
                        "alvo_data": "YYYY-MM-DD opcional para identificar o evento atual",
                        "titulo": "texto opcional",
                        "data": "YYYY-MM-DD opcional",
                        "horario": "HH:MM opcional",
                        "local": "texto opcional",
                        "duracao_minutos": 60,
                    },
                },
                "nivel_confianca": "alto|medio|baixo",
                "precisa_confirmacao": False,
                "mensagem_ao_usuario": "resposta amigavel ao usuario",
            }
        )

        prompt = (
            "Aja como a APPA, assistente virtual. "
            "Responda em pt-BR com tom natural, humano, breve e prestativo. "
            "Evite soar mecanico, robótico ou excessivamente formal. "
            "Classifique o pedido ou insight e retorne JSON estrito. "
            "Quando o destino for agenda_google, use o contexto da agenda para decidir "
            "se deve criar, atualizar o ultimo evento, atualizar um evento ja existente, "
            "cancelar ou pedir dado faltante. "
            "Quando quiser editar um evento que ja existe na agenda e nao seja apenas o ultimo "
            "em andamento, use acao=atualizar_existente com alvo e, se ajudar, alvo_data.\n\n"
            f"Contexto e memorias:\n{contexto}\n\n"
            f"Contexto atual da agenda:\n{contexto_agenda}\n\n"
            f"Mensagem do usuario: {comando}"
        )

        try:
            dados = gemini_cli.gerar_json(prompt, schema_hint=schema)
        except Exception:
            return RespostaRoteador(resposta_fallback())

        mensagem_retorno = dados.get("mensagem_ao_usuario", "Processado.")
        if dados.get("precisa_confirmacao"):
            return RespostaRoteador(mensagem_retorno)

        acao = dados.get("acao", "responder")
        destino = dados.get("destino", "conversa")
        conteudo = dados.get("conteudo", "")

        agenda_alterada = False
        anotacoes_alteradas = False

        if destino == "agenda_google" or "agenda" in comando.lower():
            plano_agenda = dados.get("campos_estruturados", {}).get("agenda", {})
            acao_agenda = self.agenda_chat.executar_plano(
                comando,
                plano_agenda if isinstance(plano_agenda, dict) else {},
                mensagem_retorno,
            )
            if acao_agenda is not None:
                return RespostaRoteador(
                    acao_agenda.texto,
                    agenda_alterada=acao_agenda.agenda_alterada,
                    agenda_referencia=acao_agenda.referencia,
                )

        if acao in ("criar", "atualizar", "reforcar") and conteudo:
            if destino == "anotacoes":
                self.memoria.salvar_nota("Anotacao de Chat", conteudo, tags=["chat", "anotacao"])
                anotacoes_alteradas = True
            elif destino == "memoria_comportamental":
                campos = dados.get("campos_estruturados", {})
                tipo = str(campos.get("tipo_comportamento", "inferencia"))
                nivel = str(dados.get("nivel_confianca", "medio"))
                self.memoria.registrar_comportamento(tipo, conteudo, nivel)
                if tipo == "interesse":
                    interesses = campos.get("interesses") or [conteudo]
                    self._persistir_interesses_inferidos(interesses)
            elif destino == "perfil_pessoal":
                self.memoria.salvar_perfil_pessoal(conteudo)
            elif destino == "noticias_relevantes":
                campos = dados.get("campos_estruturados", {})
                self.memoria.registrar_interacao_noticia(
                    titulo=conteudo,
                    link=str(campos.get("link_noticia") or ""),
                    fonte=str(campos.get("fonte_noticia") or "Gemini"),
                    grupo="relevancia",
                    origem="chat",
                    contexto=comando,
                )

        return RespostaRoteador(
            mensagem_retorno,
            agenda_alterada=agenda_alterada,
            anotacoes_alteradas=anotacoes_alteradas,
        )

    def _persistir_interesses_inferidos(self, interesses: list[str]) -> None:
        itens = _normalizar_interesses_inferidos(interesses)
        if not itens:
            return
        atuais = self.memoria.adicionar_interesses(itens)
        self.config.fontes.noticias.interesses_busca = atuais
        if self.config.config_path is not None:
            self.config.config_path.write_text(renderizar_toml(self.config), encoding="utf-8")

    def _registrar_consulta_noticias(self, consulta: str, noticias: list) -> str:
        """Guarda no banco as noticias devolvidas para uma pergunta do usuario."""
        linhas = [f"Pergunta: {consulta}", "", "## Noticias retornadas", ""]
        for noticia in noticias:
            linhas.append(f"- [{noticia.titulo}]({noticia.link})")
            linhas.append(f"  - Fonte: {noticia.fonte}")
            linhas.append(f"  - Grupo: {noticia.grupo}")
            self.memoria.registrar_interacao_noticia(
                titulo=noticia.titulo,
                link=noticia.link,
                fonte=noticia.fonte,
                grupo=noticia.grupo,
                origem="consulta",
                contexto=consulta,
            )
        caminho = self.memoria.salvar_nota(
            "Consulta de noticias",
            "\n".join(linhas),
            pasta="40_noticias",
            tags=["noticias", "consulta", "banco"],
        )
        return self.memoria.caminho_relativo(caminho)


def _remover_prefixos(texto: str, prefixos: tuple[str, ...]) -> str:
    """Remove verbos iniciais para isolar o conteudo principal do comando."""
    texto_lower = texto.lower()
    for prefixo in prefixos:
        if texto_lower.startswith(prefixo):
            return texto[len(prefixo) :].strip()
    return texto.strip()


def _contexto_memoria(memoria: Memoria, consulta: str) -> str:
    """Monta um contexto curto a partir das memorias mais parecidas."""
    resultados = memoria.buscar(consulta, limite=3)
    contexto_busca = "\n".join(f"{item.titulo}: {item.trecho}" for item in resultados)
    contexto_secretaria = memoria.contexto_secretaria_virtual(limite_noticias=8)
    if contexto_busca:
        return f"{contexto_secretaria}\n\nMemorias relacionadas:\n{contexto_busca}"
    return contexto_secretaria


def _normalizar_interesses_inferidos(interesses: list[str]) -> list[str]:
    itens: list[str] = []
    vistos: set[str] = set()
    for interesse in interesses:
        termo = " ".join(str(interesse).replace(";", ",").split(",")[0].split()).strip()
        if termo and termo.casefold() not in vistos:
            itens.append(termo)
            vistos.add(termo.casefold())
    return itens
