"""Persistencia de inspecciones en disco, detrás de una interfaz mínima.

Frodo gobierna este módulo. El JSON es el punto de commit: si existe, el
resultado y el original también. Toda escritura es atómica (``*.tmp`` +
``os.replace``) y los identificadores se validan antes de tocar el sistema de
archivos.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.exceptions import InspectionNotFound

logger = logging.getLogger("fellowship.repository")

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class InspectionRepository:
    def __init__(self, root: Path, media_prefix: str = "/media") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_prefix = media_prefix.rstrip("/")

    def save(self, original_png: bytes, result_png: bytes, payload: dict[str, Any]) -> dict[str, Any]:
        """Guarda original, resultado y metadatos. Devuelve el registro completo."""
        record_id = uuid4().hex
        record = {
            **payload,
            "id": record_id,
            "result_url": f"{self.media_prefix}/{record_id}-result.png",
            "original_url": f"{self.media_prefix}/{record_id}-original.png",
        }

        self._atomic_write(self._path(record_id, "-original.png"), original_png)
        self._atomic_write(self._path(record_id, "-result.png"), result_png)
        self._atomic_write(
            self._path(record_id, ".json"),
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return record

    def get(self, record_id: str) -> dict[str, Any]:
        self._validate_id(record_id)
        path = self._path(record_id, ".json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise InspectionNotFound(f"No existe la inspección {record_id}.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise InspectionNotFound(f"La inspección {record_id} no se puede leer.") from exc

    def list(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("Registro ilegible, se omite: %s", path, exc_info=True)
                continue
            if isinstance(record, dict):
                records.append(record)
        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return records

    def delete(self, record_id: str) -> None:
        self.get(record_id)
        for suffix in ("-original.png", "-result.png", ".json"):
            self._path(record_id, suffix).unlink(missing_ok=True)

    def clear(self) -> int:
        """Elimina todos los registros y sus artefactos. Devuelve cuántos borró."""
        removed = 0
        for path in sorted(self.root.glob("*.json")):
            record_id = path.stem
            if not ID_PATTERN.fullmatch(record_id):
                continue
            for suffix in (
                "-original.png",
                "-result.png",
                ".json",
                "-original.png.tmp",
                "-result.png.tmp",
                ".json.tmp",
            ):
                self._path(record_id, suffix).unlink(missing_ok=True)
            removed += 1
        return removed

    def _validate_id(self, record_id: str) -> None:
        if not ID_PATTERN.fullmatch(record_id):
            raise InspectionNotFound(f"Identificador inválido: {record_id!r}.")

    def _path(self, record_id: str, suffix: str) -> Path:
        return self.root / f"{record_id}{suffix}"

    def _atomic_write(self, path: Path, data: bytes) -> None:
        temporary = path.with_name(f"{path.name}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
