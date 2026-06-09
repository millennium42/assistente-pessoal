"""Interface de linha de comando do assistente pessoal."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from assistente_pessoal.application.services import AssistenteService
from assistente_pessoal.config import (
    caminho_config_padrao,
    carregar_config,
    criar_config_inicial,
    criar_pastas_vault,
)
from assistente_pessoal.logs import console, erro, sucesso
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.roteador import RoteadorComandos
from assistente_pessoal.voz import ouvir_e_transcrever

app = typer.Typer(
    help="Assistente pessoal modular em pt-BR.",
    no_args_is_help=True,
)
memoria_app = typer.Typer(help="Comandos para memoria em Obsidian.")
app.add_typer(memoria_app, name="memoria")


@app.callback()
def configurar_contexto(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Caminho do arquivo config.toml."),
    ] = None,
) -> None:
    """Guarda opcoes globais para os comandos da CLI."""
    ctx.obj = {"config_path": config}


@app.command("init")
def inicializar(
    ctx: typer.Context,
    vault: Annotated[
        Path,
        typer.Option("--vault", help="Pasta do vault dedicado do Obsidian."),
    ] = Path("vault/AssistentePessoal"),
    cidade: Annotated[
        str, typer.Option("--cidade", help="Cidade usada pelo clima.")
    ] = "Santa Maria, RS",
    latitude: Annotated[float, typer.Option("--latitude", help="Latitude WGS84.")] = -29.6868,
    longitude: Annotated[float, typer.Option("--longitude", help="Longitude WGS84.")] = -53.8149,
    timezone: Annotated[
        str,
        typer.Option("--timezone", help="Fuso horario IANA."),
    ] = "America/Sao_Paulo",
    force: Annotated[
        bool,
        typer.Option("--force", help="Sobrescreve config.toml se ele ja existir."),
    ] = False,
) -> None:
    """Cria configuracao inicial e estrutura do vault Obsidian."""
    caminho_config = _caminho_config(ctx)
    if caminho_config.exists() and not force:
        erro(f"{caminho_config} ja existe. Use --force para sobrescrever.")
        raise typer.Exit(1)
    config = criar_config_inicial(
        caminho=caminho_config,
        vault_path=vault,
        cidade=cidade,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )
    criar_pastas_vault(config.vault_path)
    sucesso(f"Configuracao criada em {caminho_config}.")
    sucesso(f"Vault preparado em {config.vault_path}.")


@app.command("chat")
def conversar(
    ctx: typer.Context,
    mensagem: Annotated[str, typer.Argument(help="Mensagem livre para o assistente.")],
    permitir_llm_externo: Annotated[
        bool,
        typer.Option(
            "--permitir-llm-externo",
            help="Permite enviar mensagem e contexto local ao provedor de LLM configurado.",
        ),
    ] = False,
) -> None:
    """Conversa com o LLM configurado ou mostra o fallback local."""
    resposta = _service(ctx).chat(mensagem, permitir_llm_externo=permitir_llm_externo)
    console.print(resposta["texto"])


@app.command("ouvir")
def ouvir(ctx: typer.Context) -> None:
    """Grava voz por alguns segundos, transcreve e executa o comando percebido."""
    config = _carregar(ctx)
    console.print(f"Gravando por {config.voz.duracao_segundos} segundos...")
    texto = ouvir_e_transcrever(config.voz)
    console.print(f"[bold]Transcricao:[/bold] {texto}")
    console.print(RoteadorComandos(config).executar(texto))


@app.command("estudar")
def estudar(
    ctx: typer.Context,
    tema: Annotated[str, typer.Argument(help="Tema da nota de estudo.")],
    conteudo: Annotated[
        str | None,
        typer.Option("--conteudo", help="Texto bruto para resumir e revisar."),
    ] = None,
    arquivo: Annotated[
        Path | None,
        typer.Option("--arquivo", help="Arquivo de texto ou Markdown com material de estudo."),
    ] = None,
    perguntas: Annotated[
        int,
        typer.Option("--perguntas", help="Quantidade de perguntas de revisao."),
    ] = 5,
) -> None:
    """Cria uma nota de estudo no vault com resumo e perguntas."""
    material = _ler_material(conteudo, arquivo)
    resposta = _service(ctx).criar_estudo(tema, material, perguntas)
    sucesso(f"Nota de estudo criada em {resposta['caminho']}.")


@app.command("noticias")
def noticias(
    ctx: typer.Context,
    limite: Annotated[int, typer.Option("--limite", help="Quantidade maxima de noticias.")] = 8,
) -> None:
    """Lista noticias recentes do The News tecnologia e das fontes RSS tech."""
    console.print(_service(ctx).noticias(limite=limite)["texto"])


@app.command("clima")
def clima(ctx: typer.Context) -> None:
    """Mostra previsao do tempo da localizacao configurada."""
    console.print(_service(ctx).clima()["texto"])


@app.command("musica")
def musica(
    ctx: typer.Context,
    dias: Annotated[int, typer.Option("--dias", help="Janela de busca em dias.")] = 45,
) -> None:
    """Lista lancamentos recentes dos artistas configurados."""
    console.print(_service(ctx).musica(dias=dias)["texto"])


@memoria_app.command("salvar")
def memoria_salvar(
    ctx: typer.Context,
    titulo: Annotated[str, typer.Argument(help="Titulo da memoria.")],
    conteudo: Annotated[str, typer.Argument(help="Conteudo a salvar.")],
) -> None:
    """Salva uma memoria em Markdown dentro do vault."""
    config = _carregar(ctx)
    memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
    caminho = memoria.salvar_nota(titulo, conteudo)
    sucesso(f"Memoria salva em {caminho}.")


@memoria_app.command("buscar")
def memoria_buscar(
    ctx: typer.Context,
    consulta: Annotated[str, typer.Argument(help="Texto para procurar na memoria.")],
    limite: Annotated[int, typer.Option("--limite", help="Quantidade maxima de resultados.")] = 5,
) -> None:
    """Busca memorias no indice SQLite FTS5."""
    config = _carregar(ctx)
    memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
    resultados = memoria.buscar(consulta, limite=limite)
    if not resultados:
        console.print("Nenhuma memoria encontrada.")
        return
    tabela = Table(title="Resultados da memoria")
    tabela.add_column("Titulo")
    tabela.add_column("Trecho")
    tabela.add_column("Caminho")
    for item in resultados:
        tabela.add_row(item.titulo, item.trecho, str(item.caminho))
    console.print(tabela)


@memoria_app.command("reindexar")
def memoria_reindexar(ctx: typer.Context) -> None:
    """Reconstrui o indice de busca a partir das notas Markdown."""
    config = _carregar(ctx)
    quantidade = MemoriaObsidian(config.vault_path, config.localizacao.timezone).reindexar()
    sucesso(f"{quantidade} notas reindexadas.")


def _carregar(ctx: typer.Context):
    """Carrega configuracao para comandos e prepara o vault quando necessario."""
    config = carregar_config(_caminho_config(ctx))
    criar_pastas_vault(config.vault_path)
    return config


def _service(ctx: typer.Context) -> AssistenteService:
    """Cria o servico de aplicacao compartilhado pela CLI e API."""
    return AssistenteService(_carregar(ctx))


def _caminho_config(ctx: typer.Context) -> Path:
    """Resolve o caminho de configuracao salvo no contexto Typer."""
    if ctx.obj and ctx.obj.get("config_path"):
        return ctx.obj["config_path"]
    return caminho_config_padrao()


def _ler_material(conteudo: str | None, arquivo: Path | None) -> str:
    """Le material de estudo vindo de texto direto ou arquivo."""
    if conteudo:
        return conteudo
    if arquivo:
        return arquivo.read_text(encoding="utf-8")
    erro("Informe --conteudo ou --arquivo para criar uma nota de estudo.")
    raise typer.Exit(1)
