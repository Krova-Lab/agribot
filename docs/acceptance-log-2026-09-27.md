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

## Telegram checks

The development bot was tested through the authorized Telegram test account:

- A text question without a precise location received a Cambodia-oriented answer
  without blocking on location. The answer stated that province, crop stage,
  soil, and irrigation context would improve precision.
- A follow-up request for sources did not invent citations. The bot stated that
  no official database record or live Web source had been retrieved for that
  answer and recommended local extension confirmation for plot-level advice.

The response remained readable on a phone and ended with an invitation for a
more tailored follow-up. The response was in English because the test request
was in English.

## Remaining release checks

The full Telegram matrix is still open for explicit location, photo, voice,
fallback, and provider-outage cases. The unit/integration suite and the live
pilot smoke checks are green, but the production gate also requires a broader
labelled retrieval set and a frozen migration sequence.
