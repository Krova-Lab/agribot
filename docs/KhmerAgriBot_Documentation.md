# Krova Agri — Technical and Operational Documentation

**Document version:** 1.0.0-PROD
**Target infrastructure:** Debian/Ubuntu VM with a dedicated service user
**Primary interface:** Telegram
**Reference repository:** `Krova-Lab/agribot`

---

## 1. Vision and operating context

Krova Agri is a resilient, auditable, multilingual agricultural assistant
for Cambodian smallholders and agricultural extension workers. It is designed
for practical use through Telegram, including low-bandwidth text, voice notes,
and crop photographs.

The knowledge workflow can incorporate official and technical sources from
CARDI, MAFF, IRRI, CIAT, and other approved repositories. The assistant is
designed to distinguish verified context from uncertainty and to avoid making
unsupported chemical or protocol recommendations.

## 2. System architecture

```text
Farmer / extension worker
          |
          v
Telegram bot gateway
  text | voice | photo
          |
          +--> language and access control
          +--> soil, weather, and location context
          +--> Pl@ntNet photo identification
          +--> local RAG retrieval
                         |
                         v
              PostgreSQL + pgvector
                         |
                         v
             Context-aware prompt assembly
                         |
                         v
                 Task-specific model adapter
                         |
                         v
             Khmer / French / English reply
                         |
                         v
              telemetry and moderation API
```

## 3. Software components

| Component | Technology | Responsibility |
| --- | --- | --- |
| Telegram gateway | `python-telegram-bot` | Text, voice, photo, language routing, feedback, and access control |
| Inference adapter | `llm_adapter.py` | Task-specific generation with bounded provider fallback |
| Embeddings | `gemini-embedding-001` | Semantic vectors for retrieval |
| Vector database | PostgreSQL 16 + `pgvector` | RAG documents, interaction audit, and telemetry |
| Document extraction | `pypdf`, `python-docx`, OCR tools | Convert approved source files to searchable text |
| Ingestion pipeline | `ingest_files.py`, `ingest_daemon.py` | Validation, chunking, embedding, and database insertion |
| Moderation API | FastAPI | Review, correction, telemetry, and controlled RAG promotion |

## 4. Database model

The database name and credentials are supplied through the central environment
configuration. The `vector` extension must be enabled before ingestion.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The main tables are:

- `interactions` — user input metadata, response timing, model, confidence,
  location, and feedback.
- `rag_documents` — newly ingested documents with source title, category,
  content, embedding vector, and review status.
- `knowledge_base` — historical vectorized chunks retained from the earlier
  ingestion pipeline.
- user and moderation tables — access control, review status, and operational
  feedback.

The running bot retrieves context from both tables through `rag_search.py`,
without re-embedding the historical corpus. The historical `agri_hf_` batch
is temporarily excluded from retrieval because spot checks found unrelated
content; the records remain in the database for review. New entries are
retrieved only when approved. Embeddings are generated with
`models/gemini-embedding-001`.

## 5. Secure ingestion workflow

```text
Approved source
      |
      v
rag_dropzone/
      |
      v
Format extraction and sanitisation
      |
      v
Length, encoding, topic, and prompt-injection checks
      |
      v
Chunking and embedding
      |
      v
PostgreSQL / pgvector
```

Operational directories:

- `rag_dropzone/` — documents awaiting validation.
- `rag_processed/` — accepted and ingested documents.
- `rag_rejected/` — documents rejected by validation rules.
- `rag_failed/` — documents that could not be processed.

These directories contain local operational data and are excluded from Git.

## 6. Runtime operations

```bash
# Check the Telegram service (use the service name configured by the deployment)
sudo systemctl status khmeragribot.service

# Follow live logs
journalctl -u khmeragribot.service -f

# Restart after a code or configuration change
sudo systemctl restart khmeragribot.service

# Ingest approved documents
python3 ingest_files.py
```

The development stack can start PostgreSQL with:

```bash
docker compose up -d postgres
```

## 7. Configuration and intellectual-property boundaries

- API keys, database credentials, Telegram tokens, user data, media, dumps,
  logs, and RAG corpora remain outside version control.
- `config/prompts.json` contains private production instructions and is ignored
  by Git.
- `config/prompts.example.json` contains a community-safe structure and generic
  instructions.
- A public clone falls back automatically to the example prompt configuration.
- The public mirror excludes private prompt documents and operational datasets.

## 8. Current status and next steps

The Telegram pilot, multimodal input flow, local RAG, soil and weather context,
moderation API, and partial prompt separation are implemented. The future public
bot currently provides isolated wait-list onboarding only; it is not yet the
production assistant. Current work focuses on field evaluation, Khmer
terminology quality, retrieval evaluation, source provenance, observability,
and release automation.
