-- Add the vector index required for predictable retrieval as the verified
-- corpus grows. This migration does not modify existing vectors or content.
-- Gemini embeddings are 3072-dimensional; pgvector HNSW indexes support at
-- most 2000 dimensions, so use IVFFlat for this existing vector size.
CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
    ON public.rag_documents USING ivfflat (embedding public.vector_cosine_ops)
    WITH (lists = 100);
