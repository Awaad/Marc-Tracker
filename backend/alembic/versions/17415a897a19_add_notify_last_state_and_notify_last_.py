"""add notify_last_state and notify_last_sent_at_ms to contacts

Revision ID: 17415a897a19
Revises: 7156bb65320f
Create Date: 2025-12-28 00:10:02.537247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17415a897a19'
down_revision: Union[str, Sequence[str], None] = '7156bb65320f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("contacts", "notify_last_state"):
        op.add_column("contacts", sa.Column("notify_last_state", sa.String(length=16), nullable=True))

    if not _has_column("contacts", "notify_last_sent_at_ms"):
        op.add_column("contacts", sa.Column("notify_last_sent_at_ms", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    if _has_column("contacts", "notify_last_sent_at_ms"):
        op.drop_column("contacts", "notify_last_sent_at_ms")
    if _has_column("contacts", "notify_last_state"):
        op.drop_column("contacts", "notify_last_state")
