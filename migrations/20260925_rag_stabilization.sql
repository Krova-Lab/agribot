-- Add the vector index required for predictable retrieval as the verified
-- corpus grows. This migration does not modify existing vectors or content.
CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
    ON public.rag_documents USING hnsw (embedding public.vector_cosine_ops);
