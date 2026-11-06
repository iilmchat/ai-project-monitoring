"""Local OpenAI-compatible LLM integration (S32-001).

Only commit-message generation lives here for now. Network failures are
swallowed and reported as ``None`` so the API can return a domain error instead
of a 500.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)

COMMIT_SYSTEM_PROMPT = (
    "Ты — senior разработчик. Напиши commit message в формате Conventional "
    "Commits (feat/fix/docs/refactor). Опиши изменения кратко и по делу. "
    "Ответь только текстом коммита, без кавычек."
)
MAX_MESSAGE_CHARS = 2000


class LLMService:
    """Generate commit messages through a local OpenAI-compatible endpoint."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._settings.llm_enabled)

    @property
    def model(self) -> str:
        return self._settings.llm_model

    @property
    def provider(self) -> str:
        parsed = urlparse(self._settings.llm_base_url)
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port == 11434 or "ollama" in host:
            return "ollama"
        if port == 1234 or "lmstudio" in host:
            return "lmstudio"
        return "openai_compatible"

    @property
    def base_url(self) -> str:
        return self._settings.llm_base_url.strip().rstrip("/")

    def remote_allowed(self) -> bool:
        """Whether a non-loopback endpoint is explicitly permitted."""
        if self._settings.llm_allow_remote:
            return True
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "localhost.localdomain"}:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    async def generate_commit_message(self, diff: str) -> str | None:
        """Return a generated commit message, or ``None`` on any failure."""
        if not self.enabled or not diff.strip() or not self.remote_allowed():
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": COMMIT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Diff:\n{diff}",
                },
            ],
            "temperature": 0.2,
            "max_tokens": 512,
            "stream": False,
        }
        headers = {"Accept": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.llm_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._endpoint(),
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException:
            logger.warning(
                "llm_request_failed",
                provider=self.provider,
                reason="timeout",
            )
            return None
        except httpx.HTTPError:
            logger.warning(
                "llm_request_failed",
                provider=self.provider,
                reason="http_error",
            )
            return None

        if response.status_code != 200:
            logger.warning(
                "llm_request_failed",
                provider=self.provider,
                status_code=response.status_code,
            )
            return None

        try:
            body = response.json()
        except ValueError:
            logger.warning(
                "llm_request_failed",
                provider=self.provider,
                reason="invalid_json",
            )
            return None

        message = _extract_message(body)
        if message is None:
            return None
        return message[:MAX_MESSAGE_CHARS]

    def _endpoint(self) -> str:
        base = self.base_url
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


def _extract_message(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    content = (
        message.get("content")
        if isinstance(message, dict)
        else first.get("text")
    )
    if not isinstance(content, str):
        return None
    cleaned = _clean_message(content)
    return cleaned or None


def _clean_message(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text.strip().strip('"').strip("'").strip()


__all__ = ["COMMIT_SYSTEM_PROMPT", "MAX_MESSAGE_CHARS", "LLMService"]
