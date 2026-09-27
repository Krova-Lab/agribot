-- Build the RAG and review tables for the dedicated production database.
-- This deliberately excludes the pilot-only legacy knowledge_base corpus.
BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS public.rag_documents (
    id bigserial PRIMARY KEY,
    source_title text,
    category text,
    content text NOT NULL,
    embedding public.vector(3072) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    file_sha256 varchar(64),
    content_sha256 varchar(64),
    trust_score real NOT NULL DEFAULT 0.7,
    content_year smallint,
    detected_source varchar(100),
    audit_status varchar(20) NOT NULL DEFAULT 'pending',
    source_url text,
    source_publisher text,
    source_publication_date date,
    source_license text,
    source_locator text,
    provenance_status varchar(20) NOT NULL DEFAULT 'unverified'
);

CREATE TABLE IF NOT EXISTS public.interactions (
    id bigserial PRIMARY KEY,
    telegram_id bigint NOT NULL,
    role varchar(30) NOT NULL DEFAULT 'prospect',
    created_at timestamptz NOT NULL DEFAULT now(),
    latitude numeric(9,6),
    longitude numeric(9,6),
    province varchar(100),
    has_text boolean NOT NULL DEFAULT false,
    has_photo boolean NOT NULL DEFAULT false,
    has_audio boolean NOT NULL DEFAULT false,
    has_video boolean NOT NULL DEFAULT false,
    raw_user_text text,
    media_file_id varchar(255),
    media_file_size_bytes integer,
    detected_language varchar(10),
    open_meteo_ms integer,
    soilgrids_ms integer,
    plantnet_ms integer,
    rag_ms integer,
    web_ms integer,
    llm_ms integer,
    total_ms integer,
    soil_source varchar(50),
    soil_quality_flag varchar(20),
    rag_sources_count integer NOT NULL DEFAULT 0,
    rag_top_distance numeric(5,4),
    model_used varchar(100),
    tokens_prompt integer,
    tokens_completion integer,
    estimated_cost_usd numeric(8,6),
    confidence_score integer,
    diagnosis_title text,
    diagnosis_json jsonb,
    rating_thumb integer,
    feedback_category varchar(50),
    feedback_text text,
    evidence_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_detail boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS public.user_preferences (
    telegram_id bigint NOT NULL,
    preference_key varchar(64) NOT NULL,
    preference_value varchar(64) NOT NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 0,
    evidence_count integer NOT NULL DEFAULT 0,
    sample_count integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (telegram_id, preference_key)
);

CREATE TABLE IF NOT EXISTS public.diagnostic_reviews (
    id bigserial PRIMARY KEY,
    interaction_id bigint,
    reviewer_telegram_id bigint,
    reviewer_name varchar(100),
    status varchar(50) NOT NULL DEFAULT 'pending',
    corrected_diagnosis text,
    agronomist_notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT production_unique_interaction_review UNIQUE (interaction_id),
    CONSTRAINT production_review_interaction_fk
        FOREIGN KEY (interaction_id) REFERENCES public.interactions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prod_rag_docs_file_sha
    ON public.rag_documents (file_sha256);
CREATE INDEX IF NOT EXISTS idx_prod_rag_docs_content_sha
    ON public.rag_documents (content_sha256);
CREATE INDEX IF NOT EXISTS idx_prod_rag_docs_verified_source
    ON public.rag_documents (audit_status, provenance_status)
    WHERE audit_status = 'approved' AND provenance_status = 'verified';
CREATE INDEX IF NOT EXISTS idx_prod_interactions_telegram_id
    ON public.interactions (telegram_id);
CREATE INDEX IF NOT EXISTS idx_prod_interactions_created_at
    ON public.interactions (created_at);
CREATE INDEX IF NOT EXISTS idx_prod_reviews_interaction_id
    ON public.diagnostic_reviews (interaction_id);
CREATE INDEX IF NOT EXISTS prod_rag_documents_embedding_idx
    ON public.rag_documents USING hnsw
    ((embedding::public.halfvec(3072)) public.halfvec_cosine_ops);

COMMIT;
