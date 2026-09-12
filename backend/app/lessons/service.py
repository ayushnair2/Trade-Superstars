"""Generate (and cache) a one-off lesson for a trade."""

from sqlalchemy import select

import re

from app.lessons.concepts import (
    GLOBAL_CONCEPTS,
    Concept,
    cache_key,
    pick_concept,
)
from app.lessons.provider import get_provider
from app.models import Athlete, Lesson, Side, Trade

SYSTEM_PROMPT = """You write one-line tips for a beginner in a sports-trading game.

Hard rules:
- ONE sentence, 20 words maximum. Two only if genuinely needed, never over 25 words.
- Punchy and concrete, like a game tip. Never open with "X means", "This refers to",
  or any definition-style throat-clearing. Never name the concept itself.
- Describe what the player just did and why it matters. Write about the move that
  already happened, never about what to do next.
- Never command the user. No "buy", "sell", "wait", "avoid", "add", "cash out",
  "spread your bets" or any other instruction aimed at them.
- Never predict a price, never state dollar amounts or percentages, never invent stats.
- Plain language. Name the athlete where it reads naturally -- but ONLY when the
  prompt gives you one. If no player is named, the tip is about the portfolio as
  a whole: never name or invent a specific player.

Style to copy:
CHASING -> "You jumped in right after the price ran up, which is the expensive seat."
CUT_LOSSES -> "Selling Jokic at a loss stings, but stepping off a slide beats riding it down."
DIVERSIFICATION -> "Your roster now leans on several names, so one cold night hurts a lot less."

Return only the tip."""

SITUATIONS = {
    Concept.WELCOME: "just made their very first trade in the game",
    Concept.TAKE_GAINS: "sold a player for more than they paid, locking in a gain",
    Concept.CUT_LOSSES: "sold a player for less than they paid, taking a loss",
    Concept.CHASING: "bought a player right after that player's price ran up",
    Concept.BUY_LOW: "bought a player after that player's price had fallen",
    Concept.VOLATILITY: "bought a player whose game-to-game performance swings a lot",
    Concept.STABILITY: "bought a player whose game-to-game performance is steady",
    Concept.DIVERSIFICATION: "now holds shares in several different players",
}


# A global concept is cached under one key and served to every user for every
# athlete, so its text has to hold true for all of them.
FALLBACK_LESSONS = {
    Concept.WELCOME: (
        "Your first trade is in -- from here you own a slice of the market and "
        "its ups and downs."
    ),
    Concept.DIVERSIFICATION: (
        "Your roster now leans on several names, so one cold night barely dents "
        "the whole thing."
    ),
}

# Skip initials and particles ("Jr", "de", "Bo") that would match ordinary prose.
MIN_NAME_TOKEN = 4


def _user_prompt(concept: Concept, athlete_name: str | None, side: Side) -> str:
    situation = SITUATIONS[concept]
    lines = [f"Concept to teach: {concept}"]
    if athlete_name is not None:
        lines.append(f"Player involved: {athlete_name}")
    else:
        # cached once for everyone, so it must not belong to any one player
        lines.append("Player involved: none -- write about the portfolio generally")
    lines.append(f"Action: {side.value}")
    lines.append(f"Situation: the user {situation}.")
    return "\n".join(lines)


def athlete_name_tokens(session) -> set[str]:
    """Full names and surnames, for spotting a player named in a global tip."""
    tokens = set()
    for (name,) in session.execute(select(Athlete.name)).all():
        tokens.add(name)
        tokens.update(part for part in name.split() if len(part) >= MIN_NAME_TOKEN)
    return tokens


def names_a_player(text: str, tokens: set[str]) -> bool:
    """Case-sensitive: "Judge" the player counts, "judge" the verb does not."""
    return any(re.search(rf"\b{re.escape(token)}\b", text) for token in tokens)


# Any figure in a shared lesson is a fact about one trader -- their cash, their
# holdings count, their P&L. Currency, percents and bare numbers are the tell.
FIGURE = re.compile(r"[\d$%]")


def cites_a_figure(text: str) -> bool:
    return FIGURE.search(text) is not None


def assert_shareable(session, concept: Concept, text: str) -> None:
    """Refuse to cache a global lesson that carries anything user-specific.

    cache_key() collapses a global concept to one row served to every user, so
    its text has to hold true for all of them: no player name, and no fact about
    the account that triggered it (cash, holdings count, gain or loss). Checked
    here at the write rather than in the generator so a future global concept
    cannot bypass it and silently show one user's numbers to the next.
    """
    if concept not in GLOBAL_CONCEPTS:
        return
    if names_a_player(text, athlete_name_tokens(session)):
        raise ValueError(f"global lesson {concept} names a player: {text!r}")
    if cites_a_figure(text):
        raise ValueError(f"global lesson {concept} cites a figure: {text!r}")


def _global_text(session, concept: Concept, side: Side, provider) -> str:
    """Generate a player-agnostic lesson, retrying once, then falling back."""
    prompt = _user_prompt(concept, None, side)
    tokens = athlete_name_tokens(session)
    for _ in range(2):
        text = provider.generate(SYSTEM_PROMPT, prompt)
        if not names_a_player(text, tokens) and not cites_a_figure(text):
            return text
    # never cache a global lesson that names a player or quotes a number
    return FALLBACK_LESSONS[concept]


def lesson_for_trade(session, trade: Trade) -> dict:
    concept = pick_concept(session, trade)
    key = cache_key(concept, trade.athlete_id)

    cached = session.scalar(select(Lesson).where(Lesson.cache_key == key))
    if cached is not None:
        return {"concept": str(concept), "text": cached.text, "cached": True}

    provider = get_provider()
    if concept in GLOBAL_CONCEPTS:
        text = _global_text(session, concept, trade.side, provider)
    else:
        athlete = session.get(Athlete, trade.athlete_id)
        text = provider.generate(
            SYSTEM_PROMPT, _user_prompt(concept, athlete.name, trade.side)
        )

    assert_shareable(session, concept, text)
    session.add(Lesson(cache_key=key, concept=str(concept), text=text))
    session.commit()
    return {"concept": str(concept), "text": text, "cached": False}
