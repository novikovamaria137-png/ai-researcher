"""Free-tier and local LLM backends, all spoken to over plain HTTP.

Every backend here is usable at zero cost:

  * ``ollama``     — a model running locally (llama3.2, qwen2.5, mistral…).
                     No key, no account, no network.
  * ``groq``       — Groq free tier, key from console.groq.com (free signup).
  * ``gemini``     — Google AI Studio free tier, key from aistudio.google.com.
  * ``openrouter`` — OpenRouter's ``:free`` model slugs.

They share one OpenAI-compatible-ish shape, so the differences are kept to a
small per-provider adapter instead of four SDK dependencies.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

import httpx

from .base import Entry, Summarizer, SummarizerError

DEFAULT_TIMEOUT = 90.0


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - network path
        body = exc.response.text[:300]
        raise SummarizerError(f"{url} -> HTTP {exc.response.status_code}: {body}") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network path
        raise SummarizerError(f"{url} unreachable: {exc}") from exc


class OllamaSummarizer(Summarizer):
    """Local model via the Ollama daemon. Free and fully offline."""

    name = "ollama"
    requires_key = False

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def available(self) -> bool:
        try:
            response = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        payload = {
            "model": self.model,
            "prompt": self.build_prompt(competitor, entries),
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 600},
        }
        data = _post_json(f"{self.host}/api/generate", payload, {})
        return str(data.get("response", "")).strip()


class _OpenAIChatCompatible(Summarizer):
    """Shared implementation for the /chat/completions providers."""

    endpoint: str = ""
    env_key: str = ""
    default_model: str = ""
    env_model: str = ""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get(self.env_key, "")
        self.model = model or os.environ.get(self.env_model, self.default_model)

    def available(self) -> bool:
        return bool(self.api_key)

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        if not self.api_key:
            raise SummarizerError(f"{self.env_key} is not set")
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 600,
            "messages": [{"role": "user", "content": self.build_prompt(competitor, entries)}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = _post_json(self.endpoint, payload, headers)
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise SummarizerError(f"unexpected response shape: {str(data)[:200]}") from exc


class GroqSummarizer(_OpenAIChatCompatible):
    """Groq free tier — fast, generous daily limits, no card required."""

    name = "groq"
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    env_key = "GROQ_API_KEY"
    env_model = "GROQ_MODEL"
    default_model = "llama-3.3-70b-versatile"


class OpenRouterSummarizer(_OpenAIChatCompatible):
    """OpenRouter, pinned to a ``:free`` model slug by default."""

    name = "openrouter"
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    env_key = "OPENROUTER_API_KEY"
    env_model = "OPENROUTER_MODEL"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"


class GeminiSummarizer(Summarizer):
    """Google AI Studio free tier (different request shape, so its own class)."""

    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    def available(self) -> bool:
        return bool(self.api_key)

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        if not self.api_key:
            raise SummarizerError("GEMINI_API_KEY is not set")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {"parts": [{"text": self.build_prompt(competitor, entries)}]}
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        data = _post_json(url, payload, {"x-goog-api-key": self.api_key})
        try:
            return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise SummarizerError(f"unexpected response shape: {str(data)[:200]}") from exc


class AnthropicSummarizer(Summarizer):
    """Optional paid backend, kept for parity — never selected automatically."""

    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def available(self) -> bool:
        return bool(self.api_key)

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        if not self.api_key:
            raise SummarizerError("ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": 600,
            "messages": [{"role": "user", "content": self.build_prompt(competitor, entries)}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = _post_json("https://api.anthropic.com/v1/messages", payload, headers)
        try:
            return str(data["content"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise SummarizerError(f"unexpected response shape: {str(data)[:200]}") from exc
