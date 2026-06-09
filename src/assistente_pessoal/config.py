"""Configuracao tipada do assistente e criacao do arquivo inicial."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from assistente_pessoal.core_paths import resolver_relativo_ao_arquivo

PASTAS_VAULT = (
    "00_inbox",
    "10_memoria",
    "20_estudos",
    "30_resumos",
    "40_noticias",
    "50_musica",
    "60_planejamento",
    "61_agenda_local",
    "90_logs",
)


class LocalizacaoConfig(BaseModel):
    """Dados de localizacao usados pelo modulo de clima."""

    cidade: str = "Santa Maria, RS"
    latitude: float = -29.6868
    longitude: float = -53.8149
    timezone: str = "America/Sao_Paulo"


class VozConfig(BaseModel):
    """Preferencias para gravacao e transcricao de voz."""

    modelo_whisper: str = "tiny"
    idioma: str = "pt"
    duracao_segundos: int = Field(default=6, ge=1, le=60)
    taxa_amostragem: int = 16000


class LLMConfig(BaseModel):
    """Configuracao de um provedor compativel com a API de chat da OpenAI."""

    base_url: str = ""
    modelo: str = ""
    api_key_env: str = "OPENAI_API_KEY"

    def habilitado(self) -> bool:
        """Indica se ha informacao suficiente para chamar um LLM externo ou local."""
        return bool(self.base_url.strip() and self.modelo.strip())


class GoogleAgendaConfig(BaseModel):
    """Configuracao da integracao com Google Agenda para leitura mensal e criacao de eventos."""

    habilitado: bool = False
    credentials_path: Path = Path("google-oauth-client.json")
    token_path: Path = Path(".assistente/google-calendar-token.json")
    calendar_id: str = "primary"
    max_eventos: int = 10
    janela_dias: int = 7


class DashboardConfig(BaseModel):
    """Controla o ritmo da interface e o cache dos blocos externos."""

    intervalo_atualizacao_segundos: int = Field(default=15, ge=5, le=3600)
    ttl_dolar_segundos: int = Field(default=15, ge=5, le=3600)
    ttl_noticias_segundos: int = Field(default=60, ge=15, le=7200)
    ttl_agenda_segundos: int = Field(default=1800, ge=60, le=86400)
    ttl_clima_segundos: int = Field(default=3600, ge=60, le=86400)


class GrupoRssConfig(BaseModel):
    """Agrupa fontes RSS por tema e prioridade."""

    habilitado: bool = True
    rss: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    palavras_chave: list[str] = Field(default_factory=list)
    modo: str = "rss"
    titulo_fonte: str = ""


class TheNewsConfig(BaseModel):
    """Configuracao da fonte The News."""

    habilitado: bool = True
    categoria: str = ""


class NoticiasConfig(BaseModel):
    """Fontes de noticia agrupadas por prioridade semantica."""

    timezone: str = "America/Sao_Paulo"
    apenas_dia_atual: bool = True
    interesses_busca: list[str] = Field(default_factory=list)
    prioridades: list[str] = Field(
        default_factory=lambda: ["the_news", "santa_maria", "tech", "economia_global"]
    )
    the_news: TheNewsConfig = Field(default_factory=TheNewsConfig)
    santa_maria: GrupoRssConfig = Field(
        default_factory=lambda: GrupoRssConfig(
            modo="midia_local",
            urls=[
                "https://diariosm.com.br/",
                "https://bei.net.br/plantao/",
            ],
            palavras_chave=[
                "santa maria",
                "santa-mariense",
                "ufsm",
                "itaara",
                "camobi",
                "regiao central",
                "quarta colonia",
                "agudo",
                "dona francisca",
                "nova palma",
                "sao joao do polesine",
                "sao sepe",
                "sao pedro do sul",
                "julio de castilhos",
                "dilermando de aguiar",
                "formigueiro",
                "jaguari",
                "mata",
                "restinga seca",
                "silveira martins",
                "faxinal do soturno",
                "cruz alta",
            ],
            titulo_fonte="santa maria - midia local",
        )
    )
    tech: GrupoRssConfig = Field(
        default_factory=lambda: GrupoRssConfig(
            rss=[
                "https://tecnoblog.net/feed/",
                "https://www.canaltech.com.br/rss/",
                "https://olhardigital.com.br/feed/",
            ],
            titulo_fonte="tech",
        )
    )
    economia_global: GrupoRssConfig = Field(
        default_factory=lambda: GrupoRssConfig(
            modo="misto",
            rss=[
                "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
                "https://feeds.bbci.co.uk/news/business/rss.xml",
                "http://feeds.marketwatch.com/marketwatch/topstories/",
                "https://www.ecb.europa.eu/rss/press.html",
                "https://www.federalreserve.gov/feeds/press_all.xml",
            ],
            urls=[],
            palavras_chave=[
                "economy",
                "economic",
                "inflation",
                "interest rate",
                "central bank",
                "gdp",
                "tariff",
                "market",
                "markets",
                "stock",
                "stocks",
                "trade",
                "jobs",
                "labour",
                "labor",
                "recession",
                "yield",
                "oil",
                "factory",
                "manufacturing",
            ],
            titulo_fonte="economia global",
        )
    )


class FontesConfig(BaseModel):
    """Fontes externas consultadas pelo assistente."""

    noticias: NoticiasConfig = Field(default_factory=NoticiasConfig)
    artistas: list[str] = Field(default_factory=list)
    musicbrainz_user_agent: str = "assistente-pessoal/0.1.0 (contato: configure-seu-email)"


class AppConfig(BaseModel):
    """Objeto central de configuracao da aplicacao."""

    vault_path: Path = Path("vault/AssistentePessoal")
    localizacao: LocalizacaoConfig = Field(default_factory=LocalizacaoConfig)
    voz: VozConfig = Field(default_factory=VozConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    google_agenda: GoogleAgendaConfig = Field(default_factory=GoogleAgendaConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    fontes: FontesConfig = Field(default_factory=FontesConfig)
    _config_path: Path | None = PrivateAttr(default=None)

    def definir_origem_config(self, caminho: Path | None) -> None:
        """Guarda o caminho real do config para resolver paths relativos com estabilidade."""
        self._config_path = caminho.resolve() if caminho else None
        if self._config_path:
            self.vault_path = resolver_relativo_ao_arquivo(self.vault_path, self._config_path)
            self.google_agenda.credentials_path = resolver_relativo_ao_arquivo(
                self.google_agenda.credentials_path,
                self._config_path,
            )
            self.google_agenda.token_path = resolver_relativo_ao_arquivo(
                self.google_agenda.token_path,
                self._config_path,
            )
            self.fontes.noticias.timezone = self.localizacao.timezone

    @property
    def config_path(self) -> Path | None:
        """Expõe o caminho do arquivo de configuracao quando conhecido."""
        return self._config_path


class EnvConfig(BaseSettings):
    """Variaveis de ambiente reconhecidas pelo assistente."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assistente_config: Path = Field(default=Path("config.toml"), alias="ASSISTENTE_CONFIG")


