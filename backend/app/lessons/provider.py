"""LLM provider interface.

Callers go through get_provider() so a different backend (Bedrock, OpenAI)
can be dropped in by adding a class and a registry entry.
"""

import os
import time
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from app.config import LESSON_MAX_TOKENS, LLM_MODEL, LLM_PROVIDER

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

TIMEOUT_SECONDS = 20.0
RETRIES = 2
# gpt-oss reasons before answering and the reasoning shares the token budget.
# At the default effort it spends all of LESSON_MAX_TOKENS thinking and returns
# empty content; "low" leaves room for the actual lesson.
REASONING_EFFORT = "low"


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
                    reasoning_effort=REASONING_EFFORT,
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


PROVIDERS: dict[str, type[LessonProvider]] = {"groq": GroqProvider}


def get_provider(name: str = LLM_PROVIDER) -> LessonProvider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise LessonProviderError(f"unknown LLM provider {name!r}") from None
