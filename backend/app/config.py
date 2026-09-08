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
# Dollars of price per point of perf_score.
PRICE_SCALE = 4.0
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
