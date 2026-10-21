"""Jerarquía de errores de dominio.

El core nunca conoce códigos HTTP: solo declara qué falló. El mapeo a status y
código de API vive en ``app/errors.py``.
"""

from __future__ import annotations


class LeafError(Exception):
    """Base de todo error de dominio del análisis de hojas."""


class InvalidImage(LeafError):
    """El archivo no es una imagen legible o el formato no está permitido."""


class UploadTooLarge(LeafError):
    """El archivo supera el tamaño máximo aceptado."""


class UnusableImage(LeafError):
    """La imagen es legible pero no permite un análisis confiable."""


class NotALeaf(LeafError):
    """La imagen no parece superficie de hoja: es otra escena u objeto."""


class InspectionNotFound(LeafError):
    """No existe una inspección con ese identificador."""
