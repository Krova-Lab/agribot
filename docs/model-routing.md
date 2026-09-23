# Task-specific model routing

The production bot keeps Gemini as its primary provider while Azure Foundry is introduced and measured. This is an availability improvement, not a claim that either provider is more accurate in Khmer. The Azure `gpt-4o` deployment has passed a minimal live text request; it has not yet passed a labeled agricultural quality benchmark.

## Runtime flow

1. Text is used directly. A voice message is transcribed in its original language. A photo is described as uncertain visible evidence, including legible place names but without guessing a location.
2. The resulting text is sent to the existing Gemini embedding and pgvector retrieval path. A photo caption remains the user's own text; the image observation is retrieval context, not a confirmed diagnosis.
3. The response model receives the retrieved sources, user text, interpreted media, and the existing safety instructions.
4. Each task tries its configured models in order. A timeout, API error, or empty response triggers the next model. No user content or credentials are written to inference logs.

The fallback is bounded to the listed routes. An unavailable Azure model or key cannot prevent the existing Gemini route from running first. If media interpretation fails on every configured model, the bot returns its technical-error message instead of inventing an answer without seeing the media.

## Configuration

`KROVA_RESPONSE_MODELS`, `KROVA_VISION_MODELS`, and `KROVA_TRANSCRIPTION_MODELS` are comma-separated `provider:deployment` lists. Supported providers are `gemini` and `azure`; Azure Foundry can host deployments from multiple model families without a new adapter for each family.

```dotenv
KROVA_RESPONSE_MODELS=gemini:gemini-3.6-flash,azure:gpt-4o
KROVA_VISION_MODELS=gemini:gemini-3.6-flash,azure:gpt-4o
KROVA_TRANSCRIPTION_MODELS=gemini:gemini-3.6-flash
```

`AZURE_FOUNDRY_BASE_URL` must end in `/openai/v1`; `AZURE_FOUNDRY_API_KEY` is required for Azure routes. The bot reads process variables, then its repository `.env`, then an optional `AZURE_FOUNDRY_ENV_FILE` or the `.env` next to its Python virtual environment. Never commit credentials. Azure route names must be actual deployment names. GPT-4o chat does **not** transcribe voice; an audio transcription deployment is separate.

To try an Azure-first response on a pilot instance, set `KROVA_RESPONSE_MODELS=azure:gpt-4o,gemini:gemini-3.6-flash`. Do not change the production default based only on a connectivity test.

## Evaluation before changing defaults

Create a private JSONL case file outside Git. Each line needs `id`, `task` (`response`, `vision`, or `transcription`), and `prompt`; media cases additionally need an absolute `media_path` and `mime_type`. Example:

```json
{"id":"rice-fr-01","task":"response","prompt":"A Cambodian farmer asks in French about yellow rice leaves. Explain what to check before recommending any treatment."}
```

Run `python bin/evaluate_models.py /path/to/private-cases.jsonl --output runtime/model-eval.jsonl`. The output is ignored by Git. The script calls each configured model independently and records model, latency, success, and answer for blind human review. It does **not** auto-score agronomic correctness.

Include at least a small set of labeled Khmer text and voice questions, Khmer place names, French and English controls, crop photos, uncertain/poor-quality photos, greetings, and unsafe pesticide requests. A Khmer-speaking reviewer and an agronomist should score transcription accuracy, crop/symptom fidelity, groundedness in the supplied source, uncertainty, safety, language, latency, and cost. Compare retrieval separately: changing the response model does not repair bad corpus ranking. Avoid sending real user data to a new provider without appropriate consent and data-policy review.

Candidate next comparison: the existing Gemini transcription route versus a separately deployed Azure `gpt-transcribe` (or another Khmer-capable speech model). Azure GPT-4o is an available vision/response challenger, not a presumed winner. Keep `models/gemini-embedding-001` for the existing vector index; switching embeddings requires a full re-embedding and retrieval evaluation.

Specialized [Gemini 3.5 Transcribe](https://ai.google.dev/gemini-api/docs/transcribe) is another Khmer speech candidate, but it uses Google's Interactions API rather than this adapter's `generate_content` path. It must not be selected in `KROVA_TRANSCRIPTION_MODELS` until that transport is implemented and tested. Azure's [v1 transcription endpoint](https://learn.microsoft.com/en-us/azure/foundry/openai/reference-preview-latest) is already supported by this adapter for a separately deployed transcription model; Telegram OGG is converted to WAV for that route.
