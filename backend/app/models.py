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
    # the source's own position code, when it publishes one (football: F/M/D/G).
    # Drives how far per-game output may move a price -- see FUT_MOVE_WEIGHTS.
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_ref: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    # Set when an athlete leaves the market but cannot be deleted, because
    # trades.athlete_id is NOT NULL and past trades are real events we keep.
    # Retired athletes are excluded from pricing and the market list, so they
    # neither quote a price nor accrue new state.
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
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
    __table_args__ = (
        UniqueConstraint("user_id", "athlete_id", name="uq_user_athlete_holding"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    quantity: Mapped[int] = mapped_column(default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    athlete: Mapped["Athlete"] = relationship(back_populates="holding")


class Portfolio(Base):
    """One portfolio per user, created lazily on first authenticated access."""

    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
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


class SportNorm(Base):
    """Per-sport distributions, so prices compare across sports.

    Two of them. mean_perf/std_perf describe game-to-game production and scale
    how far form moves a price. mean_anchor/std_anchor describe whatever sets
    the sport's price LEVEL -- production for most sports, market value for
    football, where the free per-game data cannot see defending.
    """

    __tablename__ = "sport_norms"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport: Mapped[str] = mapped_column(String(40), unique=True)
    mean_perf: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    std_perf: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    # which AthleteStat key the anchor distribution was built from
    anchor_stat: Mapped[str] = mapped_column(String(40), default="perf_mean")
    mean_anchor: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    std_anchor: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    athlete_count: Mapped[int] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    """A player account. Only the bcrypt hash is stored, never the password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # stored lowercased so lookups are case-insensitive
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Fund(Base):
    """An index fund: a fixed basket of athletes priced as one asset."""

    __tablename__ = "funds"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    members: Mapped[list["FundMember"]] = relationship(back_populates="fund")


class FundMember(Base):
    """One athlete's share of a fund. Weights across a fund sum to 1."""

    __tablename__ = "fund_members"
    __table_args__ = (
        UniqueConstraint("fund_id", "athlete_id", name="uq_fund_athlete"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"))
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id"))
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 6))

    fund: Mapped["Fund"] = relationship(back_populates="members")
    athlete: Mapped["Athlete"] = relationship()


class FundPrice(Base):
    """A fund's price over time.

    Its own table rather than a nullable asset reference on prices: making
    prices.athlete_id nullable would weaken that FK and change every athlete
    price query -- the market window function, the history endpoint, pruning
    and the portfolio's cost basis -- to serve a second asset type.
    """

    __tablename__ = "fund_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    fund: Mapped["Fund"] = relationship()
