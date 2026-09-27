-- Persist short-window request limits so a process restart cannot reset them.
BEGIN;

CREATE TABLE IF NOT EXISTS public.request_rate_limits (
    telegram_id bigint PRIMARY KEY,
    window_started_at timestamptz NOT NULL DEFAULT now(),
    window_count integer NOT NULL DEFAULT 0,
    quota_date date NOT NULL DEFAULT CURRENT_DATE,
    daily_count integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_request_rate_limits_updated_at
    ON public.request_rate_limits (updated_at);

COMMIT;
