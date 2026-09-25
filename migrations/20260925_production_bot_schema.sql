-- Apply this file only to the dedicated PROD_DB_NAME database.
-- It intentionally has no relationship with the pilot bot schema.
BEGIN;

CREATE TABLE IF NOT EXISTS public.prod_bot_users (
    telegram_id bigint PRIMARY KEY,
    username varchar(100),
    first_name varchar(255),
    status varchar(20) NOT NULL DEFAULT 'waitlist',
    preferred_language varchar(5) NOT NULL DEFAULT 'km',
    location_text varchar(255),
    location_lat numeric(9, 6),
    location_lon numeric(9, 6),
    onboarding_step varchar(32) NOT NULL DEFAULT 'complete',
    referral_code varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT prod_bot_users_status_check CHECK (status IN ('waitlist', 'active', 'paused', 'blocked')),
    CONSTRAINT prod_bot_users_language_check CHECK (preferred_language IN ('km', 'en', 'fr')),
    CONSTRAINT prod_bot_users_step_check CHECK (onboarding_step IN ('complete', 'awaiting_language', 'awaiting_location'))
);

CREATE INDEX IF NOT EXISTS idx_prod_bot_users_status
    ON public.prod_bot_users (status, created_at);

CREATE TABLE IF NOT EXISTS public.prod_bot_settings (
    key varchar(50) PRIMARY KEY,
    value varchar(255) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.prod_bot_settings (key, value)
VALUES
    ('access_mode', 'waitlist'),
    ('default_country', 'Cambodia'),
    ('daily_quota', '30')
ON CONFLICT (key) DO NOTHING;

COMMIT;
