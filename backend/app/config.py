"""Tunable constants shared by ingest and the pricing engine.

perf_score is the single definition of "how well did this athlete play".
Ingest and the engine must both call it -- never re-implement the weights.
"""

PTS_WEIGHT = 1.0
REB_WEIGHT = 0.5
AST_WEIGHT = 0.5


def perf_score(pts: float, reb: float, ast: float) -> float:
    return PTS_WEIGHT * pts + REB_WEIGHT * reb + AST_WEIGHT * ast
