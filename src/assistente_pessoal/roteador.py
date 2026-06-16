"""Roteador simples de intencoes em texto livre para o assistente atual."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from assistente_pessoal.agenda_chat import AssistenteAgendaChat
from assistente_pessoal.agenda_google import ClienteGoogleAgenda
from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import AppConfig
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.memoria import Memoria
from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias

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
        """Executa a melhor acao conhecida e informa se a agenda foi alterada."""
        comando = texto.strip()
        comando_minusculo = comando.lower()
        if not comando:
            return RespostaRoteador("Nao ouvi nenhum comando.")
        acao_agenda = self.agenda_chat.tentar_executar(comando)
        if acao_agenda is not None:
            return RespostaRoteador(
                acao_agenda.texto,
                agenda_alterada=acao_agenda.agenda_alterada,
                agenda_referencia=acao_agenda.referencia,
            )
        if "clima" in comando_minusculo or "tempo" in comando_minusculo:
            return RespostaRoteador(
                formatar_previsao(ClienteClima().obter_previsao(self.config.localizacao))
            )
        if "noticia" in comando_minusculo or "noticias" in comando_minusculo:
            noticias = ClienteNoticias().listar(self.config.fontes.noticias)
            resposta = formatar_noticias(noticias, timezone=self.config.fontes.noticias.timezone)
            if noticias:
                caminho = self._registrar_consulta_noticias(comando, noticias)
                resposta = f"{resposta}\n\nConsulta salva no banco de dados em {caminho}."
            return RespostaRoteador(resposta)
        if comando_minusculo.startswith(PREFIXOS_MEMORIA):
            conteudo = _remover_prefixos(comando, PREFIXOS_MEMORIA)
            caminho = self.memoria.salvar_nota("Memoria rapida", conteudo, tags=["memoria-rapida"])
            return RespostaRoteador(f"Memoria salva em {self.memoria.caminho_relativo(caminho)}.")
        if comando_minusculo.startswith(PREFIXOS_BUSCA):
            consulta = _remover_prefixos(comando, PREFIXOS_BUSCA)
            resultados = self.memoria.buscar(consulta)
            if not resultados:
                return RespostaRoteador("Nao encontrei memorias para essa busca.")
            return RespostaRoteador(
                "\n".join(f"- {item.titulo}: {item.trecho}" for item in resultados)
            )
        resposta = self.llm.gerar(comando, contexto=_contexto_memoria(self.memoria, comando))
        if resposta:
            return RespostaRoteador(resposta.texto)
        return RespostaRoteador(resposta_fallback())

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
