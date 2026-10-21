"""El core debe poder importarse sin FastAPI ni la capa app."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import sys

import core  # noqa: F401

forbidden = [
    name
    for name in sys.modules
    if name == "app"
    or name.startswith("app.")
    or name.startswith("fastapi")
    or name.startswith("starlette")
]
print(",".join(sorted(forbidden)))
raise SystemExit(1 if forbidden else 0)
"""


def test_core_does_not_import_http_layers():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"El core cargó módulos prohibidos: {result.stdout.strip()}\n{result.stderr}"
    )


def test_core_source_does_not_import_app():
    offenders = []
    for path in (ROOT / "core").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "import fastapi" in text or "from app" in text or "import app" in text:
            offenders.append(path.name)
    assert not offenders, f"Archivos del core con imports de HTTP: {offenders}"
