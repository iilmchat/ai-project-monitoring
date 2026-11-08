"""Local OpenAI-compatible LLM integration (S32-001).

Only commit-message generation lives here for now. Network failures are
swallowed and reported as ``None`` so the API can return a domain error instead
of a 500.
"""

from __future__ import annotations

import ipaddress
import time
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
SECURITY_SYSTEM_PROMPT = (
    "Ты - эксперт по безопасности. Отвечай кратко и только по фактам описания."
)
UNIFICATION_SYSTEM_PROMPT = (
    "Ты - senior инженер. Давай практичные советы по унификации версий "
    "зависимостей. Не выдумывай факты, опирайся только на переданные версии."
)
DEVOPS_SYSTEM_PROMPT = (
    "Ты - DevOps-ассистент. Давай короткие приоритизированные рекомендации "
    "по состоянию локальных репозиториев. Не выдумывай факты."
)
AGENT_TASK_SYSTEM_PROMPT = (
    "Ты - Senior-разработчик. Пиши чёткие пошаговые инструкции для другого "
    "AI-агента. Не выполняй действия сам, только составь задачу."
)
MAX_MESSAGE_CHARS = 2000
MAX_EXPLANATION_CHARS = 2000


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
        if not diff.strip():
            return None
        return await self._complete(
            COMMIT_SYSTEM_PROMPT,
            f"Diff:\n{diff}",
            max_tokens=512,
            max_chars=MAX_MESSAGE_CHARS,
        )

    async def explain_cve(self, cve_id: str, summary: str) -> str | None:
        """Return a short, developer-friendly CVE explanation."""
        cve = cve_id.strip()
        description = summary.strip()
        if not cve or not description:
            return None
        prompt = (
            "Ты — эксперт по безопасности. Объясни разработчику простым языком, "
            f"в чем опасность уязвимости {cve} (описание: {description}). "
            "Как её исправить? Ответь кратко, 2-3 предложения."
        )
        return await self._complete(
            SECURITY_SYSTEM_PROMPT,
            prompt,
            max_tokens=256,
            max_chars=MAX_EXPLANATION_CHARS,
        )

    async def advise_unification(
        self,
        package: str,
        versions: dict[str, list[str]],
    ) -> str | None:
        """Return a short advice on which version to standardise on."""
        name = package.strip()
        if not name or not versions:
            return None
        lines = []
        for version, projects in sorted(versions.items()):
            projects_text = ", ".join(projects[:8]) if projects else "—"
            lines.append(f"{version}: {projects_text}")
        prompt = (
            f"В проектах используются разные версии пакета {name}:\n"
            + "\n".join(lines)
            + "\n\nНапиши краткий совет (1-2 предложения), на какую версию "
            "лучше унифицироваться и почему."
        )
        return await self._complete(
            UNIFICATION_SYSTEM_PROMPT,
            prompt,
            max_tokens=256,
            max_chars=MAX_EXPLANATION_CHARS,
        )

    async def generate_dashboard_advice(
        self,
        stats: dict[str, int],
        *,
        language: str = "ru",
    ) -> str | None:
        """Return 2-3 prioritized recommendations for the dashboard."""
        stats_text = ", ".join(f"{key}={value}" for key, value in sorted(stats.items()))
        prompt = (
            f"Состояние проектов: {stats_text}. "
            "Дай 2-3 краткие рекомендации, с чего начать работу сегодня. "
            + _language_instruction(language)
        )
        return await self._complete(
            DEVOPS_SYSTEM_PROMPT,
            prompt,
            max_tokens=320,
            max_chars=MAX_EXPLANATION_CHARS,
        )

    async def generate_agent_task(
        self,
        context: dict[str, object],
        *,
        language: str = "ru",
    ) -> str | None:
        """Return a Markdown task for DSH/OpenCode."""
        lines = [
            f"Репозиторий: {context.get('repository', '—')}",
            f"Состояние: {context.get('state', 'unknown')}",
            f"Ветка: {context.get('branch', '—')}",
            f"Ahead/Behind: {context.get('ahead', 0)}/{context.get('behind', 0)}",
            f"Изменено/в индексе/untracked: {context.get('dirty', '0/0/0')}",
        ]
        conflicts = context.get("conflicts")
        if isinstance(conflicts, list) and conflicts:
            lines.append("Конфликтные файлы: " + ", ".join(str(item) for item in conflicts))
        commits = context.get("commits")
        if isinstance(commits, list) and commits:
            lines.append("Последние коммиты:")
            lines.extend(f"- {item}" for item in commits)
        prompt = (
            "Напиши чёткую пошаговую инструкцию (Markdown) для другого "
            "AI-агента (DSH/OpenCode), как исправить текущую проблему в этом "
            "репозитории. Не выполняй команды, только составь задачу с "
            "acceptance criteria и списком проверок.\n\n"
            + "\n".join(lines)
            + "\n"
            + _language_instruction(language)
        )
        return await self._complete(
            AGENT_TASK_SYSTEM_PROMPT,
            prompt,
            max_tokens=700,
            max_chars=MAX_EXPLANATION_CHARS,
        )

    async def test_connection(self) -> tuple[bool, float, str | None]:
        """Ping the configured model and return ``(ok, latency_ms, error)``."""
        if not self.enabled:
            return False, 0.0, "llm_disabled"
        if not self.remote_allowed():
            return False, 0.0, "llm_remote_not_allowed"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        }
        headers = {"Accept": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=min(self._settings.llm_timeout_seconds, 15.0),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._endpoint(),
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException:
            return False, _elapsed_ms(started), "timeout"
        except httpx.HTTPError:
            return False, _elapsed_ms(started), "connection_error"

        latency = _elapsed_ms(started)
        if response.status_code != 200:
            return False, latency, f"http_{response.status_code}"
        try:
            body = response.json()
        except ValueError:
            return False, latency, "invalid_json"
        if _extract_message(body) is None:
            return False, latency, "invalid_response"
        return True, latency, None

    async def _complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        max_chars: int,
    ) -> str | None:
        if not self.enabled or not self.remote_allowed():
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
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
        return message[:max_chars]

    def _endpoint(self) -> str:
        base = self.base_url
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


def _language_instruction(language: str) -> str:
    return "Answer in English." if language == "en" else "Отвечай на русском."


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


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


__all__ = [
    "AGENT_TASK_SYSTEM_PROMPT",
    "COMMIT_SYSTEM_PROMPT",
    "DEVOPS_SYSTEM_PROMPT",
    "MAX_EXPLANATION_CHARS",
    "MAX_MESSAGE_CHARS",
    "SECURITY_SYSTEM_PROMPT",
    "UNIFICATION_SYSTEM_PROMPT",
    "LLMService",
]
