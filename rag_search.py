"""Auditable retrieval over provenance-verified agricultural documents."""

from __future__ import annotations

import os
import hashlib
import time
from dataclasses import asdict, dataclass

import psycopg2
from dotenv import load_dotenv
from google import genai

from config.database import PROJECT_ROOT, get_db_params

load_dotenv(PROJECT_ROOT / ".env")
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
DB_PARAMS = get_db_params()
DEFAULT_MAX_DISTANCE = float(os.getenv("RAG_MAX_DISTANCE", "0.32"))


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
    source_locator: str | None
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
    metrics: dict | None = None

    def trace(self) -> dict:
        return {
            "status": self.status,
            "error_type": self.error_type,
            "metrics": self.metrics or {},
            "sources": [source.trace(rank) for rank, source in enumerate(self.sources, 1)],
        }


def retrieve_rag(
    query: str,
    limit: int = 3,
    *,
    raise_on_error: bool = False,
    telemetry: dict | None = None,
) -> RagRetrieval:
    """Retrieve only approved passages with an explicitly verified source URL."""
    if not query or query == "[Photo sent]":
        return RagRetrieval("skipped")
    conn = None
    cur = None
    try:
        max_distance = DEFAULT_MAX_DISTANCE
        if not 0 < max_distance <= 2:
            raise ValueError("RAG_MAX_DISTANCE must be greater than 0 and no more than 2")
        embedding_start = time.monotonic()
        res = client.models.embed_content(model="models/gemini-embedding-001", contents=query)
        embedding_ms = int((time.monotonic() - embedding_start) * 1000)
        query_vector = res.embeddings[0].values
        if telemetry is not None:
            telemetry["embedding_ms"] = embedding_ms
            telemetry["embedding_model"] = "gemini-embedding-001"
        search_start = time.monotonic()
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        # The pilot database keeps a legacy corpus; the clean production database does not.
        cur.execute("SELECT to_regclass('public.knowledge_base')")
        legacy_corpus_exists = cur.fetchone()[0] is not None
        legacy_union = """
                UNION ALL
                SELECT 'knowledge_base'::text AS corpus, id, source_title, content,
                       source_url, source_publisher, source_publication_date,
                       source_license, source_locator, content_sha256, embedding
                FROM knowledge_base AS kb
                WHERE embedding IS NOT NULL
                  AND audit_status = 'approved'
                  AND provenance_status = 'verified'
                  AND NULLIF(BTRIM(source_url), '') IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM rag_documents AS rd
                      WHERE rd.file_sha256 = kb.file_sha256
                  )
        """ if legacy_corpus_exists else ""
        cur.execute(
            f"""
            WITH candidates AS (
                SELECT 'rag_documents'::text AS corpus, id, source_title, content,
                       source_url, source_publisher, source_publication_date,
                       source_license, source_locator, content_sha256, embedding
                FROM rag_documents
                WHERE embedding IS NOT NULL
                  AND audit_status = 'approved'
                  AND provenance_status = 'verified'
                  AND NULLIF(BTRIM(source_url), '') IS NOT NULL
                {legacy_union}
            ),
            scored AS (
                SELECT corpus, id, source_title, content, source_url,
                       source_publisher, source_publication_date, source_license,
                       source_locator, content_sha256,
                       embedding::halfvec(3072) <=> %s::halfvec(3072) AS distance
                FROM candidates
            ),
            diversified AS (
                SELECT scored.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY source_url
                           ORDER BY distance ASC, id ASC
                       ) AS source_rank
                FROM scored
            )
            SELECT corpus, id, source_title, content, source_url,
                   source_publisher, source_publication_date, source_license,
                   source_locator, content_sha256, distance
            FROM diversified
            WHERE source_rank <= 2
              AND distance <= %s
            ORDER BY distance ASC, id ASC
            LIMIT %s;
            """,
            (query_vector, max_distance, limit),
        )
        rows = cur.fetchall()
        query_ms = int((time.monotonic() - search_start) * 1000)
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
                source_locator=row[8],
                content_sha256=row[9] or hashlib.sha256((row[3] or "").encode("utf-8")).hexdigest(),
                distance=float(row[10]),
            )
            for row in rows
        )
        metrics = {
            "embedding_ms": embedding_ms,
            "query_ms": query_ms,
            "source_count": len(sources),
            "max_distance": max_distance,
        }
        if sources:
            metrics["top_distance"] = sources[0].distance
        if telemetry is not None:
            telemetry.update(metrics)
        return RagRetrieval("ok" if sources else "no_sources", sources, metrics=metrics)
    except Exception as exc:
        print(f"[RAG SEARCH ERROR] {type(exc).__name__}: {exc}")
        if raise_on_error:
            raise
        if telemetry is not None:
            telemetry["error_type"] = type(exc).__name__
        return RagRetrieval("failed", error_type=type(exc).__name__, metrics=telemetry or {})
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def format_rag_context(sources: list[RetrievedSource]) -> str:
    """Format retrieved evidence with explicit provenance and ranking context."""
    return "\n\n".join(
        f"[RAG SOURCE {rank}] {source.title}\n"
        f"Publisher: {source.publisher or 'Not recorded'}\n"
        f"Published: {source.publication_date or 'Not recorded'}\n"
        f"Page/section: {source.source_locator or 'Not recorded'}\n"
        f"Cosine distance (lower is closer): {source.distance:.4f}\n"
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
