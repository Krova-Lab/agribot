# Agricultural Corpus Ingestion and Validation Pipeline

This module automates selective collection, cleaning, and qualitative
validation of agronomic corpora before they enter the production `rag_dropzone/`.

## Flow architecture

1. **Harvest (`harvest.py`)**
   - Download target pages and PDF documents from a whitelist of technical
     sources such as IRRI, MAFF, and CIAT.
   - Extract text with `trafilatura` for HTML and `pypdf` for PDF files.
   - Reject raw content shorter than 250 characters.
   - Store an intermediate `cleaned/<id>.json` record with a SHA-256 hash.

2. **Validation, normalisation, and export (`validate.py`)**
   - Inspect extracted data from `cleaned/`.
   - Normalise repeated line breaks and remove unnecessary whitespace.
   - Enforce a minimum length above 300 characters and targeted agronomic
     keywords.
   - Move rejected JSON files to `rejected/`.
   - Export approved content as a `.txt` file with YAML metadata into
     `../rag_dropzone/` (`agri_<id>.txt`), then remove the intermediate JSON.

## Output format (`rag_dropzone/agri_<hash>.txt`)

```text
---
source: <SOURCE_URL>
id: <SHA256_HASH>
---

Compacted, cleaned, and normalised text
```
