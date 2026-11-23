"""users and weekly_reports tables; drop readings.battery

Revision ID: a3c1e9d27b10
Revises: f196042084e8
Create Date: 2026-11-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c1e9d27b10'
down_revision: Union[str, Sequence[str], None] = 'f196042084e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('username', sa.String(length=30), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('premium', sa.Boolean(), nullable=False),
    sa.Column('consent', sa.Boolean(), nullable=False),
    sa.Column('device_id', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('device_id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('weekly_reports',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('week_end', sa.Date(), nullable=False),
    sa.Column('report_content', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_column('readings', 'battery')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('readings', sa.Column('battery', sa.SmallInteger(), nullable=True))
    op.drop_table('weekly_reports')
    op.drop_table('users')
