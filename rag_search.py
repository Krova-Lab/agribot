"""Auditable retrieval over provenance-verified agricultural documents."""

from __future__ import annotations

import os
import hashlib
from dataclasses import asdict, dataclass

import psycopg2
from dotenv import load_dotenv
from google import genai

from config.database import PROJECT_ROOT, get_db_params

load_dotenv(PROJECT_ROOT / ".env")
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
DB_PARAMS = get_db_params()


@dataclass(frozen=True)
class RetrievedSource:
    corpus: str
    document_id: int
    title: str
    content: str
    url: str
    publisher: str | None
    publication_date: str | None
    license: str | None
    content_sha256: str | None
    distance: float

    def trace(self, rank: int) -> dict:
        """Return identifiers and provenance, not the full document text."""
        item = asdict(self)
        item.pop("content")
        item["rank"] = rank
        return item


@dataclass(frozen=True)
class RagRetrieval:
    status: str
    sources: tuple[RetrievedSource, ...] = ()
    error_type: str | None = None

    def trace(self) -> dict:
        return {
            "status": self.status,
            "error_type": self.error_type,
            "sources": [source.trace(rank) for rank, source in enumerate(self.sources, 1)],
        }


def retrieve_rag(query: str, limit: int = 3, *, raise_on_error: bool = False) -> RagRetrieval:
    """Retrieve only approved passages with an explicitly verified source URL."""
    if not query or query == "[Photo sent]":
        return RagRetrieval("skipped")
    conn = None
    cur = None
    try:
        res = client.models.embed_content(model="models/gemini-embedding-001", contents=query)
        query_vector = res.embeddings[0].values
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute(
            """
            WITH candidates AS (
                SELECT 'rag_documents'::text AS corpus, id, source_title, content,
                       source_url, source_publisher, source_publication_date,
                       source_license, content_sha256, embedding
                FROM rag_documents
                WHERE embedding IS NOT NULL
                  AND audit_status = 'approved'
                  AND provenance_status = 'verified'
                  AND NULLIF(BTRIM(source_url), '') IS NOT NULL
                UNION ALL
                SELECT 'knowledge_base'::text AS corpus, id, source_title, content,
                       source_url, source_publisher, source_publication_date,
                       source_license, content_sha256, embedding
                FROM knowledge_base AS kb
                WHERE embedding IS NOT NULL
                  AND audit_status = 'approved'
                  AND provenance_status = 'verified'
                  AND NULLIF(BTRIM(source_url), '') IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM rag_documents AS rd
                      WHERE rd.file_sha256 = kb.file_sha256
                  )
            )
            SELECT corpus, id, source_title, content, source_url,
                   source_publisher, source_publication_date, source_license,
                   content_sha256, embedding <=> %s::vector AS distance
            FROM candidates
            ORDER BY distance ASC
            LIMIT %s;
            """,
            (query_vector, limit),
        )
        rows = cur.fetchall()
        sources = tuple(
            RetrievedSource(
                corpus=row[0],
                document_id=row[1],
                title=row[2] or "Untitled source",
                content=row[3] or "",
                url=row[4],
                publisher=row[5],
                publication_date=row[6].isoformat() if row[6] else None,
                license=row[7],
                content_sha256=row[8] or hashlib.sha256((row[3] or "").encode("utf-8")).hexdigest(),
                distance=float(row[9]),
            )
            for row in rows
        )
        return RagRetrieval("ok" if sources else "no_sources", sources)
    except Exception as exc:
        print(f"[RAG SEARCH ERROR] {type(exc).__name__}: {exc}")
        if raise_on_error:
            raise
        return RagRetrieval("failed", error_type=type(exc).__name__)
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def format_rag_context(sources: list[RetrievedSource]) -> str:
    """Format retrieved evidence with explicit, machine-verified provenance."""
    return "\n\n".join(
        f"[RAG SOURCE {rank}] {source.title}\n"
        f"Publisher: {source.publisher or 'Not recorded'}\n"
        f"Published: {source.publication_date or 'Not recorded'}\n"
        f"URL: {source.url}\n"
        f"Passage: {source.content}"
        for rank, source in enumerate(sources, 1)
    )


def search_rag(query: str, limit: int = 3, *, raise_on_error: bool = False) -> str:
    """Backward-compatible text interface for callers that do not need a trace."""
    return format_rag_context(retrieve_rag(query, limit, raise_on_error=raise_on_error).sources)


if __name__ == "__main__":
    test_q = "ឫសស្អុយចំបើងរលួយ"
    print("Vector search test for:", test_q)
    print(search_rag(test_q))
