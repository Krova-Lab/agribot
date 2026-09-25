-- Add the vector index required for predictable retrieval as the verified
-- corpus grows. This migration does not modify existing vectors or content.
-- Gemini embeddings are 3072-dimensional; pgvector vector indexes support at
-- most 2000 dimensions. Index a half-precision expression instead. This keeps
-- the stored vectors untouched while allowing HNSW retrieval up to 4000 dims.
CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
    ON public.rag_documents USING hnsw
    ((embedding::halfvec(3072)) halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
    ON public.knowledge_base USING hnsw
    ((embedding::halfvec(3072)) halfvec_cosine_ops);
