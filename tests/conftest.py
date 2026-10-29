"""Fixtures compartidas. El storage se aísla ANTES de importar la app."""

from __future__ import annotations

import os
import sys
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from core.io import encode_png  # noqa: E402

# Base de docker-compose. Se puede apuntar a otra con FELLOWSHIP_TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get(
    "FELLOWSHIP_TEST_DATABASE_URL",
    "postgresql://fellowship:fellowship@127.0.0.1:5433/fellowship_test",
)

# Credenciales del administrador de prueba (ADR-017). Se recrean en cada fixture:
# el bootstrap solo actúa cuando la tabla de usuarios está vacía.
AUTH_SECRET = "secreto-de-prueba-no-usar-en-produccion"
ADMIN_USER = "nico"
ADMIN_PASSWORD = "clave-de-prueba-123"


@pytest.fixture
def settings_factory(tmp_path: Path):
    def make(**overrides) -> Settings:
        values = {
            "storage_dir": tmp_path / "storage",
            "frontend_dir": ROOT / "frontend",
            "max_upload_bytes": 2 * 1024 * 1024,
            "allowed_formats": frozenset({"PNG", "JPEG"}),
            "secret_key": AUTH_SECRET,
        }
        values.update(overrides)
        return Settings(**values)

    return make


@pytest.fixture
def settings(settings_factory) -> Settings:
    return settings_factory()


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def leaf_image() -> np.ndarray:
    """Superficie verde con dos manchas pardas y ruido reproducible."""
    height, width = 240, 240
    rng = np.random.default_rng(7)

    base = np.zeros((height, width, 3), dtype=np.float32)
    base[..., 0] = 74
    base[..., 1] = 122
    base[..., 2] = 58

    xx = np.linspace(-12, 12, width, dtype=np.float32)[None, :, None]
    yy = np.linspace(-12, 12, height, dtype=np.float32)[:, None, None]
    image = np.clip(base + xx + 0.6 * yy + rng.normal(0, 4, base.shape), 0, 255).astype(np.uint8)

    cv2.ellipse(image, (170, 90), (28, 20), 0, 0, 360, (92, 60, 38), -1)
    cv2.ellipse(image, (70, 170), (14, 10), 25, 0, 360, (110, 78, 48), -1)
    return image


@pytest.fixture
def leaf_on_background() -> np.ndarray:
    """Hoja verde sobre una mesa parda: el aislamiento debe recortar el fondo."""
    height, width = 320, 420
    rng = np.random.default_rng(11)

    background = np.zeros((height, width, 3), dtype=np.float32)
    background[..., 0] = 158
    background[..., 1] = 126
    background[..., 2] = 96
    image = np.clip(
        background + rng.normal(0, 6, background.shape), 0, 255
    ).astype(np.uint8)

    leaf = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(leaf, (220, 160), (120, 65), 12, 0, 360, 255, -1)
    cv2.line(leaf, (105, 190), (60, 230), 255, 8)

    leaf_color = np.zeros_like(image, dtype=np.float32)
    leaf_color[..., 0] = 78
    leaf_color[..., 1] = 126
    leaf_color[..., 2] = 60
    leaf_rgb = np.clip(
        leaf_color + rng.normal(0, 8, leaf_color.shape), 0, 255
    ).astype(np.uint8)
    selected = leaf > 0
    image[selected] = leaf_rgb[selected]

    cv2.ellipse(image, (250, 150), (18, 12), 0, 0, 360, (96, 62, 40), -1)
    return image


@pytest.fixture
def png_bytes(leaf_image: np.ndarray) -> bytes:
    return encode_png(leaf_image)


@pytest.fixture
def blank_image() -> np.ndarray:
    """Imagen legible pero sin nitidez: la puerta de calidad debe rechazarla."""
    return np.full((120, 120, 3), (100, 140, 70), dtype=np.uint8)


@pytest.fixture
def document_image() -> np.ndarray:
    """Nítida y bien expuesta, pero no es una hoja: la puerta de dominio la rechaza."""
    image = np.full((240, 240, 3), 246, dtype=np.uint8)
    rng = np.random.default_rng(5)
    for row in range(20, 220, 18):
        width = int(rng.integers(60, 200))
        cv2.rectangle(image, (20, row), (20 + width, row + 7), (30, 30, 34), -1)
    return image


# -- Postgres (ADR-016) ---------------------------------------------------
# Los tests que escriben en la base se saltean si no hay servidor o driver:
# el resto de la suite no depende de nada.


def truncate_postgres(dsn: str) -> None:
    """Deja las tablas del almanaque vacías, sin importar quién las haya escrito."""
    from app.db.connection import connect

    with closing(connect(dsn)) as connection:
        connection.execute("DELETE FROM inspections")
        connection.execute("DELETE FROM software_versions")
        # Al final, cuando las inspecciones ya no apuntan a nadie.
        connection.execute("DELETE FROM users")
        connection.commit()


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """DSN de la base de prueba, migrada y lista. Se saltea si no hay Postgres."""
    pytest.importorskip("psycopg", reason="Falta psycopg. Instalar con: pip install -e .")

    from app.db.connection import check, connect
    from app.db.migrate import apply_migrations

    if not check(TEST_DATABASE_URL, timeout=1):
        pytest.skip(
            f"Postgres no responde en {TEST_DATABASE_URL}. "
            "Levantarlo con: docker compose up -d"
        )

    with closing(connect(TEST_DATABASE_URL)) as connection:
        apply_migrations(connection)
    return TEST_DATABASE_URL


@pytest.fixture
def sql_store(postgres_dsn: str):
    """Repositorio en base, con la tabla limpia antes y después del test."""
    from app.sql_repository import SqlInspectionRepository

    truncate_postgres(postgres_dsn)
    yield SqlInspectionRepository(postgres_dsn, use_pool=False)
    truncate_postgres(postgres_dsn)


@pytest.fixture(params=["archivos", "postgres"])
def any_store(request, tmp_path: Path):
    """La misma batería contra las dos implementaciones del contrato."""
    if request.param == "postgres":
        return request.getfixturevalue("sql_store")

    from app.repository import InspectionRepository

    return InspectionRepository(tmp_path / "storage")


@pytest.fixture
def sql_settings(postgres_dsn: str, settings_factory):
    """Settings con base y login activo, con el administrador de prueba."""
    return settings_factory(
        database_url=postgres_dsn,
        is_serverless=True,
        admin_username=ADMIN_USER,
        admin_password=ADMIN_PASSWORD,
    )


@pytest.fixture
def sql_client_anon(postgres_dsn: str, sql_settings):
    """App con login obligatorio, sin sesión: la puerta de la API."""
    truncate_postgres(postgres_dsn)
    with TestClient(create_app(sql_settings)) as client:
        yield client
    truncate_postgres(postgres_dsn)


@pytest.fixture
def sql_client(postgres_dsn: str, sql_settings):
    """App completa apuntando a la base, con sesión iniciada como admin."""
    truncate_postgres(postgres_dsn)
    with TestClient(create_app(sql_settings)) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 200, response.text
        yield client
    truncate_postgres(postgres_dsn)
