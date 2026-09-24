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
The source reference is also included in the Telegram reply.

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

## Database deployment

Back up the database, then apply
`migrations/20260924_rag_provenance_and_trace.sql` **before** deploying the new
bot code. The migration is additive and keeps all old rows, but makes old rows
without reviewed source metadata unavailable to retrieval. Do not deploy the
code first: it expects the migration's provenance and interaction-trace fields.
