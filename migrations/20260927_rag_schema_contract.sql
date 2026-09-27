-- Fail fast if a database does not use the embedding dimension required by the
-- active Gemini embedding model and the provenance-aware retrieval indexes.
DO $$
DECLARE
    knowledge_base_embedding_type text;
    rag_documents_embedding_type text;
    knowledge_base_exists boolean;
BEGIN
    SELECT to_regclass('public.knowledge_base') IS NOT NULL
    INTO knowledge_base_exists;

    SELECT format_type(a.atttypid, a.atttypmod)
    INTO knowledge_base_embedding_type
    FROM pg_class AS c
    JOIN pg_attribute AS a ON a.attrelid = c.oid
    WHERE c.relname = 'knowledge_base'
      AND a.attname = 'embedding'
      AND a.attnum > 0;

    SELECT format_type(a.atttypid, a.atttypmod)
    INTO rag_documents_embedding_type
    FROM pg_class AS c
    JOIN pg_attribute AS a ON a.attrelid = c.oid
    WHERE c.relname = 'rag_documents'
      AND a.attname = 'embedding'
      AND a.attnum > 0;

    IF rag_documents_embedding_type <> 'vector(3072)'
       OR (knowledge_base_exists AND knowledge_base_embedding_type <> 'vector(3072)') THEN
        RAISE EXCEPTION
            'RAG schema contract requires vector(3072): knowledge_base=%, rag_documents=%',
            knowledge_base_embedding_type,
            rag_documents_embedding_type;
    END IF;
END
$$;
