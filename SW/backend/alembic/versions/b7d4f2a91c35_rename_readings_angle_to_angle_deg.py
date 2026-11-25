"""rename readings.angle to angle_deg

Revision ID: b7d4f2a91c35
Revises: a3c1e9d27b10
Create Date: 2026-11-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d4f2a91c35'
down_revision: Union[str, Sequence[str], None] = 'a3c1e9d27b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Written by hand: autogenerate would drop `angle` and add `angle_deg`, losing the data.
    op.alter_column('readings', 'angle', new_column_name='angle_deg')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('readings', 'angle_deg', new_column_name='angle')
