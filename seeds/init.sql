-- CIS AgentOps — Local Database Schema
-- Runs automatically on first postgres container start

CREATE TABLE IF NOT EXISTS published_tours (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tour_name        VARCHAR(200) NOT NULL,
    destination      VARCHAR(100) NOT NULL,
    title            TEXT,
    tagline          TEXT,
    description      TEXT,
    highlights       TEXT,
    seo_meta_title   VARCHAR(60),
    seo_meta_description VARCHAR(155),
    quality_score    FLOAT DEFAULT 0,
    model_used       VARCHAR(50),
    cost_usd         FLOAT DEFAULT 0,
    is_active        BOOLEAN DEFAULT true,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tour_name, destination)
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       VARCHAR(50) UNIQUE NOT NULL,
    run_at       TIMESTAMPTZ DEFAULT now(),
    dataset_size INT,
    success_rate FLOAT,
    judge_avg    FLOAT,
    pipeline_avg FLOAT,
    total_cost   FLOAT,
    result_json  JSONB
);

CREATE TABLE IF NOT EXISTS pipeline_traces (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id     VARCHAR(100),
    tour_name    VARCHAR(200),
    stage        VARCHAR(50),
    elapsed_ms   FLOAT,
    cost_usd     FLOAT,
    model_used   VARCHAR(50),
    success      BOOLEAN,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tours_active ON published_tours(is_active, destination);
CREATE INDEX IF NOT EXISTS idx_traces_tour ON pipeline_traces(tour_name);
