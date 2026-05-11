-- Planportal metadata schema
-- One row per QGIS project; layers/themes/layouts stored as jsonb plus normalised lookups.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS planportal;

-- ── projects ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.project (
    slug          TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    qgs_path      TEXT NOT NULL,
    qgs_mtime     TIMESTAMPTZ NOT NULL,
    crs           TEXT NOT NULL,
    bbox          GEOMETRY(POLYGON, 4326),
    thumbnail_url TEXT,
    status        TEXT NOT NULL CHECK (status IN ('active','draft','archived','error')),
    error_msg     TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS project_status_idx ON planportal.project (status);
CREATE INDEX IF NOT EXISTS project_title_trgm_idx ON planportal.project USING gin (title gin_trgm_ops);

-- ── layers ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.project_layer (
    project_slug      TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    layer_id          TEXT,
    name              TEXT NOT NULL,
    layer_type        TEXT NOT NULL,
    geom_type         TEXT,
    datasource        TEXT,
    crs               TEXT,
    wms_visible       BOOLEAN NOT NULL DEFAULT TRUE,
    vector_eligible   BOOLEAN NOT NULL DEFAULT FALSE,
    pmtiles_url       TEXT,
    style_url         TEXT,
    PRIMARY KEY (project_slug, layer_id)
);

-- ── map themes (QGIS <visibility-presets>) ──────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.project_theme (
    project_slug    TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    name            TEXT,
    visible_layers  JSONB NOT NULL,
    PRIMARY KEY (project_slug, name)
);

-- ── print layouts ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.project_layout (
    project_slug    TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    name            TEXT,
    paper_size      TEXT,
    orientation     TEXT,
    PRIMARY KEY (project_slug, name)
);

-- ── authentik group → project role ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.user_group (
    authentik_group TEXT NOT NULL,
    project_slug    TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('viewer','editor','admin')),
    PRIMARY KEY (authentik_group, project_slug)
);

-- ── feature comments (per geometry feature) ─────────────────────────────
-- Bridges Planportal to the bimavo CDE later (see ADR-0006).
CREATE TABLE IF NOT EXISTS planportal.feature_comment (
    id              BIGSERIAL PRIMARY KEY,
    project_slug    TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    layer_id        TEXT NOT NULL,
    feature_id      TEXT NOT NULL,
    geom            GEOMETRY(GEOMETRY, 25832),
    author          TEXT NOT NULL,
    body            TEXT NOT NULL,
    parent_id       BIGINT REFERENCES planportal.feature_comment(id) ON DELETE CASCADE,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feature_comment_loc_idx
    ON planportal.feature_comment (project_slug, layer_id, feature_id);
CREATE INDEX IF NOT EXISTS feature_comment_geom_idx
    ON planportal.feature_comment USING gist (geom);

-- ── share links ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.share_link (
    token         TEXT PRIMARY KEY,
    project_slug  TEXT REFERENCES planportal.project(slug) ON DELETE CASCADE,
    permalink     JSONB NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── indexer event log ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS planportal.indexer_event (
    id            BIGSERIAL PRIMARY KEY,
    project_slug  TEXT,
    kind          TEXT NOT NULL,
    payload       JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
