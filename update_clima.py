import re
from pathlib import Path

clima_path = Path("d:/milla/OneDrive/Documentos/Assistente de IA pessoal/src/assistente_pessoal/clima.py")
content = clima_path.read_text(encoding="utf-8")

# 1. Update PrevisaoClima dataclass
old_dataclass = r"""    cidade: str
    data_alvo: date
    e_hoje: bool
    temperatura_referencia: float \| None
    sensacao: float \| None
    vento: float \| None
    maxima: float \| None
    minima: float \| None
    chuva: float \| None
    codigo_tempo: int \| None"""

new_dataclass = """    cidade: str
    data_alvo: date
    e_hoje: bool
    temperatura_referencia: float | None
    sensacao: float | None
    vento: float | None
    direcao_vento: int | None
    umidade: float | None
    pressao: float | None
    maxima: float | None
    minima: float | None
    chuva: float | None
    uv_max: float | None
    nascer_sol: str | None
    por_sol: str | None
    codigo_tempo: int | None"""

content = re.sub(old_dataclass, new_dataclass, content)

# 2. Update params in obter_previsao
old_params = r""""current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
            "daily": \(
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            \),"""

new_params = """"current": "temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,relative_humidity_2m,surface_pressure,weather_code",
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset,weather_code"
            ),"""
content = re.sub(old_params, new_params, content)

# 3. Update montar_previsao return
old_return = r"""    return PrevisaoClima\(
        cidade=cidade,
        data_alvo=data_alvo,
        e_hoje=e_hoje,
        temperatura_referencia=temperatura_referencia,
        sensacao=atual.get\("apparent_temperature"\) if e_hoje else None,
        vento=atual.get\("wind_speed_10m"\),
        maxima=maxima,
        minima=minima,
        chuva=_valor_na_posicao\(diario.get\("precipitation_probability_max"\), indice\),
        codigo_tempo=_valor_na_posicao\(diario.get\("weather_code"\), indice\)
        if not e_hoje
        else atual.get\("weather_code"\),
    \)"""

new_return = """    nascer = _valor_na_posicao(diario.get("sunrise"), indice)
    por = _valor_na_posicao(diario.get("sunset"), indice)
    if nascer: nascer = nascer.split("T")[-1][:5]
    if por: por = por.split("T")[-1][:5]

    return PrevisaoClima(
        cidade=cidade,
        data_alvo=data_alvo,
        e_hoje=e_hoje,
        temperatura_referencia=temperatura_referencia,
        sensacao=atual.get("apparent_temperature") if e_hoje else None,
        vento=atual.get("wind_speed_10m"),
        direcao_vento=atual.get("wind_direction_10m"),
        umidade=atual.get("relative_humidity_2m"),
        pressao=atual.get("surface_pressure"),
        maxima=maxima,
        minima=minima,
        chuva=_valor_na_posicao(diario.get("precipitation_probability_max"), indice),
        uv_max=_valor_na_posicao(diario.get("uv_index_max"), indice),
        nascer_sol=nascer,
        por_sol=por,
        codigo_tempo=_valor_na_posicao(diario.get("weather_code"), indice)
        if not e_hoje
        else atual.get("weather_code"),
    )"""
content = re.sub(old_return, new_return, content)

clima_path.write_text(content, encoding="utf-8")
print("clima.py updated")
