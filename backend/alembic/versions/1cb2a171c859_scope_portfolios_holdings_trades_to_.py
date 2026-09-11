"""scope portfolios holdings trades to users

Revision ID: 1cb2a171c859
Revises: b5f9731f78ed
Create Date: 2026-09-10 21:56:24.958307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cb2a171c859'
down_revision: Union[str, Sequence[str], None] = 'b5f9731f78ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The old portfolio/holdings/trades were a single global sandbox with no
    # owner. There is no sensible user to attribute them to, so they are wiped
    # before the NOT NULL owner columns land. Market data is untouched.
    op.execute(sa.text("DELETE FROM trades"))
    op.execute(sa.text("DELETE FROM holdings"))
    op.execute(sa.text("DELETE FROM portfolio"))

    # one row per user now, so the single-global-row rule has to go
    op.drop_constraint("portfolio_single_row", "portfolio", type_="check")

    # portfolio.id was never a sequence: the old model pinned it to 1, so
    # SQLAlchemy created a plain integer column. Multiple portfolios need
    # generated ids.
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS portfolio_id_seq OWNED BY portfolio.id"))
    op.execute(
        sa.text("ALTER TABLE portfolio ALTER COLUMN id SET DEFAULT nextval('portfolio_id_seq')")
    )

    op.add_column('holdings', sa.Column('user_id', sa.Integer(), nullable=False))
    op.drop_constraint(op.f('holdings_athlete_id_key'), 'holdings', type_='unique')
    op.create_unique_constraint('uq_user_athlete_holding', 'holdings', ['user_id', 'athlete_id'])
    op.create_foreign_key('fk_holdings_user', 'holdings', 'users', ['user_id'], ['id'])

    op.add_column('portfolio', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_unique_constraint('uq_portfolio_user', 'portfolio', ['user_id'])
    op.create_foreign_key('fk_portfolio_user', 'portfolio', 'users', ['user_id'], ['id'])

    op.add_column('trades', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key('fk_trades_user', 'trades', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM trades"))
    op.execute(sa.text("DELETE FROM holdings"))
    op.execute(sa.text("DELETE FROM portfolio"))

    op.drop_constraint('fk_trades_user', 'trades', type_='foreignkey')
    op.drop_column('trades', 'user_id')

    op.drop_constraint('fk_portfolio_user', 'portfolio', type_='foreignkey')
    op.drop_constraint('uq_portfolio_user', 'portfolio', type_='unique')
    op.drop_column('portfolio', 'user_id')

    op.drop_constraint('fk_holdings_user', 'holdings', type_='foreignkey')
    op.drop_constraint('uq_user_athlete_holding', 'holdings', type_='unique')
    op.create_unique_constraint(op.f('holdings_athlete_id_key'), 'holdings', ['athlete_id'])
    op.drop_column('holdings', 'user_id')

    op.execute(sa.text("ALTER TABLE portfolio ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS portfolio_id_seq"))
    op.create_check_constraint("portfolio_single_row", "portfolio", "id = 1")
