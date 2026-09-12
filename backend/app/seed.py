"""Seed a database from empty to playable. Run: python -m app.seed

Idempotent end to end, so it is safe to re-run against any DATABASE_URL:
  1. create tables
  2. ingest athletes from the sport adapters
  3. load per-game logs and perf baselines
  4. open the market at each athlete's baseline price
"""

from sqlalchemy import func, select

from app.adapters.mlb import MLBAdapter
from app.adapters.nba import NBAAdapter
from app.adapters.nfl import NFLAdapter
from app.adapters.nhl import NHLAdapter
from app.adapters.soccer import SoccerAdapter
from app.db import Base, SessionLocal, engine
from app.gamelogs import load_game_logs
from app.gamelogs_generic import load_game_logs_for
from app.gamelogs_nfl import load_nfl_game_logs
from app.ingest import ingest, prune_sport
from app.models import Athlete, AthleteStat, Price
from app.norms import baseline_price, compute_sport_norms, get_sport_norms
from app.pricing import init_market, open_missing_prices


def _sport_jobs(soccer):
    """Each sport: (label, ingest callable, game-log callable)."""
    nba, nfl = NBAAdapter(), NFLAdapter()
    nhl, mlb = NHLAdapter(), MLBAdapter()
    return [
        ("NBA", nba, load_game_logs),
        ("NFL", nfl, load_nfl_game_logs),
        ("NHL", nhl, lambda: load_game_logs_for(nhl)),
        ("MLB", mlb, lambda: load_game_logs_for(mlb)),
        ("FUT", soccer, lambda: load_game_logs_for(soccer)),
    ]


def run_all_sports(soccer) -> list[str]:
    """Ingest every sport in isolation. One sport failing never stops the rest."""
    status = []
    for label, adapter, load_logs in _sport_jobs(soccer):
        try:
            refs = ingest(adapter)
            with SessionLocal() as session:
                removed, kept = prune_sport(session, adapter.sport, set(refs))
            logs = load_logs()
            games = sum(g for _, g in logs)
            line = f"{label}: {len(refs)} players, {games} games"
            if removed:
                line += f", dropped {len(removed)} stale"
            if kept:
                line += f", kept {len(kept)} held/traded"
            status.append(line)
        except Exception as exc:
            status.append(f"{label}: FAILED - {type(exc).__name__}: {str(exc)[:110]}")
    return status


def report_soccer_values(adapter) -> None:
    """Print what the value ranking gave us and what it matched to."""
    if not adapter.value_rows:
        print("     (no value ranking fetched)")
        return

    print(f"     parsed {len(adapter.value_rows)} ranked players from the value page")
    for league, note in sorted(adapter.league_status.items()):
        print(f"       {league}: {note}")
    print()
    print(f"     {'#':>3} {'player':24} {'€m':>5} {'pos':>4} {'lg':5} {'team':5} src-pos")
    for entry in adapter.resolved:
        espn = entry["espn"]
        flag = "" if entry["source_position"][:1] == (espn["position"] or "") else "  <- source disagreed"
        print(
            f"     {entry['rank']:>3} {espn['display'][:24]:24} {entry['value_m']:>5.0f} "
            f"{espn['position'] or '?':>4} {espn['tag']:5} {espn['team']:5} "
            f"{entry['source_position']}{flag}"
        )
    if adapter.unresolved:
        print()
        print(f"     UNRESOLVED ({len(adapter.unresolved)}) - skipped:")
        for entry in adapter.unresolved:
            print(
                f"       {entry['rank']:>3} {entry['name'][:24]:24} "
                f"{entry['club'][:22]:22} €{entry['value_m']:.0f}m - {entry['why']}"
            )


