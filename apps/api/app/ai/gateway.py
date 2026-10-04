"""The single door to every AI model. Handlers call `gateway.run(task, ...)`; they never import
a provider or hold a prompt string. Routing rules live here and nowhere else:

* each task type maps to a provider through configuration (switching = changing env);
* `sensitive` calls may only reach a local provider, otherwise SensitiveRoutingError;
* prompts are versioned PromptTemplate rows.
"""

import json
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import PROVIDER_CLASSES, Provider, ProviderError
from app.config import Settings, get_settings
from app.enums import Sensitivity
from app.models import PromptTemplate

# task name -> which configured provider slot serves it
TASK_SLOT = {
    "signal_analysis": "classify",
    "content_generation": "generate",
}


class SensitiveRoutingError(RuntimeError):
    """A sensitive request was about to leave the organisation boundary."""


class PromptNotFound(RuntimeError):
    pass


@dataclass
class AIResult:
    text: str
    provider: str
    template_version: int


def extract_json(text: str) -> dict:
    """Models wrap JSON in prose or code fences; pull out the first JSON object."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


class AIGateway:
    def __init__(
        self, settings: Settings | None = None, providers: dict[str, Provider] | None = None
    ):
        self.settings = settings or get_settings()
        self._providers = providers

    def provider_named(self, name: str) -> Provider:
        if self._providers is not None:
            try:
                return self._providers[name]
            except KeyError as e:
                raise ProviderError(f"unknown provider {name!r}") from e
        try:
            return PROVIDER_CLASSES[name](self.settings)
        except KeyError as e:
            raise ProviderError(f"unknown provider {name!r}") from e

    def resolve_provider(self, task: str, sensitivity: Sensitivity) -> Provider:
        if sensitivity == Sensitivity.SENSITIVE:
            provider = self.provider_named(self.settings.ai_provider_sensitive)
            if not provider.is_local:
                raise SensitiveRoutingError(
                    f"sensitive request refused: provider {provider.name!r} is not local"
                )
            return provider
        slot = TASK_SLOT[task]
        return self.provider_named(getattr(self.settings, f"ai_provider_{slot}"))

    @staticmethod
    def load_template(db: Session, name: str) -> PromptTemplate:
        tpl = db.scalar(
            select(PromptTemplate)
            .where(PromptTemplate.name == name, PromptTemplate.active.is_(True))
            .order_by(PromptTemplate.version.desc())
        )
        if not tpl:
            raise PromptNotFound(name)
        return tpl

    def run(
        self,
        db: Session,
        task: str,
        variables: dict[str, str],
        *,
        sensitivity: Sensitivity = Sensitivity.NORMAL,
        max_tokens: int = 2000,
    ) -> AIResult:
        provider = self.resolve_provider(task, sensitivity)  # routing check precedes everything
        tpl = self.load_template(db, task)
        user = tpl.user_template
        for key, value in variables.items():
            user = user.replace("{{" + key + "}}", value)
        text = provider.complete(
            tpl.system_text, user, model=tpl.default_model, max_tokens=max_tokens
        )
        return AIResult(text=text, provider=provider.name, template_version=tpl.version)


_gateway: AIGateway | None = None


def get_gateway() -> AIGateway:
    global _gateway
    if _gateway is None:
        _gateway = AIGateway()
    return _gateway
