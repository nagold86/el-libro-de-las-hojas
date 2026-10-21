"""Configuración por entorno: local en disco, Vercel en /tmp."""

from __future__ import annotations

from pathlib import Path

from app.config import (
    DEFAULT_MAX_UPLOAD_BYTES,
    PROJECT_ROOT,
    VERCEL_MAX_UPLOAD_BYTES,
    VERCEL_STORAGE_DIR,
    Settings,
)


def _clear_env(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("FELLOWSHIP_STORAGE_DIR", raising=False)
    monkeypatch.delenv("FELLOWSHIP_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.delenv("FELLOWSHIP_FRONTEND_DIR", raising=False)


def test_local_uses_project_storage(monkeypatch):
    _clear_env(monkeypatch)

    settings = Settings.from_env()

    assert settings.storage_dir == PROJECT_ROOT / "storage"
    assert settings.max_upload_bytes == DEFAULT_MAX_UPLOAD_BYTES


def test_vercel_uses_ephemeral_storage(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    settings = Settings.from_env()

    assert settings.storage_dir == VERCEL_STORAGE_DIR
    assert settings.max_upload_bytes == VERCEL_MAX_UPLOAD_BYTES


def test_explicit_environment_wins(monkeypatch, tmp_path: Path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FELLOWSHIP_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("FELLOWSHIP_MAX_UPLOAD_BYTES", "1234")

    settings = Settings.from_env()

    assert settings.storage_dir == tmp_path
    assert settings.max_upload_bytes == 1234
