"""Generate (and cache) a one-off lesson for a trade."""

from sqlalchemy import select

from app.lessons.concepts import Concept, cache_key, pick_concept
from app.lessons.provider import get_provider
from app.models import Athlete, Lesson, Side, Trade

SYSTEM_PROMPT = """You write micro-lessons for a beginner in a sports-trading game.

Rules, all mandatory:
- Reply with at most 2 sentences. No preamble, no bullet points, no headings.
- Plain, friendly language a curious beginner understands. No jargon unless you
  explain it in the same sentence.
- Teach ONLY the one concept you are given. Do not mention other concepts.
- You may name the player and describe the general situation, but NEVER mention
  specific dollar amounts, share counts, or percentages, and never invent
  statistics for the player.
- This is a game with pretend money. Never give real financial advice, never
  tell the user what to buy or sell, and never predict where a price will go.
Return only the lesson text."""

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