def caminho_config_padrao() -> Path:
    """Resolve o caminho de configuracao a partir do ambiente ou do padrao local."""
    return EnvConfig().assistente_config


def carregar_config(caminho: Path | None = None) -> AppConfig:
    """Carrega o arquivo TOML de configuracao ou retorna valores padrao."""
    caminho_real = (caminho or caminho_config_padrao()).resolve()
    if not caminho_real.exists():
        config = AppConfig()
        config.definir_origem_config(caminho_real)
        return config
    with caminho_real.open("rb") as arquivo:
        dados = tomllib.load(arquivo)
    config = AppConfig.model_validate(dados)
    config.definir_origem_config(caminho_real)
    return config


def criar_config_inicial(
    caminho: Path,
    vault_path: Path,
    cidade: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> AppConfig:
    """Cria um arquivo ``config.toml`` inicial e devolve a configuracao carregada."""
    caminho_real = caminho.resolve()
    config = AppConfig(
        vault_path=vault_path,
        localizacao=LocalizacaoConfig(
            cidade=cidade,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        ),
    )
    config.fontes.noticias.timezone = timezone
    caminho_real.parent.mkdir(parents=True, exist_ok=True)
    caminho_real.write_text(renderizar_toml(config), encoding="utf-8")
    return carregar_config(caminho_real)


def renderizar_toml(config: AppConfig) -> str:
    """Renderiza a configuracao em TOML simples, suficiente para a V1.1."""
    tech_rss = "\n".join(f'  "{url}",' for url in config.fontes.noticias.tech.rss)
    santa_urls = "\n".join(f'  "{url}",' for url in config.fontes.noticias.santa_maria.urls)
    santa_palavras_chave = "\n".join(
        f'  "{_escapar(palavra)}",' for palavra in config.fontes.noticias.santa_maria.palavras_chave
    )
    economia_rss = "\n".join(f'  "{url}",' for url in config.fontes.noticias.economia_global.rss)
    economia_urls = "\n".join(f'  "{url}",' for url in config.fontes.noticias.economia_global.urls)
    interesses_busca = "\n".join(
        f'  "{_escapar(interesse)}",' for interesse in config.fontes.noticias.interesses_busca
    )
    prioridades = "\n".join(
        f'  "{prioridade}",' for prioridade in config.fontes.noticias.prioridades
    )
    artistas = "\n".join(f'  "{artista}",' for artista in config.fontes.artistas)
    return f"""vault_path = "{_normalizar_path(config.vault_path)}"

[localizacao]
cidade = "{_escapar(config.localizacao.cidade)}"
latitude = {config.localizacao.latitude}
longitude = {config.localizacao.longitude}
timezone = "{_escapar(config.localizacao.timezone)}"

[voz]
modelo_whisper = "{_escapar(config.voz.modelo_whisper)}"
idioma = "{_escapar(config.voz.idioma)}"
duracao_segundos = {config.voz.duracao_segundos}
taxa_amostragem = {config.voz.taxa_amostragem}

[llm]
base_url = "{_escapar(config.llm.base_url)}"
modelo = "{_escapar(config.llm.modelo)}"
api_key_env = "{_escapar(config.llm.api_key_env)}"

[google_agenda]
habilitado = {_toml_bool(config.google_agenda.habilitado)}
credentials_path = "{_normalizar_path(config.google_agenda.credentials_path)}"
token_path = "{_normalizar_path(config.google_agenda.token_path)}"
calendar_id = "{_escapar(config.google_agenda.calendar_id)}"
max_eventos = {config.google_agenda.max_eventos}
janela_dias = {config.google_agenda.janela_dias}

[dashboard]
intervalo_atualizacao_segundos = {config.dashboard.intervalo_atualizacao_segundos}
ttl_dolar_segundos = {config.dashboard.ttl_dolar_segundos}
ttl_noticias_segundos = {config.dashboard.ttl_noticias_segundos}
ttl_agenda_segundos = {config.dashboard.ttl_agenda_segundos}
ttl_clima_segundos = {config.dashboard.ttl_clima_segundos}

[fontes.noticias]
timezone = "{_escapar(config.fontes.noticias.timezone)}"
apenas_dia_atual = {_toml_bool(config.fontes.noticias.apenas_dia_atual)}
interesses_busca = [
{interesses_busca}
]
prioridades = [
{prioridades}
]

[fontes.noticias.the_news]
habilitado = {_toml_bool(config.fontes.noticias.the_news.habilitado)}
categoria = "{_escapar(config.fontes.noticias.the_news.categoria)}"

[fontes.noticias.santa_maria]
habilitado = {_toml_bool(config.fontes.noticias.santa_maria.habilitado)}
modo = "{_escapar(config.fontes.noticias.santa_maria.modo)}"
titulo_fonte = "{_escapar(config.fontes.noticias.santa_maria.titulo_fonte)}"
urls = [
{santa_urls}
]
palavras_chave = [
{santa_palavras_chave}
]

[fontes.noticias.tech]
habilitado = {_toml_bool(config.fontes.noticias.tech.habilitado)}
titulo_fonte = "{_escapar(config.fontes.noticias.tech.titulo_fonte)}"
rss = [
{tech_rss}
]

[fontes.noticias.economia_global]
habilitado = {_toml_bool(config.fontes.noticias.economia_global.habilitado)}
modo = "{_escapar(config.fontes.noticias.economia_global.modo)}"
titulo_fonte = "{_escapar(config.fontes.noticias.economia_global.titulo_fonte)}"
rss = [
{economia_rss}
]
urls = [
{economia_urls}
]

[fontes]
artistas = [
{artistas}
]
musicbrainz_user_agent = "{_escapar(config.fontes.musicbrainz_user_agent)}"
"""


def ler_api_key(nome_variavel: str) -> str:
    """Le uma chave de API do ambiente sem expor o valor em logs ou arquivos."""
    return os.getenv(nome_variavel, "")


def criar_pastas_vault(vault_path: Path) -> None:
    """Cria as pastas padrao do vault dedicado do Obsidian."""
    for pasta in PASTAS_VAULT:
        (vault_path / pasta).mkdir(parents=True, exist_ok=True)
    # A pasta oculta guarda indices tecnicos para nao poluir a navegacao do Obsidian.
    (vault_path / ".assistente").mkdir(parents=True, exist_ok=True)


def _normalizar_path(caminho: Path) -> str:
    """Converte caminhos para um formato TOML legivel em Windows e Unix."""
    return caminho.as_posix()


def _escapar(valor: Any) -> str:
    """Escapa aspas e barras invertidas para escrita segura em strings TOML."""
    return str(valor).replace("\\", "\\\\").replace('"', '\\"')


def _toml_bool(valor: bool) -> str:
    """Renderiza booleanos no formato esperado pelo TOML."""
    return "true" if valor else "false"
