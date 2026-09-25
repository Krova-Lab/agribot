"""Load private or community-safe prompt configuration.

The private prompt file is intentionally ignored by Git. A clone of the public
repository transparently uses the anonymised example configuration instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(__file__).resolve().parent
PRIVATE_PROMPTS_PATH = CONFIG_DIR / "prompts.json"
EXAMPLE_PROMPTS_PATH = CONFIG_DIR / "prompts.example.json"
REQUIRED_PROMPT_KEYS = {
    "system_prompt", "persona", "attached_media", "fallback_rag_context",
    "audio_instructions", "api_rag_prompt", "workflow_prompt",
    "document_audit_prompt", "diagnostic_prompt",
}


MINIMAL_PROMPTS: dict[str, Any] = {
    "system_prompt": (
        "You are an agricultural assistant. Use the provided context to answer "
        "carefully and state when information is unavailable."
    ),
    "response_style": "Answer briefly and practically. Do not list sources unless the user explicitly asks for them. A request for more detail means a fuller explanation, not a source list.",
    "attached_media": {
        "none": "None",
        "image": "YES, image attached. Analyze only visible evidence.",
        "audio": "YES, audio attached. Transcribe only clearly audible human speech.",
    },
    "fallback_rag_context": "No verified knowledge-base context is available.",
    "audio_instructions": "Do not invent content when the audio is silent, unclear, or non-human.",
    "api_rag_prompt": "Answer the user question in {language} using only this verified context:\n{context_text}\n\nQuestion: {question}",
    "workflow_prompt": "Analyze the agricultural problem using the supplied context and return structured JSON.\nContext: {context_str}\nFarmer message: {user_text}",
    "document_audit_prompt": "Analyze this technical document excerpt and return valid JSON with content_year, detected_source, trust_score, status, and reason.\nFilename: {filename}\nExcerpt:\n{text_sample}",
    "diagnostic_prompt": "Analyze the farmer's agricultural issue using the supplied context and return a cautious, structured recommendation.\nContext: {rag_context}\nFarmer message: {user_query}",
}


def _read_prompt_file(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as prompt_file:
            data = json.load(prompt_file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not REQUIRED_PROMPT_KEYS.issubset(data):
        return None
    if not isinstance(data["attached_media"], dict):
        return None
    return data


def load_prompts() -> dict[str, Any]:
    """Load private prompts, then the public example, then a safe minimal set."""

    return (
        _read_prompt_file(PRIVATE_PROMPTS_PATH)
        or _read_prompt_file(EXAMPLE_PROMPTS_PATH)
        or dict(MINIMAL_PROMPTS)
    )


def render_prompt(template: str, **values: object) -> str:
    """Replace named template placeholders without interpreting prompt braces."""

    rendered = template
    for name, value in values.items():
        rendered = rendered.replace("{" + name + "}", str(value))
    return rendered
