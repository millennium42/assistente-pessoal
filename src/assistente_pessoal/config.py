"""Configuracao tipada do assistente e criacao do arquivo inicial."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PASTAS_VAULT = (
    "00_inbox",
    "10_memoria",
    "20_estudos",
    "30_resumos",
    "40_noticias",
    "50_musica",
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
    """Configuracao de um provedor de LLM sem armazenar segredos."""

    provedor: str = "openai-compatible"
    base_url: str = ""
    modelo: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    exigir_opt_in_externo: bool = True

    def habilitado(self) -> bool:
        """Indica se ha informacao suficiente para chamar um LLM externo ou local."""
        return bool(self.base_url.strip() and self.modelo.strip())


class FontesConfig(BaseModel):
    """Fontes externas consultadas pelo assistente."""

    assuntos_interesse: list[str] = Field(default_factory=list)
    rss: list[str] = Field(
        default_factory=lambda: [
            "https://tecnoblog.net/feed/",
            "https://www.canaltech.com.br/rss/",
            "https://olhardigital.com.br/feed/",
        ]
    )
    incluir_the_news_tecnologia: bool = True
    artistas: list[str] = Field(default_factory=list)
    musicbrainz_user_agent: str = "assistente-pessoal/0.1.0 (contato: configure-seu-email)"


class AppConfig(BaseModel):
    """Objeto central de configuracao da aplicacao."""

    vault_path: Path = Path("vault/AssistentePessoal")
    localizacao: LocalizacaoConfig = Field(default_factory=LocalizacaoConfig)
    voz: VozConfig = Field(default_factory=VozConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    fontes: FontesConfig = Field(default_factory=FontesConfig)


class EnvConfig(BaseSettings):
    """Variaveis de ambiente reconhecidas pelo assistente."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assistente_config: Path = Field(default=Path("config.toml"), alias="ASSISTENTE_CONFIG")


def caminho_config_padrao() -> Path:
    """Resolve o caminho de configuracao a partir do ambiente ou do padrao local."""
    return EnvConfig().assistente_config


def carregar_config(caminho: Path | None = None) -> AppConfig:
    """Carrega o arquivo TOML de configuracao ou retorna valores padrao."""
    caminho_real = caminho or caminho_config_padrao()
    if not caminho_real.exists():
        return AppConfig()
    with caminho_real.open("rb") as arquivo:
        dados = tomllib.load(arquivo)
    return AppConfig.model_validate(dados)


def criar_config_inicial(
    caminho: Path,
    vault_path: Path,
    cidade: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> AppConfig:
    """Cria um arquivo ``config.toml`` inicial e devolve a configuracao carregada."""
    config = AppConfig(
        vault_path=vault_path,
        localizacao=LocalizacaoConfig(
            cidade=cidade,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
        ),
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(renderizar_toml(config), encoding="utf-8")
    return config


def renderizar_toml(config: AppConfig) -> str:
    """Renderiza a configuracao em TOML simples, suficiente para a V1."""
    assuntos = "\n".join(f'  "{assunto}",' for assunto in config.fontes.assuntos_interesse)
    rss = "\n".join(f'  "{url}",' for url in config.fontes.rss)
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
provedor = "{_escapar(config.llm.provedor)}"
base_url = "{_escapar(config.llm.base_url)}"
modelo = "{_escapar(config.llm.modelo)}"
api_key_env = "{_escapar(config.llm.api_key_env)}"
exigir_opt_in_externo = {_toml_bool(config.llm.exigir_opt_in_externo)}

[fontes]
incluir_the_news_tecnologia = {_toml_bool(config.fontes.incluir_the_news_tecnologia)}
assuntos_interesse = [
{assuntos}
]
rss = [
{rss}
]
artistas = [
{artistas}
]
musicbrainz_user_agent = "{_escapar(config.fontes.musicbrainz_user_agent)}"
"""


def ler_api_key(nome_variavel: str) -> str:
    """Le uma chave de API por variavel de ambiente sem expor o valor."""
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
