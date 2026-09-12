"""Retire athletes that have left their sport's selection but are still held.

Run: python -m app.retire [--apply]

prune_sport deletes athletes an adapter no longer selects, but it refuses to
touch anyone a user has traded or holds -- deleting those would tear a hole in
that user's history. This closes the loop for the ones it spared: cash the
holders out at the current market price, then strip the athlete's market data.

The athlete ROW survives, and so do its trades. trades.athlete_id is NOT NULL
with ON DELETE NO ACTION, so deleting the athlete would mean deleting real past
trades. Instead the row is stamped retired_at and filtered out of pricing and
the market list, which is what "gone from the market" has to mean here.
"""

import argparse
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import (
    Athlete,
    AthleteStat,
    GameLog,
    Holding,
    MarketAthleteState,
    Portfolio,
    Price,
    Side,
    Trade,
    utcnow,
)
from app.norms import compute_sport_norms

CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def latest_price(session, athlete_id: int) -> Decimal | None:
    price = session.scalar(
        select(Price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(1)
    )
    return price.price if price else None


def selected_refs(session, sport: str) -> set[str]:
    """The refs the most recent ingest of this sport refreshed.

    Ingest stamps every stat it writes with that run's date, so the newest
    as_of in a sport marks the roster the adapter last selected. Anything
    carrying only older stats fell out of the selection.
    """
    newest = session.scalar(
        select(func.max(AthleteStat.as_of))
        .join(Athlete, Athlete.id == AthleteStat.athlete_id)
        .where(Athlete.sport == sport)
    )
    if newest is None:
        return set()
    return set(
        session.scalars(
            select(Athlete.external_ref)
            .join(AthleteStat, AthleteStat.athlete_id == Athlete.id)
            .where(Athlete.sport == sport, AthleteStat.as_of == newest)
            .distinct()
        ).all()
    )


def stale_held_athletes(session) -> list[tuple[Athlete, set[str], date]]:
    """Athletes outside their sport's current selection that someone still holds."""
    sports = session.scalars(select(Athlete.sport).distinct()).all()

    stale = []
    for sport in sorted(sports):
        keep = selected_refs(session, sport)
        if not keep:
            continue  # no ingest has stamped this sport; nothing to compare against
        candidates = session.scalars(
            select(Athlete).where(
                Athlete.sport == sport,
                Athlete.retired_at.is_(None),
                Athlete.external_ref.not_in(keep),
            )
        ).all()
        for athlete in candidates:
            held = session.scalar(
                select(func.count())
                .select_from(Holding)
                .where(Holding.athlete_id == athlete.id, Holding.quantity > 0)
            )
            if held:
                stale.append((athlete, keep, sport))
    return stale


def liquidate(session, athlete: Athlete, price: Decimal) -> list[dict]:
    """Sell every open position in this athlete at `price`, one user per commit.

    Each user is its own transaction: a failure on one holder leaves the others
    already cashed out rather than rolling the whole sweep back.
    """
    holdings = session.scalars(
        select(Holding).where(Holding.athlete_id == athlete.id, Holding.quantity > 0)
    ).all()

    done = []
    for holding in holdings:
        quantity = holding.quantity
        proceeds = _money(price * quantity)
        portfolio = session.scalar(
            select(Portfolio).where(Portfolio.user_id == holding.user_id)
        )
        if portfolio is None:
            # holding without a portfolio should not happen; skip rather than crash
            done.append(
                {
                    "user_id": holding.user_id,
                    "quantity": quantity,
                    "price": price,
                    "proceeds": Decimal("0"),
                    "cash_before": None,
                    "cash_after": None,
                    "error": "no portfolio",
                }
            )
            continue

        before = portfolio.cash
        try:
            # same money math as the sell endpoint, so the ledger is consistent
            portfolio.cash = _money(portfolio.cash + proceeds)
            session.add(
                Trade(
                    user_id=holding.user_id,
                    athlete_id=athlete.id,
                    side=Side.sell,
                    quantity=quantity,
                    price=price,
                )
            )
            holding.quantity = 0
            session.flush()
            # the SELL trade is the record now; a zeroed holding is just a dangler
            session.delete(holding)
            session.commit()
        except Exception as exc:
            session.rollback()
            done.append(
                {
                    "user_id": holding.user_id,
                    "quantity": quantity,
                    "price": price,
                    "proceeds": Decimal("0"),
                    "cash_before": before,
                    "cash_after": before,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        done.append(
            {
                "user_id": holding.user_id,
                "quantity": quantity,
                "price": price,
                "proceeds": proceeds,
                "cash_before": before,
                "cash_after": portfolio.cash,
                "error": None,
            }
        )
    return done


def retire(session, athlete: Athlete) -> dict[str, int]:
    """Strip an athlete's market data and mark them retired. Trades survive."""
    if session.scalar(
        select(func.count())
        .select_from(Holding)
        .where(Holding.athlete_id == athlete.id, Holding.quantity > 0)
    ):
        raise RuntimeError(f"{athlete.name} still has open holdings; not retiring")

    removed = {}
    # FK-safe: every dependent row goes before the athlete is stamped. Holdings
    # at zero are removed too, so nothing dangles against a retired athlete.
    for model, label in (
        (Price, "prices"),
        (GameLog, "game_logs"),
        (AthleteStat, "athlete_stats"),
        (MarketAthleteState, "market_athlete_state"),
        (Holding, "holdings"),
    ):
        removed[label] = (
            session.execute(
                delete(model).where(model.athlete_id == athlete.id)
            ).rowcount
            or 0
        )
    removed["trades_kept"] = session.scalar(
        select(func.count()).select_from(Trade).where(Trade.athlete_id == athlete.id)
    )
    athlete.retired_at = utcnow()
    session.commit()
    return removed


def run(apply: bool = False) -> None:
    with SessionLocal() as session:
        stale = stale_held_athletes(session)
        if not stale:
            print("nothing to retire: no held athlete is outside its selection")
            return

        print(f"STALE + HELD ({len(stale)})")
        for athlete, keep, sport in stale:
            price = latest_price(session, athlete.id)
            holders = session.scalar(
                select(func.count())
                .select_from(Holding)
                .where(Holding.athlete_id == athlete.id, Holding.quantity > 0)
            )
            print(
                f"  #{athlete.id} {athlete.name} [{sport}] "
                f"ref={athlete.external_ref} holders={holders} "
                f"price={price} (sport selection: {len(keep)} refs)"
            )

        if not apply:
            print("\ndry run; pass --apply to liquidate and retire")
            return

        for athlete, _, sport in stale:
            price = latest_price(session, athlete.id)
            print(f"\n--- {athlete.name} [{sport}] @ {price}")
            if price is None:
                print("  no market price; cannot liquidate fairly -- skipped")
                continue

            for row in liquidate(session, athlete, price):
                if row["error"]:
                    print(f"  user#{row['user_id']}: FAILED - {row['error']}")
                    continue
                print(
                    f"  user#{row['user_id']}: sold {row['quantity']} @ {row['price']} "
                    f"= +{row['proceeds']}  cash {row['cash_before']} -> {row['cash_after']}"
                )

            removed = retire(session, athlete)
            print(
                "  retired; removed "
                + ", ".join(f"{v} {k}" for k, v in removed.items() if k != "trades_kept")
                + f"; kept {removed['trades_kept']} trades"
            )

    with SessionLocal() as session:
        print("\nrecomputing sport norms...")
        for sport, norm in sorted(compute_sport_norms(session).items()):
            print(
                f"  {sport}: anchor {norm.anchor_stat} mean {norm.mean_anchor} "
                f"std {norm.std_anchor} | {norm.athlete_count} athletes"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="actually liquidate and retire"
    )
    run(apply=parser.parse_args().apply)


if __name__ == "__main__":
    main()
