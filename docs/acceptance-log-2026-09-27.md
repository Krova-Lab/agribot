# Development acceptance log — 2026-09-27

This log records the qualitative checks completed on the development pilot after
the RAG confidence gate was enabled. It is not a production sign-off.

## RAG checks

The checks were run against `krova_dev` with the current `RAG_MAX_DISTANCE=0.32`
default:

| Query class | Expected result | Observed result |
| --- | --- | --- |
| Cambodia rice and pond management | Relevant WorldFish evidence | Relevant WorldFish evidence returned |
| Rice-field pond management in Prey Veng | Relevant local evidence | Relevant WorldFish evidence returned |
| Cassava soil preparation in Cambodia | No matching approved source in the fixture | No RAG source returned |
| Unrelated cryptocurrency question | No agricultural source | No RAG source returned |

The gate removed the earlier false-positive retrievals for cassava and the
unrelated control query. The current fixture is intentionally small; the
threshold must be re-evaluated after more approved crops, regions, and source
types are ingested.

The same checks are reproducible with `python bin/evaluate_rag.py`. The current
approved fixture returns two ranked passages from one canonical WorldFish URL;
the evaluator records both passage count and unique-source count so this does
not get mistaken for two independent sources.

## Telegram checks

The development bot was tested through the authorized Telegram test account:

- A text question without a precise location received a Cambodia-oriented answer
  without blocking on location. The answer stated that province, crop stage,
  soil, and irrigation context would improve precision.
- A follow-up request for sources did not invent citations. The bot stated that
  no official database record or live Web source had been retrieved for that
  answer and recommended local extension confirmation for plot-level advice.
- A text question with an explicit location (`Prey Veng, Cambodia`) used that
  location in the answer, provided a Cambodia-relevant baseline, and asked for
  the rice growth stage before offering more tailored guidance.
- A Khmer `.wav` audio file sent as a Telegram document was accepted after the
  audio-attachment handler was deployed. The bot downloaded and transcribed
  the file, then returned a Khmer response instead of silently ignoring the
  document. This validates the common-audio-file path; a native Telegram voice
  note still needs a separate live check.
- A Khmer `.ogg` audio file sent through Telegram's audio upload flow was then
  accepted after generic Telegram MIME values were normalized. The service
  called Telegram `getFile`, downloaded the file, ran the transcription route,
  and returned a Khmer answer. This confirms the audio-object path as well as
  the document path.
- A native Telegram voice note was accepted by the deployed service. The bot
  downloaded the `.ogg` voice payload, transcribed it, and returned a response.
- A fresh photo-only Telegram message was accepted after the media-routing
  fix. The service saved the image, ran the vision route, sent the final
  response, and did not enter the audio-transcription path.
- A controlled response failover test made an unavailable Azure deployment
  fail first; Gemini then returned the response and telemetry recorded
  `fallback_used=true` with both attempts.
- A controlled all-provider failure test made both configured response routes
  fail. The adapter returned no answer, recorded both failed attempts and
  preserved the fail-closed path used by the Telegram handler.

The read-only retention report also ran against the live development database;
it completed without deleting or anonymising any interaction.

The persistent limiter was exercised with ten concurrent requests for a
temporary user identifier. Five requests were admitted and five were rejected
by the minute limit; the temporary row was then removed.

A separate two-process check confirmed that a request admitted by one process
was rejected by the next process because the minute-limit state persisted in
PostgreSQL. Invalid image bytes are rejected before external processing.

The response remained readable on a phone and ended with an invitation for a
more tailored follow-up. The response was in English because the test request
was in English.

## Remaining release checks

The full Telegram matrix is still open for a complete
provider-outage simulation through the Telegram UI. The adapter-level outage
check is green. Photo handling, native voice-note, common audio-file handling,
explicit location, no-location, source-request, and controlled model-failover
cases passed this acceptance pass. The unit/integration suite and the live
pilot smoke checks are green, but the production gate also requires a broader
labelled retrieval set and a frozen migration sequence.
