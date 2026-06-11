"""Roteador simples de intencoes em texto livre para comandos da V1."""

from __future__ import annotations

from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import AppConfig
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.memoria import MemoriaObsidian
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
            noticias = ClienteNoticias().listar(self.config.fontes.noticias)
            resposta = formatar_noticias(noticias, timezone=self.config.fontes.noticias.timezone)
            if noticias:
                caminho = self._registrar_consulta_noticias(comando, noticias)
                resposta = f"{resposta}\n\nConsulta salva no Obsidian em {caminho}."
            return resposta
        if comando_minusculo.startswith(PREFIXOS_MEMORIA):
            conteudo = _remover_prefixos(comando, PREFIXOS_MEMORIA)
            caminho = self.memoria.salvar_nota("Memoria rapida", conteudo, tags=["memoria-rapida"])
            return f"Memoria salva em {self.memoria.caminho_relativo(caminho)}."
        if comando_minusculo.startswith(PREFIXOS_BUSCA):
            consulta = _remover_prefixos(comando, PREFIXOS_BUSCA)
            resultados = self.memoria.buscar(consulta)
            if not resultados:
                return "Nao encontrei memorias para essa busca."
            return "\n".join(f"- {item.titulo}: {item.trecho}" for item in resultados)
        resposta = self.llm.gerar(comando, contexto=_contexto_memoria(self.memoria, comando))
        if resposta:
            return resposta.texto
        return resposta_fallback()

    def _registrar_consulta_noticias(self, consulta: str, noticias: list) -> str:
        """Guarda no vault as noticias devolvidas para uma pergunta do usuario."""
        linhas = [f"Pergunta: {consulta}", "", "## Noticias retornadas", ""]
        for noticia in noticias:
            linhas.append(f"- [{noticia.titulo}]({noticia.link})")
            linhas.append(f"  - Fonte: {noticia.fonte}")
            linhas.append(f"  - Grupo: {noticia.grupo}")
        caminho = self.memoria.salvar_nota(
            "Consulta de noticias",
            "\n".join(linhas),
            pasta="40_noticias",
            tags=["noticias", "consulta", "obsidian"],
        )
        return self.memoria.caminho_relativo(caminho)


def _remover_prefixos(texto: str, prefixos: tuple[str, ...]) -> str:
    """Remove verbos iniciais para isolar o conteudo principal do comando."""
    texto_lower = texto.lower()
    for prefixo in prefixos:
        if texto_lower.startswith(prefixo):
            return texto[len(prefixo):].strip()
    return texto.strip()


def _contexto_memoria(memoria: MemoriaObsidian, consulta: str) -> str:
    """Monta um contexto curto a partir das memorias mais parecidas."""
    resultados = memoria.buscar(consulta, limite=3)
    return "\n".join(f"{item.titulo}: {item.trecho}" for item in resultados)
