# RAG provenance and grounded Web research

## Ingest a document

Place the document in `rag_dropzone/`. Add a sidecar with the same basename and
the `.source.json` extension (for example, `rice-guide.pdf` and
`rice-guide.source.json`):

```json
{
  "source_title": "Water management in rice production",
  "source_url": "https://example.org/rice-water-management",
  "publisher": "Example agricultural institute",
  "publication_date": "2025-03-01",
  "license": "CC BY 4.0",
  "page_or_section": "Water management, p. 12"
}
```

Use the publication's own page or document URL, not a search result page or a
filename. Record only fields that can be checked. If the original source cannot
be identified, omit the URL; the document will be ingested as pending and will
not appear in bot retrieval. Text inside OCR or a document that merely claims
“CARDI”, “MAFF”, or another institution is not proof of origin.

Ingestion does not approve a source. A reviewer must open the URL, confirm that
it resolves to the cited document, check that the publisher/title/date match,
review the relevant passage and licensing, then explicitly promote the matching
chunks:

```sql
UPDATE rag_documents
SET provenance_status = 'verified', audit_status = 'approved'
WHERE file_sha256 = '<reviewed-file-sha256>'
  AND source_url = '<verified-canonical-url>';
```

Keep the review record with the ingestion/audit process. Do not run an update
based only on a model-generated title or OCR text. The migration deliberately
quarantines existing rows whose provenance has not been verified; it does not
delete or rewrite their content. Review existing corpus rows before approving
them again.

## What the bot retrieves and records

RAG retrieval is limited to rows with `audit_status = 'approved'`,
`provenance_status = 'verified'`, and a non-empty `source_url`. Each retrieved
chunk carries its database ID, corpus, content hash, source title, URL, publisher,
publication date, licence, and vector distance into the interaction audit trace.
Source references are available in the Telegram reply when the user explicitly
asks for sources or more detail. PDF extraction keeps
page boundaries and records the one-based PDF page (or page range) for each chunk;
an optional sidecar locator such as a chapter or printed page range is retained
alongside it. For non-paginated sources, supply the best verifiable section in the
sidecar rather than relying on the document title alone.

For substantive agriculture questions, the bot separately calls Gemini with
Google Search grounding enabled, even when Azure is configured as the response
model. It records whether grounding occurred, the search queries, model, source
titles/URLs, and provider error type. Web citations are shown only when grounding
metadata actually contains sources. A failed or empty search must never be
described as a successful online verification. `KROVA_WEB_RESEARCH_ENABLED=false`
turns this feature off; it is enabled by default. Web grounding can add latency
and provider usage/cost.

Retrieved passages and web page contents are untrusted evidence, not bot
instructions. The response must distinguish verified evidence from provisional
guidance and must not stretch a source beyond the claims its passage supports.
The bot compares exact passages and web-grounded claims, preserves quoted values,
and must not silently combine conflicting numbers or recommendations. When
credible sources disagree and no source clearly applies better, it should state
the conflict and uncertainty rather than give a falsely precise answer.

Publication date is part of evidence assessment, not only citation metadata. Older
documents may remain useful for stable agronomic methods, definitions, or historical
context, but they are not automatically current. The bot must apply additional
caution to time-sensitive claims such as climate and weather conditions, pollution,
pest and disease pressure, regulations, product registrations and approvals, prices,
and public-health guidance. For these claims it should seek recent or current
confirmation, and disclose when the available source is old or undated. An old
source is not discarded automatically: its relevance depends on the claim being
made and on whether a newer source or grounded Web result supersedes it.

## Database deployment

Back up the database, then apply
`migrations/20260924_rag_provenance_and_trace.sql` and then
`migrations/20260925_rag_stabilization.sql` **before** deploying the new bot
code. The first migration is additive and keeps all old rows, but makes old
rows without reviewed source metadata unavailable to retrieval. The second
adds HNSW indexes over half-precision expressions for both vector corpora so
retrieval remains predictable as the verified corpus grows. This representation
is intentional because the existing Gemini embedding size is 3072 dimensions,
above the standard vector index limit. The stored vectors are not rewritten.
Do not deploy the code first: it expects the migration's provenance and
interaction-trace fields.
