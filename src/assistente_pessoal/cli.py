"""Interface de linha de comando do assistente pessoal."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer
from rich.table import Table

from assistente_pessoal.agenda_google import (
    ClienteGoogleAgenda,
    NovoEventoGoogleAgenda,
    formatar_eventos_google,
)
from assistente_pessoal.clima import ClienteClima, formatar_previsao
from assistente_pessoal.config import (
    caminho_config_padrao,
    carregar_config,
    criar_config_inicial,
    criar_pastas_vault,
)
from assistente_pessoal.estudos import criar_nota_estudo
from assistente_pessoal.llm import ClienteLLM, resposta_fallback
from assistente_pessoal.logs import avisar, console, erro, sucesso
from assistente_pessoal.memoria import MemoriaObsidian
from assistente_pessoal.musica import ClienteMusica, formatar_lancamentos
from assistente_pessoal.noticias import (
    LIMITE_PADRAO_NOTICIAS,
    ClienteNoticias,
    formatar_noticias,
)
from assistente_pessoal.roteador import RoteadorComandos
from assistente_pessoal.voz import ouvir_e_transcrever

app = typer.Typer(
    help="Assistente pessoal modular em pt-BR.",
    no_args_is_help=True,
)
memoria_app = typer.Typer(help="Comandos para memoria em Obsidian.")
agenda_app = typer.Typer(help="Comandos para agenda local e Google Agenda.")
app.add_typer(memoria_app, name="memoria")
app.add_typer(agenda_app, name="agenda")


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
        erro(f"{caminho_config.name} ja existe. Use --force para sobrescrever.")
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
    sucesso(f"Configuracao criada em {caminho_config.name}.")
    sucesso(f"Vault efetivo preparado em {config.vault_path.as_posix()}.")


@app.command("chat")
def conversar(
    ctx: typer.Context,
    mensagem: Annotated[str, typer.Argument(help="Mensagem livre para o assistente.")],
) -> None:
    """Conversa com o LLM configurado ou mostra o fallback local."""
    config = _carregar(ctx)
    memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
    llm = ClienteLLM(config.llm)
    contexto = "\n".join(
        f"{item.titulo}: {item.trecho}" for item in memoria.buscar(mensagem, limite=3)
    )
    resposta = llm.gerar(mensagem, contexto=contexto)
    console.print(resposta.texto if resposta else resposta_fallback())


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
    config = _carregar(ctx)
    material = _ler_material(conteudo, arquivo)
    memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
    caminho = criar_nota_estudo(memoria, tema, material, ClienteLLM(config.llm), perguntas)
    sucesso(f"Nota de estudo criada em {memoria.caminho_relativo(caminho)}.")


@app.command("noticias")
def noticias(
    ctx: typer.Context,
    limite: Annotated[
        int,
        typer.Option("--limite", help="Quantidade maxima de noticias."),
    ] = LIMITE_PADRAO_NOTICIAS,
) -> None:
    """Lista noticias recentes do dia em ordem de publicacao."""
    config = _carregar(ctx)
    itens = ClienteNoticias().listar(config.fontes.noticias, limite=limite)
    console.print(formatar_noticias(itens, timezone=config.fontes.noticias.timezone))


@app.command("clima")
def clima(
    ctx: typer.Context,
    dia: Annotated[
        str | None,
        typer.Option("--dia", help="Hoje, amanha ou um dia da semana futuro."),
    ] = None,
) -> None:
    """Mostra previsao do tempo da localizacao configurada."""
    config = _carregar(ctx)
    previsao = ClienteClima().obter_previsao(config.localizacao, dia=dia)
    console.print(formatar_previsao(previsao))


@app.command("gui")
def gui(
    ctx: typer.Context,
    host: Annotated[str, typer.Option("--host", help="Host local do dashboard.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Porta local do dashboard.")] = 8765,
) -> None:
    """Inicia um dashboard local com clima, noticias e notas do vault."""
    config = _carregar(ctx)
    from assistente_pessoal.gui import iniciar_dashboard, resolver_porta_dashboard

    porta_real = resolver_porta_dashboard(host, port)
    if porta_real != port:
        avisar(f"Porta {port} ocupada. Vou usar a porta {porta_real}.")
    sucesso(f"Dashboard iniciando em http://{host}:{porta_real}")
    iniciar_dashboard(config, host=host, port=porta_real)


@app.command("musica")
def musica(
    ctx: typer.Context,
    dias: Annotated[int, typer.Option("--dias", help="Janela de busca em dias.")] = 45,
) -> None:
    """Lista lancamentos recentes dos artistas configurados."""
    config = _carregar(ctx)
    cliente = ClienteMusica(config.fontes.musicbrainz_user_agent)
    console.print(
        formatar_lancamentos(cliente.listar_lancamentos(config.fontes.artistas, dias=dias))
    )


@agenda_app.command("google-auth")
def agenda_google_auth(ctx: typer.Context) -> None:
    """Executa o login OAuth da Google Agenda e salva um token local."""
    config = _carregar(ctx)
    cliente = ClienteGoogleAgenda(config.google_agenda)
    if not config.google_agenda.credentials_path.exists():
        erro(
            "Nao encontrei o arquivo de credenciais OAuth do Google. "
            "Configure google_agenda.credentials_path no config.toml."
        )
        raise typer.Exit(1)
    caminho = cliente.autenticar_interativo()
    sucesso(f"Token Google salvo em {caminho.as_posix()}.")


@agenda_app.command("google-listar")
def agenda_google_listar(ctx: typer.Context) -> None:
    """Lista os proximos eventos da Google Agenda configurada."""
    config = _carregar(ctx)
    eventos = ClienteGoogleAgenda(config.google_agenda).listar_eventos()
    console.print(formatar_eventos_google(eventos))


@agenda_app.command("google-criar")
def agenda_google_criar(
    ctx: typer.Context,
    titulo: Annotated[str, typer.Argument(help="Titulo do evento.")],
    data: Annotated[str, typer.Option("--data", help="Data no formato AAAA-MM-DD.")],
    hora: Annotated[str, typer.Option("--hora", help="Hora no formato HH:MM.")] = "09:00",
    duracao: Annotated[int, typer.Option("--duracao", help="Duracao em minutos.")] = 60,
    local: Annotated[str, typer.Option("--local", help="Local do evento.")] = "",
    descricao: Annotated[str, typer.Option("--descricao", help="Descricao do evento.")] = "",
) -> None:
    """Cria um evento simples na Google Agenda configurada."""
    config = _carregar(ctx)
    inicio = datetime.fromisoformat(f"{data}T{hora}:00").replace(
        tzinfo=ZoneInfo(config.localizacao.timezone)
    )
    evento = NovoEventoGoogleAgenda(
        titulo=titulo,
        inicio=inicio,
        fim=inicio + timedelta(minutes=duracao),
        local=local,
        descricao=descricao,
    )
    criado = ClienteGoogleAgenda(config.google_agenda).criar_evento(evento)
    sucesso(f"Evento criado: {criado.titulo} em {criado.inicio}.")


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
    sucesso(f"Memoria salva em {memoria.caminho_relativo(caminho)}.")


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
    tabela.add_column("Caminho no vault")
    for item in resultados:
        tabela.add_row(item.titulo, item.trecho, memoria.caminho_relativo(item.caminho))
    console.print(tabela)


@memoria_app.command("reindexar")
def memoria_reindexar(ctx: typer.Context) -> None:
    """Reconstrui o indice de busca a partir das notas Markdown."""
    config = _carregar(ctx)
    quantidade = MemoriaObsidian(config.vault_path, config.localizacao.timezone).reindexar()
    sucesso(f"{quantidade} notas reindexadas.")


@memoria_app.command("info")
def memoria_info(ctx: typer.Context) -> None:
    """Mostra qual vault esta em uso e quantas notas ele contem."""
    config = _carregar(ctx)
    memoria = MemoriaObsidian(config.vault_path, config.localizacao.timezone)
    estatisticas = memoria.estatisticas()
    tabela = Table(title="Diagnostico do vault")
    tabela.add_column("Campo")
    tabela.add_column("Valor")
    tabela.add_row("Vault efetivo", estatisticas.vault_path.as_posix())
    tabela.add_row("Indice", estatisticas.indice_path.as_posix())
    tabela.add_row("Notas Markdown", str(estatisticas.quantidade_notas))
    console.print(tabela)


def _carregar(ctx: typer.Context):
    """Carrega configuracao para comandos e prepara o vault quando necessario."""
    config = carregar_config(_caminho_config(ctx))
    criar_pastas_vault(config.vault_path)
    return config


def _caminho_config(ctx: typer.Context) -> Path:
    """Resolve o caminho de configuracao salvo no contexto Typer."""
    if ctx.obj and ctx.obj.get("config_path"):
        return Path(ctx.obj["config_path"])
    return caminho_config_padrao()


def _ler_material(conteudo: str | None, arquivo: Path | None) -> str:
    """Le material de estudo vindo de texto direto ou arquivo."""
    if conteudo:
        return conteudo
    if arquivo:
        return arquivo.read_text(encoding="utf-8")
    erro("Informe --conteudo ou --arquivo para criar uma nota de estudo.")
    raise typer.Exit(1)
