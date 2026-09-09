"""Generate (and cache) a one-off lesson for a trade."""

from sqlalchemy import select

from app.lessons.concepts import Concept, cache_key, pick_concept
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
- Plain language. Name the athlete where it reads naturally.

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


def _user_prompt(concept: Concept, athlete_name: str, side: Side) -> str:
    situation = SITUATIONS[concept]
    return (
        f"Concept to teach: {concept}\n"
        f"Player involved: {athlete_name}\n"
        f"Action: {side.value}\n"
        f"Situation: the user {situation}."
    )


def lesson_for_trade(session, trade: Trade) -> dict:
    concept = pick_concept(session, trade)
    key = cache_key(concept, trade.athlete_id)

    cached = session.scalar(select(Lesson).where(Lesson.cache_key == key))
    if cached is not None:
        return {"concept": str(concept), "text": cached.text, "cached": True}

    athlete = session.get(Athlete, trade.athlete_id)
    text = get_provider().generate(
        SYSTEM_PROMPT, _user_prompt(concept, athlete.name, trade.side)
    )

    session.add(Lesson(cache_key=key, concept=str(concept), text=text))
    session.commit()
    return {"concept": str(concept), "text": text, "cached": False}
