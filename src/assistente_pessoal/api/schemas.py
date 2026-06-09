"""Schemas HTTP da API local."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    """Payload para criar memoria local."""

    titulo: str = Field(min_length=1, max_length=160)
    conteudo: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Payload do chat com opt-in explicito para LLM externo."""

    mensagem: str = Field(min_length=1)
    permitir_llm_externo: bool = False


class StudyRequest(BaseModel):
    """Payload para criar nota de estudo."""

    tema: str = Field(min_length=1, max_length=160)
    conteudo: str = Field(min_length=1)
    perguntas: int = Field(default=5, ge=1, le=20)


class NewsInterestRequest(BaseModel):
    """Payload para registrar uma noticia clicada/salva como interesse."""

    titulo: str = Field(min_length=1, max_length=300)
    link: str = ""
    fonte: str = ""
    resumo: str = ""
    publicado: str = ""
    tags: list[str] = Field(default_factory=list)


class CalendarEventCreateRequest(BaseModel):
    """Payload para criar evento no Google Agenda."""

    titulo: str = Field(min_length=1, max_length=160)
    inicio: str = Field(min_length=1)
    fim: str | None = None
    descricao: str = ""
