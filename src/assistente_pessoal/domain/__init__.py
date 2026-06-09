"""Modelos de dominio compartilhados entre CLI, API e GUI."""

from assistente_pessoal.domain.privacy import (
    DATA_INVENTORY,
    DataInventoryItem,
    DataSensitivity,
    ProcessingPurpose,
)

__all__ = [
    "DATA_INVENTORY",
    "DataInventoryItem",
    "DataSensitivity",
    "ProcessingPurpose",
]
