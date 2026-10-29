-- Usuarios, versiones del software y autoría de cada inspección (ADR-017).
--
-- El login vive en la base: sin DATABASE_URL la aplicación sigue en modo
-- archivos y sin autenticación, que es la demo pública. Las sesiones no se
-- guardan acá: viajan como cookie firmada, así que esta tabla no crece con cada
-- acceso.

CREATE TABLE IF NOT EXISTS users (
    id            text        PRIMARY KEY,
    username      text        NOT NULL UNIQUE,
    display_name  text        NOT NULL,
    password_hash text        NOT NULL,
    role          text        NOT NULL DEFAULT 'operador',
    is_active     boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    CONSTRAINT users_role_valid CHECK (role IN ('admin', 'operador'))
);

-- Quién subió cada hoja. Las inspecciones anteriores al login quedan sin dueño.
ALTER TABLE inspections
    ADD COLUMN IF NOT EXISTS user_id text REFERENCES users (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS inspections_user_idx ON inspections (user_id);

-- Una fila por versión publicada, con la huella del método que produjo los
-- números. La inserta el propio guardado (ON CONFLICT) para que el registro de
-- versiones no dependa de un paso manual.
CREATE TABLE IF NOT EXISTS software_versions (
    version        text        PRIMARY KEY,
    method_version text        NOT NULL,
    notes          text        NOT NULL DEFAULT '',
    first_seen     timestamptz NOT NULL DEFAULT now(),
    last_seen      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inspections_app_version_idx ON inspections (app_version);
