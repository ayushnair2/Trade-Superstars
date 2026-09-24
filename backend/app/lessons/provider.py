"""LLM provider interface.

Callers go through get_provider() so a different backend (Bedrock, OpenAI)
can be dropped in by adding a class and a registry entry.
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from app.config import LESSON_MAX_TOKENS, LLM_MODEL, LLM_PROVIDER

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

TIMEOUT_SECONDS = 20.0
RETRIES = 2
# Reasoning models spend the token budget thinking before they answer, which
# starves a cap this small. Set this only when LLM_MODEL is such a model.
REASONING_EFFORT: str | None = None


logger = logging.getLogger(__name__)


class LessonProviderError(RuntimeError):
    pass


class LessonProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's reply as plain text."""
        raise NotImplementedError


class GroqProvider(LessonProvider):
    def __init__(self, model: str = LLM_MODEL):
        from groq import Groq

        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise LessonProviderError("GROQ_API_KEY is not set")
        self.model = model
        self.client = Groq(api_key=key, timeout=TIMEOUT_SECONDS)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        last_error = None
        for attempt in range(RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_completion_tokens=LESSON_MAX_TOKENS,
                    temperature=0.7,
                    **(
                        {"reasoning_effort": REASONING_EFFORT}
                        if REASONING_EFFORT
                        else {}
                    ),
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    return text
                last_error = "model returned empty content"
            except Exception as exc:
                last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(1)
        raise LessonProviderError(f"{self.model} failed: {last_error}")


    def available_models(self) -> list[str]:
        return [m.id for m in self.client.models.list().data]


PROVIDERS: dict[str, type[LessonProvider]] = {"groq": GroqProvider}


def check_model() -> bool:
    """Warn loudly at startup if the configured model no longer exists.

    Never raises: a retired model degrades lessons to their fallback text, and
    that is not worth refusing to serve the market over. It is logged at ERROR
    because it is silent otherwise -- the last retirement was only noticed when
    someone read a 502.
    """
    try:
        provider = get_provider()
        models = provider.available_models()
    except Exception as exc:
        logger.error("could not check LLM model %r: %s", LLM_MODEL, exc)
        return False

    if LLM_MODEL in models:
        logger.info("LLM model %r is available", LLM_MODEL)
        return True
    logger.error(
        "LLM model %r is NOT in the provider's list -- lessons will serve "
        "fallback text. Available: %s",
        LLM_MODEL,
        ", ".join(sorted(models)),
    )
    return False


def get_provider(name: str = LLM_PROVIDER) -> LessonProvider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise LessonProviderError(f"unknown LLM provider {name!r}") from None
