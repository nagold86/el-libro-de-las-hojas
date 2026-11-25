"""Las diez muestras viajan con la app y ninguna regla de empaquetado las excluye.

**Validates: Requirements 2.1, 2.2, 2.3, 3.4, 3.5**
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.routers import examples as examples_module

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "app" / "example_images"
FRONTEND_COPY = ROOT / "frontend" / "examples"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FILENAMES = [example["filename"] for example in examples_module.EXAMPLES]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def _exclude_patterns() -> list[str]:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    raw = config["functions"]["app/main.py"]["excludeFiles"]
    match = re.fullmatch(r"\{(.*)\}", raw)
    return match.group(1).split(",") if match else [raw]


def _vercelignore_patterns() -> list[str]:
    lines = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith(("#", "!"))]


def _vercelignore_matches(pattern: str, rel: str) -> bool:
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        if "/" not in prefix:
            return prefix in rel.split("/")[:-1]
        return rel.startswith(prefix + "/")
    if "/" not in pattern:
        return bool(_glob_to_regex(pattern).match(rel.rsplit("/", 1)[-1]))
    return bool(_glob_to_regex(pattern).match(rel))


@pytest.mark.parametrize("filename", FILENAMES)
def test_every_catalogue_sample_is_bundled_as_png(filename):
    path = BUNDLED / filename
    assert path.is_file(), f"falta {path}"
    assert path.read_bytes().startswith(PNG_SIGNATURE)


@pytest.mark.parametrize("filename", FILENAMES)
def test_bundled_sample_is_byte_identical_to_frontend_copy(filename):
    original = FRONTEND_COPY / filename
    if not original.is_file():
        pytest.skip("frontend/examples no existe en este entorno")
    assert _sha(BUNDLED / filename) == _sha(original)


def test_image_root_points_to_bundled_directory():
    assert Path(examples_module.IMAGE_ROOT).resolve() == BUNDLED.resolve()


@pytest.mark.parametrize("filename", FILENAMES)
def test_no_exclude_pattern_matches_bundled_sample(filename):
    rel = f"app/example_images/{filename}"
    for pattern in _exclude_patterns():
        assert not _glob_to_regex(pattern).match(rel), pattern
    for pattern in _vercelignore_patterns():
        assert not _vercelignore_matches(pattern, rel), pattern


def test_exclusion_matchers_still_exclude_dataset():
    assert any(_glob_to_regex(p).match("imgs/a.png") for p in _exclude_patterns())
    assert any(_vercelignore_matches(p, "imgs/a.png") for p in _vercelignore_patterns())


@pytest.mark.skipif(shutil.which("git") is None, reason="git no disponible")
def test_git_does_not_ignore_bundled_samples_but_ignores_imgs():
    def ignored(path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True
        )
        if result.returncode not in (0, 1):
            pytest.skip("no es un repositorio git")
        return result.returncode == 0

    assert not any(ignored(f"app/example_images/{name}") for name in FILENAMES)
    assert ignored("imgs/x.png")
