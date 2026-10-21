"""CLI sobre la misma fachada que usa la API.

Uso:
    python -m core imgs/IMG_20231015_110914_14.png
    python -m core imgs/hoja.png --overlay sandbox/hoja-overlay.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.exceptions import LeafError
from core.io import encode_png, read_photo
from core.orchestrator import LeafInspector
from core.render import render_overlay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core",
        description="Inspecciona una imagen de hoja con visión clásica.",
    )
    parser.add_argument("image", type=Path, help="Ruta de la imagen a inspeccionar.")
    parser.add_argument("--overlay", type=Path, default=None, help="PNG de salida con máscaras.")
    args = parser.parse_args(argv)

    try:
        photo = read_photo(args.image.read_bytes())
        result = LeafInspector().inspect(photo.image)
    except OSError as exc:
        print(f"No se pudo leer {args.image}: {exc}", file=sys.stderr)
        return 2
    except LeafError as exc:
        print(f"Rechazado: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    if args.overlay is not None:
        overlay = render_overlay(photo.image, result.lesion_mask, result.vein_mask)
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        args.overlay.write_bytes(encode_png(overlay))
        print(f"Overlay: {args.overlay}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
