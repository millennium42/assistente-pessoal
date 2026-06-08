"""Roteador simples de intencoes em texto livre para comandos da V1."""

from __future__ import annotations

from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import AppConfig
from assistente_pessoal.estudos import criar_nota_estudo
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.musica import ClienteMusica, formatar_lancamentos
from assistente_pessoal.noticias import ClienteNoticias, formatar_noticias


class RoteadorComandos:
    """Converte frases curtas em chamadas aos modulos do assistente."""

    def __init__(self, config: AppConfig) -> None:
        """Cria clientes sob demanda a partir da configuracao da aplicacao."""
        self.config = config
        self.memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
        self.llm = ClienteLLM(config.llm)

    def executar(self, texto: str) -> str:
        """Executa a melhor acao conhecida para um texto livre."""
        comando = texto.strip()
        comando_minusculo = comando.lower()
        if not comando:
            return "Nao ouvi nenhum comando."
        if "clima" in comando_minusculo or "tempo" in comando_minusculo:
            return formatar_previsao(ClienteClima().obter_previsao(self.config.localizacao))
        if "noticia" in comando_minusculo or "noticias" in comando_minusculo:
            noticias = ClienteNoticias().listar(
                self.config.fontes.rss,
                incluir_the_news_tecnologia=self.config.fontes.incluir_the_news_tecnologia,
                timezone_local=self.config.localizacao.timezone,
            )
            return formatar_noticias(noticias)
        if "musica" in comando_minusculo or "lancamento" in comando_minusculo:
            cliente = ClienteMusica(self.config.fontes.musicbrainz_user_agent)
            return formatar_lancamentos(cliente.listar_lancamentos(self.config.fontes.artistas))
        if comando_minusculo.startswith(("memorize ", "memorizar ", "salve ", "salvar ")):
            conteudo = _remover_prefixo_memoria(comando)
            caminho = self.memoria.salvar_nota("Memoria rapida", conteudo, tags=["memoria-rapida"])
            return f"Memoria salva em {caminho}."
        if comando_minusculo.startswith(("buscar ", "procure ", "pesquisar ")):
            consulta = _remover_prefixo_busca(comando)
            resultados = self.memoria.buscar(consulta)
            if not resultados:
                return "Nao encontrei memorias para essa busca."
            return "\n".join(f"- {item.titulo}: {item.trecho}" for item in resultados)
        if comando_minusculo.startswith("estudar "):
            tema = comando.removeprefix("estudar").strip() or "Tema sem nome"
            caminho = criar_nota_estudo(self.memoria, tema, tema, self.llm)
            return f"Nota de estudo criada em {caminho}."
        resposta = self.llm.gerar(comando, contexto=_contexto_memoria(self.memoria, comando))
        if resposta:
            return resposta.texto
        return resposta_fallback()


def _remover_prefixo_memoria(texto: str) -> str:
    """Remove verbos comuns de salvamento para deixar apenas o conteudo."""
    for prefixo in ("memorize ", "memorizar ", "salve ", "salvar "):
        if texto.lower().startswith(prefixo):
            return texto[len(prefixo) :].strip()
    return texto.strip()


def _remover_prefixo_busca(texto: str) -> str:
    """Remove verbos comuns de busca para deixar apenas a consulta."""
    for prefixo in ("buscar ", "procure ", "pesquisar "):
        if texto.lower().startswith(prefixo):
            return texto[len(prefixo) :].strip()
    return texto.strip()


def _contexto_memoria(memoria: MemoriaObsidian, consulta: str) -> str:
    """Monta um contexto curto a partir das memorias mais parecidas."""
    resultados = memoria.buscar(consulta, limite=3)
    return "\n".join(f"{item.titulo}: {item.trecho}" for item in resultados)
