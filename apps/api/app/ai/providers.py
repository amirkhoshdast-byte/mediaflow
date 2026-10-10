"""Provider interface and implementations. Providers know nothing about prompts or routing."""

from abc import ABC, abstractmethod

import httpx

from app.config import Settings


class ProviderError(RuntimeError):
    pass


class Provider(ABC):
    name: str
    is_local: bool

    @abstractmethod
    def complete(self, system: str, user: str, *, model: str | None, max_tokens: int) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderError(f"{self.name} has no embeddings API")


class AnthropicProvider(Provider):
    name = "anthropic"
    is_local = False

    def __init__(self, s: Settings):
        self.api_key, self.model, self.timeout = (
            s.anthropic_api_key,
            s.anthropic_model,
            s.ai_timeout_seconds,
        )

    def complete(self, system, user, *, model, max_tokens):
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured")
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        msg = client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


class OpenAICompatibleProvider(Provider):
    name = "openai_compatible"
    is_local = False  # may point anywhere; never trusted for sensitive data

    def __init__(self, s: Settings):
        self.base, self.key, self.model = (
            s.openai_compat_base_url.rstrip("/"),
            s.openai_compat_api_key,
            s.openai_compat_model,
        )
        self.timeout = s.ai_timeout_seconds
        self.embed_model = s.openai_compat_embed_model

    def embed(self, texts):
        if not self.base:
            raise ProviderError("OPENAI_COMPAT_BASE_URL is not configured")
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        r = httpx.post(
            f"{self.base}/embeddings",
            headers=headers,
            timeout=self.timeout,
            json={"model": self.embed_model, "input": texts},
        )
        if r.status_code >= 400:
            raise ProviderError(f"openai_compatible HTTP {r.status_code}")
        rows = sorted(r.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in rows]

    def complete(self, system, user, *, model, max_tokens):
        if not self.base:
            raise ProviderError("OPENAI_COMPAT_BASE_URL is not configured")
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        r = httpx.post(
            f"{self.base}/chat/completions",
            headers=headers,
            timeout=self.timeout,
            json={
                "model": model or self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        if r.status_code >= 400:
            raise ProviderError(f"openai_compatible HTTP {r.status_code}")
        return r.json()["choices"][0]["message"]["content"]


class OllamaProvider(Provider):
    name = "ollama"
    is_local = True

    def __init__(self, s: Settings):
        self.base, self.model, self.timeout = (
            s.ollama_base_url.rstrip("/"),
            s.ollama_model,
            s.ai_timeout_seconds,
        )
        self.embed_model = s.ollama_embed_model

    def embed(self, texts):
        try:
            r = httpx.post(
                f"{self.base}/api/embed",
                timeout=self.timeout,
                json={"model": self.embed_model, "input": texts},
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"ollama unreachable: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            raise ProviderError(f"ollama HTTP {r.status_code}")
        return r.json()["embeddings"]

    def complete(self, system, user, *, model, max_tokens):
        try:
            r = httpx.post(
                f"{self.base}/api/chat",
                timeout=self.timeout,
                json={
                    "model": model or self.model,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"ollama unreachable: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            raise ProviderError(f"ollama HTTP {r.status_code}")
        return r.json()["message"]["content"]


PROVIDER_CLASSES: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "ollama": OllamaProvider,
}
