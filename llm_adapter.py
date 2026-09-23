"""Task-specific model routing with bounded, cross-provider failover."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv
from google import genai
from google.genai import types

from config.database import PROJECT_ROOT


logger = logging.getLogger(__name__)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
load_dotenv(PROJECT_ROOT / ".env")
# Read only the two Azure values from the shared runtime file; do not import
# unrelated service credentials into the bot process.
azure_env_file = Path(os.getenv("AZURE_FOUNDRY_ENV_FILE") or Path(sys.prefix).parent / ".env")
if azure_env_file.is_file():
    shared_values = dotenv_values(azure_env_file)
    for name in ("AZURE_FOUNDRY_BASE_URL", "AZURE_FOUNDRY_API_KEY"):
        if shared_values.get(name) and not os.getenv(name):
            os.environ[name] = shared_values[name]

DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_ROUTES = {
    "response": "gemini:gemini-3.6-flash,azure:gpt-4o",
    "vision": "gemini:gemini-3.6-flash,azure:gpt-4o",
    "transcription": "gemini:gemini-3.6-flash",
}


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def configured_routes(task: str) -> list[ModelRoute]:
    """Read an ordered, de-duplicated route list for one inference task."""
    if task not in DEFAULT_ROUTES:
        raise ValueError(f"Unknown inference task: {task}")
    raw = os.getenv(f"KROVA_{task.upper()}_MODELS", DEFAULT_ROUTES[task])
    routes = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        provider, separator, model = item.partition(":")
        if not separator or provider not in {"gemini", "azure"} or not model.strip():
            raise ValueError(f"Invalid model route for {task}: {item}")
        route = ModelRoute(provider, model.strip())
        if route not in routes:
            routes.append(route)
    if not routes:
        raise ValueError(f"No models configured for {task}")
    return routes


@lru_cache(maxsize=2)
def _gemini_client(key: str) -> genai.Client:
    """Keep the SDK client alive while requests are in flight."""
    return genai.Client(api_key=key)


def _gemini_generate(route: ModelRoute, prompt: str, payload: bytes | None, mime_type: str, temperature: float) -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Gemini credentials are missing")
    contents = []
    if payload:
        contents.append(types.Part.from_bytes(data=payload, mime_type=mime_type))
    contents.append(prompt)
    response = _gemini_client(key).models.generate_content(
        model=route.model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=temperature,
            tool_config={"function_calling_config": {"mode": "NONE"}},
        ),
    )
    return response.text or ""


def _azure_generate(route: ModelRoute, prompt: str, payload: bytes | None, mime_type: str, temperature: float, task: str) -> str:
    base_url = os.getenv("AZURE_FOUNDRY_BASE_URL", "").rstrip("/")
    key = os.getenv("AZURE_FOUNDRY_API_KEY")
    if not base_url or not key:
        raise RuntimeError("Azure Foundry credentials are missing")
    if not base_url.startswith("https://") or not base_url.endswith("/openai/v1"):
        raise ValueError("AZURE_FOUNDRY_BASE_URL must be an HTTPS /openai/v1 endpoint")
    headers = {"api-key": key}
    if task == "transcription":
        if not payload or not mime_type.startswith("audio/"):
            raise ValueError("Azure transcription requires audio input")
        if mime_type == "audio/ogg":
            converted = subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "ogg", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
                input=payload,
                capture_output=True,
                timeout=20,
                check=True,
            )
            payload, mime_type = converted.stdout, "audio/wav"
        if len(payload) > 25 * 1024 * 1024:
            raise ValueError("Audio exceeds the transcription upload limit")
        suffix = ".wav" if mime_type == "audio/wav" else ".mp3"
        response = requests.post(
            f"{base_url}/audio/transcriptions",
            headers=headers,
            data={"model": route.model},
            files={"file": (f"voice{suffix}", payload, mime_type)},
            timeout=45,
        )
        response.raise_for_status()
        return response.json().get("text", "")
    if payload:
        if task != "vision" or not mime_type.startswith("image/"):
            raise ValueError("Azure chat route supports only image input for vision")
        encoded = base64.b64encode(payload).decode("ascii")
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
        ]
    else:
        content = prompt
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={**headers, "Content-Type": "application/json"},
        json={"model": route.model, "messages": [{"role": "user", "content": content}], "temperature": temperature},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"].get("content") or ""


def ask_llm(
    prompt: str,
    image_bytes: bytes | None = None,
    media_bytes: bytes | None = None,
    mime_type: str = "image/jpeg",
    model_name: str | None = None,
    temperature: float = 0.2,
    task: str = "response",
) -> tuple[str | None, str]:
    """Try configured models in order; never log user content or credentials."""
    payload = media_bytes if media_bytes is not None else image_bytes
    routes = configured_routes(task)
    if model_name:
        provider, separator, model = model_name.partition(":")
        routes = [ModelRoute(provider, model)] if separator else [ModelRoute("gemini", model_name)]
    attempted = "none"
    for route in routes:
        attempted = route.label
        started = time.monotonic()
        try:
            if route.provider == "gemini":
                answer = _gemini_generate(route, prompt, payload, mime_type, temperature)
            elif route.provider == "azure":
                answer = _azure_generate(route, prompt, payload, mime_type, temperature, task)
            else:
                raise ValueError(f"Unsupported provider: {route.provider}")
            if not answer.strip():
                raise ValueError("Empty model output")
            logger.info("Inference task=%s model=%s duration_ms=%d", task, route.label, int((time.monotonic() - started) * 1000))
            return answer.strip(), route.label
        except Exception as exc:
            logger.warning("Inference failed task=%s model=%s error=%s", task, route.label, type(exc).__name__)
    return None, attempted


if __name__ == "__main__":
    result, model_used = ask_llm("Reply with OK only.")
    print(f"Model: {model_used}\nResponse: {result}")
