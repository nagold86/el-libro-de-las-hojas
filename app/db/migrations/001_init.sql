-- Esquema inicial del registro de análisis (ADR-016).
--
-- Las columnas tipadas se derivan del payload al insertar y nunca se
-- actualizan aparte: la fila es un índice consultable del registro completo.
-- Se usa text en vez de char(n) para no arrastrar relleno de espacios.

CREATE TABLE IF NOT EXISTS inspections (
    id                  text        PRIMARY KEY,
    created_at          timestamptz NOT NULL,
    method_version      text        NOT NULL,
    app_version         text        NOT NULL,
    image_sha256        text        NOT NULL,
    filename            text        NOT NULL,
    width               integer     NOT NULL,
    height              integer     NOT NULL,
    format              text        NOT NULL,
    lesion_count        integer     NOT NULL,
    area_fraction       double precision NOT NULL,
    chlorosis_fraction  double precision NOT NULL,
    payload             jsonb       NOT NULL,
    original_png        bytea       NOT NULL
);

CREATE INDEX IF NOT EXISTS inspections_created_idx ON inspections (created_at DESC);
CREATE INDEX IF NOT EXISTS inspections_area_idx    ON inspections (area_fraction DESC);
CREATE INDEX IF NOT EXISTS inspections_sha_idx     ON inspections (image_sha256);
