"""Frontera entre bytes y matrices. Único punto de decodificación.

Convención del proyecto: todo el core trabaja en **RGB** (uint8, H×W×3). Cuando
se usa OpenCV se explicita la conversión (`cv2.COLOR_RGB2LAB`), nunca se asume
BGR dentro del dominio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError

from core.exceptions import InvalidImage

# Formatos que el decodificador entiende. ``app/uploads.py`` decide cuáles
# acepta la API; acá solo se valida que sean imágenes reales.
READABLE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


@dataclass(frozen=True)
class Photo:
    """Imagen decodificada y su procedencia técnica."""

    image: np.ndarray
    format: str
    width: int
    height: int
    mode: str = field(default="RGB")

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.height, self.width, 3


def read_photo(data: bytes) -> Photo:
    """Decodifica bytes a RGB sin pérdida y valida el contenido real.

    Se verifica primero el contenedor y después se vuelve a abrir para leer los
    píxeles: ``verify()`` consume el archivo y deja el objeto inservible.
    """
    if not data:
        raise InvalidImage("El archivo está vacío.")

    try:
        with Image.open(BytesIO(data)) as probe:
            probe.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise InvalidImage("El archivo no es una imagen legible.") from exc

    try:
        with Image.open(BytesIO(data)) as raw:
            fmt = (raw.format or "").upper()
            if fmt not in READABLE_FORMATS:
                raise InvalidImage(f"Formato de imagen no soportado: {fmt or 'desconocido'}.")
            raw.load()
            rgb = raw.convert("RGB")
            array = np.asarray(rgb, dtype=np.uint8)
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise InvalidImage("La imagen está dañada o truncada.") from exc

    if array.ndim != 3 or array.shape[2] != 3 or array.size == 0:
        raise InvalidImage("La imagen no tiene tres canales RGB utilizables.")

    height, width = array.shape[:2]
    return Photo(image=np.ascontiguousarray(array), format=fmt, width=width, height=height)


def encode_png(image: np.ndarray) -> bytes:
    """Codifica RGB uint8 a PNG sin pérdida."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("encode_png espera una matriz RGB uint8 de H×W×3.")
    buffer = BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()
