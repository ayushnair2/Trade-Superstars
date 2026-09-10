"""Tunable constants shared by ingest and the pricing engine.

perf_score is the single definition of "how well did this athlete play".
Ingest and the engine must both call it -- never re-implement the weights.
"""

PTS_WEIGHT = 1.0
REB_WEIGHT = 0.5
AST_WEIGHT = 0.5


def perf_score(pts: float, reb: float, ast: float) -> float:
    return PTS_WEIGHT * pts + REB_WEIGHT * reb + AST_WEIGHT * ast


# --- Pricing engine ---------------------------------------------------------
# Price of a perfectly average athlete in any sport.
PRICE_BASE = 120.0
# Dollars of price per standard deviation above/below that sport's average.
PRICE_Z_SCALE = 30.0
# How many recent steps count as "current form".
FORM_WINDOW = 5
# The market overreacts to form: >1 amplifies the gap vs baseline.
OVERREACTION = 1.5
# Per-step randomness in how hard the market overreacts.
REACTION_JITTER = 0.2
# Fraction of the gap to target closed each step.
MOMENTUM = 0.3
# Pull back toward baseline each step, so prices mean-revert.
TETHER = 0.05
# Multiplicative per-step noise (stdev, as a fraction of price).
TICK_JITTER = 0.01
PRICE_FLOOR = 1.0
MARKET_SEED = 1337
# How many recent prices the dashboard sparkline shows, and the lookback
# distance for percent change.
SPARK_WINDOW = 12
# Seconds between automatic market advances.
TICK_INTERVAL_SECONDS = 3


# --- AI lessons -------------------------------------------------------------
LLM_PROVIDER = "groq"
# Verified against Groq's live model list. Not a reasoning model, which matters:
# max_completion_tokens covers reasoning + output, so on gpt-oss a 60-token cap
# starved the answer (empty 5 of 8 tries). Here the cap limits the tip itself.
LLM_MODEL = "groq/compound-mini"
LESSON_MAX_TOKENS = 60
