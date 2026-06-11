"""Utilitarios de data e timezone usados pela aplicacao.

Este modulo concentra as funcoes necessarias para lidar com fusos horarios,
conversao de strings de datas humanas em datas reais, e normalizacao de dados
temporais provenientes de fontes externas (como feeds RSS).
"""

from __future__ import annotations

import calendar
import unicodedata
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from time import struct_time
from zoneinfo import ZoneInfo

DIAS_SEMANA = {
    "segunda": 0,
    "terca": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "domingo": 6,
}


def normalizar_texto_ascii(texto: str) -> str:
    """Remove acentos preservando uma forma ASCII previsivel para slugs e chaves.

    Args:
        texto: Texto original com possiveis caracteres acentuados.

    Returns:
        O texto sem acentos, contendo apenas os caracteres base.
    """
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in normalizado if not unicodedata.combining(caractere))


def hoje_local(timezone: str) -> date:
    """Retorna a data local atual no timezone configurado.

    Args:
        timezone: Nome do fuso horario (ex: 'America/Sao_Paulo').

    Returns:
        A data atual correspondente ao fuso horario informado.
    """
    return datetime.now(ZoneInfo(timezone)).date()


def resolver_dia_previsao(dia: str | None, timezone: str, referencia: date | None = None) -> date:
    """Converte um seletor humano de dia em uma data local concreta.

    Suporta valores como 'hoje', 'amanha', 'segunda', 'terca', etc.

    Args:
        dia: A string representando o dia desejado. Se None ou vazio, retorna 'hoje'.
        timezone: O fuso horario a ser utilizado para definir 'hoje'.
        referencia: Data base opcional para os calculos. Por padrao utiliza a data local atual.

    Returns:
        A data exata correspondente ao dia solicitado.

    Raises:
        ValueError: Se a string fornecida nao for um dia reconhecido.
    """
    base = referencia or hoje_local(timezone)
    if dia is None:
        return base
    texto = normalizar_texto_ascii(dia.strip().lower())
    if texto in {"", "hoje"}:
        return base
    if texto == "amanha":
        return base + timedelta(days=1)
    indice_semana = DIAS_SEMANA.get(texto)
    if indice_semana is None:
        raise ValueError(
            "Dia invalido. Use hoje, amanha ou um dia da semana, como segunda ou sexta."
        )
    dias_ate = (indice_semana - base.weekday()) % 7
    if dias_ate == 0:
        dias_ate = 7
    return base + timedelta(days=dias_ate)


def extrair_data_iso(valor: str | None) -> datetime | None:
    """Converte strings de datas ISO em objetos datetime com timezone conhecido.

    Args:
        valor: A string contendo a data no formato ISO 8601.

    Returns:
        Um objeto datetime com fuso horario, ou None se o valor for invalido/vazio.
    """
    if not valor:
        return None
    try:
        normalizado = valor.replace("Z", "+00:00")
        data = datetime.fromisoformat(normalizado)
    except ValueError:
        return None
    if data.tzinfo is None:
        return data.replace(tzinfo=UTC)
    return data


def extrair_data_rss(item: dict) -> datetime | None:
    """Extrai a melhor data publicada de um item proveniente de feed RSS ou Atom.

    Tenta ler primeiro dos campos parseados ('published_parsed', 'updated_parsed')
    e aplica um fallback para os campos de texto brutos ('published', 'updated').

    Args:
        item: Dicionario representando a entrada do feed RSS/Atom.

    Returns:
        A data de publicacao normalizada com fuso horario, ou None em caso de falha.
    """
    publicado_parseado = item.get("published_parsed") or item.get("updated_parsed")
    if isinstance(publicado_parseado, struct_time):
        return datetime.fromtimestamp(calendar.timegm(publicado_parseado), tz=UTC)
    valor = item.get("published") or item.get("updated")
    if not valor:
        return None
    try:
        data = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None
    if data.tzinfo is None:
        return data.replace(tzinfo=UTC)
    return data


def publicado_no_dia(
    publicado_em: datetime | None,
    data_referencia: date,
    timezone: str,
) -> bool:
    """Confere se um dado momento pertence a um dia especifico num fuso horario.

    Args:
        publicado_em: O datetime que queremos verificar.
        data_referencia: A data alvo.
        timezone: O fuso horario utilizado para converter 'publicado_em'.

    Returns:
        True se a data e hora informadas ocorreram durante a data de referencia
        no fuso horario indicado, caso contrario False.
    """
    if publicado_em is None:
        return False
    return publicado_em.astimezone(ZoneInfo(timezone)).date() == data_referencia
