"""Versión publicada del paquete. Un solo número para la API y el registro.

Vive en su propio módulo para que ``core.pipeline`` pueda leerlo sin depender
del orden de inicialización de ``core/__init__.py``.
"""

from __future__ import annotations

__version__ = "0.2.1"
