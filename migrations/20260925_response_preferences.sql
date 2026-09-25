-- Store only an inferred response-style preference, never a hidden user profile dump.
BEGIN;

CREATE TABLE IF NOT EXISTS public.user_preferences (
    telegram_id bigint NOT NULL,
    preference_key character varying(64) NOT NULL,
    preference_value character varying(64) NOT NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 0,
    evidence_count integer NOT NULL DEFAULT 0,
    sample_count integer NOT NULL DEFAULT 0,
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (telegram_id, preference_key)
);

ALTER TABLE public.interactions
    ADD COLUMN IF NOT EXISTS requested_detail boolean NOT NULL DEFAULT false;

COMMIT;
