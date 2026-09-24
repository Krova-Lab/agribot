-- Apply once before deploying the provenance-aware RAG code.
-- Existing documents are preserved, but stay out of retrieval until a human
-- has verified a concrete source URL and explicitly approved them.
BEGIN;

ALTER TABLE public.rag_documents
    ADD COLUMN IF NOT EXISTS source_url text,
    ADD COLUMN IF NOT EXISTS source_publisher text,
    ADD COLUMN IF NOT EXISTS source_publication_date date,
    ADD COLUMN IF NOT EXISTS source_license text,
    ADD COLUMN IF NOT EXISTS source_locator text,
    ADD COLUMN IF NOT EXISTS provenance_status character varying(20) NOT NULL DEFAULT 'unverified';

ALTER TABLE public.rag_documents
    ALTER COLUMN audit_status SET DEFAULT 'pending';

UPDATE public.rag_documents
SET audit_status = 'pending', provenance_status = 'unverified'
WHERE NULLIF(BTRIM(source_url), '') IS NULL
   OR provenance_status <> 'verified';

ALTER TABLE public.knowledge_base
    ADD COLUMN IF NOT EXISTS file_sha256 character varying(64),
    ADD COLUMN IF NOT EXISTS content_sha256 character varying(64),
    ADD COLUMN IF NOT EXISTS source_url text,
    ADD COLUMN IF NOT EXISTS source_publisher text,
    ADD COLUMN IF NOT EXISTS source_publication_date date,
    ADD COLUMN IF NOT EXISTS source_license text,
    ADD COLUMN IF NOT EXISTS source_locator text,
    ADD COLUMN IF NOT EXISTS provenance_status character varying(20) NOT NULL DEFAULT 'unverified',
    ADD COLUMN IF NOT EXISTS audit_status character varying(20) NOT NULL DEFAULT 'pending';

UPDATE public.knowledge_base
SET audit_status = 'pending', provenance_status = 'unverified'
WHERE NULLIF(BTRIM(source_url), '') IS NULL
   OR provenance_status <> 'verified';

ALTER TABLE public.interactions
    ADD COLUMN IF NOT EXISTS web_ms integer,
    ADD COLUMN IF NOT EXISTS evidence_trace jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_rag_docs_verified_source
    ON public.rag_documents (audit_status, provenance_status)
    WHERE audit_status = 'approved' AND provenance_status = 'verified';
CREATE INDEX IF NOT EXISTS idx_knowledge_base_verified_source
    ON public.knowledge_base (audit_status, provenance_status)
    WHERE audit_status = 'approved' AND provenance_status = 'verified';

COMMIT;
