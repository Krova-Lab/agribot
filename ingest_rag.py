"""Retired legacy seeder kept only to explain its replacement.

The old script truncated ``rag_documents`` and inserted three unsourced
summaries labelled CARDI/MAFF. It must not be used for a production corpus.
Use ``ingest_files.py`` with reviewed, traceable documents instead.
"""


def ingest() -> None:
    raise RuntimeError(
        "Legacy unsourced RAG seeding is disabled. "
        "Review source documents and use ingest_files.py instead."
    )


if __name__ == "__main__":
    ingest()
