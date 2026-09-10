import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Side(enum.Enum):
    buy = "buy"
    sell = "sell"


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    sport: Mapped[str] = mapped_column(String(40))
    team: Mapped[str] = mapped_column(String(80))
    external_ref: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    prices: Mapped[list["Price"]] = relationship(back_populates="athlete")
    trades: Mapped[list["Trade"]] = relationship(back_populates="athlete")
    holding: Mapped["Holding | None"] = relationship(back_populates="athlete")
    stats: Mapped[list["AthleteStat"]] = relationship(back_populates="athlete")
    game_logs: Mapped[list["GameLog"]] = relationship(back_populates="athlete")


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="prices")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    side: Mapped[Side] = mapped_column(Enum(Side, name="trade_side"))
    quantity: Mapped[int] = mapped_column()
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="trades")


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), unique=True)
    quantity: Mapped[int] = mapped_column(default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    athlete: Mapped["Athlete"] = relationship(back_populates="holding")


class Portfolio(Base):
    """Single-row table: this is a solo sim, so there is exactly one portfolio."""

    __tablename__ = "portfolio"
    __table_args__ = (CheckConstraint("id = 1", name="portfolio_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("100000"))


class AthleteStat(Base):
    """Per-sport stat store: each sport writes whatever stat_keys it has."""

    __tablename__ = "athlete_stats"
    __table_args__ = (
        UniqueConstraint("athlete_id", "stat_key", name="uq_athlete_stat_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    stat_key: Mapped[str] = mapped_column(String(40))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    as_of: Mapped[date] = mapped_column(Date)

    athlete: Mapped["Athlete"] = relationship(back_populates="stats")


class GameLog(Base):
    """One athlete's single game. game_index 0 is their oldest game this season."""

    __tablename__ = "game_logs"
    __table_args__ = (
        UniqueConstraint("athlete_id", "game_index", name="uq_athlete_game_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    game_index: Mapped[int] = mapped_column()
    game_date: Mapped[date] = mapped_column(Date)
    pts: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    reb: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    ast: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    perf_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    athlete: Mapped["Athlete"] = relationship(back_populates="game_logs")


class MarketState(Base):
    """Single-row market clock: where the simulation is and what seeds it."""

    __tablename__ = "market_state"
    __table_args__ = (CheckConstraint("id = 1", name="market_state_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    current_step: Mapped[int] = mapped_column(default=0)
    # Game-days are the slow layer; current_step counts price ticks.
    current_day: Mapped[int] = mapped_column(default=0)
    seed: Mapped[int] = mapped_column()


class Lesson(Base):
    """Cached AI lesson text, keyed by concept (+ athlete when player-specific)."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(120), unique=True)
    concept: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketAthleteState(Base):
    """Per-athlete values set on a game-day and read by every price tick."""

    __tablename__ = "market_athlete_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"), unique=True)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    current_target: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    last_game_day: Mapped[int] = mapped_column()


class Settings(Base):
    """Single-row market cadence settings."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="settings_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    day_length_minutes: Mapped[int] = mapped_column(default=10)
    ticks_per_day: Mapped[int] = mapped_column(default=10)
    randomness: Mapped[str] = mapped_column(String(20), default="fully_random")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
