"""Turn incoming media into text before retrieval and response generation."""

from __future__ import annotations

from dataclasses import dataclass

from llm_adapter import ask_llm


@dataclass(frozen=True)
class PreparedInput:
    user_text: str
    retrieval_query: str
    media_observation: str
    interpretation_model: str | None


class InputInterpretationError(RuntimeError):
    """Raised when a media input cannot be interpreted reliably."""


def prepare_input(user_text: str, media_bytes: bytes | None, mime_type: str) -> PreparedInput:
    user_text = user_text.strip()
    if not media_bytes:
        return PreparedInput(user_text, user_text, "None", None)

    if mime_type.startswith("audio/"):
        transcript, model = ask_llm(
            "Transcribe this voice message verbatim in its original language. "
            "Preserve Khmer script, crop names, place names and any location the speaker states. "
            "Do not translate, answer the question, or invent inaudible words. "
            "If there is no intelligible speech, return exactly [NO_SPEECH]. "
            "Otherwise return only the transcript.",
            media_bytes=media_bytes,
            mime_type=mime_type,
            task="transcription",
            temperature=0,
        )
        if not transcript or transcript.strip() == "[NO_SPEECH]":
            raise InputInterpretationError("Voice transcription failed")
        text = " ".join(part for part in (user_text, transcript) if part)
        return PreparedInput(text, text, f"Voice transcript: {transcript}", model)

    if mime_type.startswith("image/"):
        observation, model = ask_llm(
            "Describe only agricultural evidence visible in this image: crop, affected parts, "
            "symptoms, and any legible text. Transcribe legible place names exactly. "
            "Do not diagnose a disease or infer a location from scenery. "
            "State uncertainty when the crop or text is unclear. Keep it concise.",
            media_bytes=media_bytes,
            mime_type=mime_type,
            task="vision",
            temperature=0,
        )
        if not observation:
            raise InputInterpretationError("Image interpretation failed")
        query = " ".join(part for part in (user_text, observation) if part)
        return PreparedInput(user_text, query, observation, model)

    raise InputInterpretationError("Unsupported media type")