def report_soccer_baselines(session) -> None:
    """Show that football baselines track market value, not attacking output."""
    norms = get_sport_norms(session)
    norm = norms.get("FUT")
    if norm is None:
        print("     (no FUT norm)")
        return

    print(f"     anchor stat: {norm.anchor_stat}  "
          f"mean {norm.mean_anchor}  std {norm.std_anchor}")
    rows = []
    for athlete in session.scalars(select(Athlete).where(Athlete.sport == "FUT")).all():
        stats = {
            s.stat_key: float(s.value)
            for s in session.scalars(
                select(AthleteStat).where(AthleteStat.athlete_id == athlete.id)
            ).all()
        }
        value = stats.get("market_value")
        # same fallback pricing uses: no value means "average for the sport"
        anchor = float(norm.mean_anchor) if value is None else value
        rows.append(
            (
                baseline_price(anchor, norm),
                athlete.name,
                athlete.position,
                value,
                stats.get("perf_mean", 0.0),
            )
        )
    rows.sort(reverse=True)
    print(f"     {'baseline':>9} {'player':24} {'pos':>4} {'€m':>5} {'perf_mean':>9}")
    for price, name, position, value, perf in rows:
        shown = f"{value:>5.0f}" if value is not None else "    -"
        print(f"     {price:>9.2f} {name[:24]:24} {position or '?':>4} {shown} {perf:>9.2f}")

    defenders = [r for r in rows if r[2] in ("D", "G")]
    if defenders:
        ranks = {name: i + 1 for i, (_, name, _, _, _) in enumerate(rows)}
        print()
        print(f"     defenders/keepers by baseline rank (of {len(rows)}):")
        for price, name, position, value, perf in defenders:
            print(
                f"       #{ranks[name]:<3} {name[:24]:24} {position} "
                f"€{value:.0f}m  baseline {price:.2f}  attacking perf_mean {perf:.2f}"
            )


def report_top_cross_sport(session, limit: int = 20) -> None:
    norms = get_sport_norms(session)
    rows = []
    for athlete in session.scalars(select(Athlete)).all():
        norm = norms.get(athlete.sport)
        if norm is None:
            continue
        stats = {
            s.stat_key: float(s.value)
            for s in session.scalars(
                select(AthleteStat).where(AthleteStat.athlete_id == athlete.id)
            ).all()
        }
        anchor = stats.get(norm.anchor_stat, stats.get("perf_mean", 0.0))
        rows.append((baseline_price(anchor, norm), athlete.name, athlete.sport, athlete.position))
    rows.sort(reverse=True)
    print(f"     {'baseline':>9} {'player':26} {'sport':6} pos")
    for price, name, sport, position in rows[:limit]:
        print(f"     {price:>9.2f} {name[:26]:26} {sport:6} {position or ''}")


def main() -> None:
    print("1/7 creating tables...")
    Base.metadata.create_all(engine)

    soccer = SoccerAdapter()
    print("2/7 ingesting athletes and loading game logs (per sport)...")
    status = run_all_sports(soccer)
    print()
    print("3/7 STATUS")
    for line in status:
        print(f"     {line}")

    print()
    print("4/7 SOCCER: value ranking -> ESPN")
    report_soccer_values(soccer)

    print()
    print("5/7 computing per-sport norms...")
    with SessionLocal() as session:
        norms = compute_sport_norms(session)
        for sport, norm in sorted(norms.items()):
            print(
                f"     {sport}: perf mean {norm.mean_perf} std {norm.std_perf} | "
                f"anchor {norm.anchor_stat} mean {norm.mean_anchor} "
                f"std {norm.std_anchor} | {norm.athlete_count} athletes"
            )

    print()
    print("6/7 SOCCER baselines (value-anchored)")
    with SessionLocal() as session:
        report_soccer_baselines(session)

    print()
    print("7/7 opening the market...")
    with SessionLocal() as session:
        # init_market writes a fresh opening price for everyone, so only run it
        # on a market that has never been opened.
        if session.scalar(select(func.count()).select_from(Price)):
            # market already trading: only newcomers need an opening price
            opened = open_missing_prices(session)
            print(f"     already open; opened {len(opened)} new athletes")
        else:
            opening = init_market(session)
            print(f"     opened {len(opening)} athletes at their baseline")

    print()
    print("CROSS-SPORT TOP 20 by baseline")
    with SessionLocal() as session:
        report_top_cross_sport(session)

    print("done.")


if __name__ == "__main__":
    main()
