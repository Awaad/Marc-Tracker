"""add probe_id to tracker_points

Revision ID: 1d20b7896f0b
Revises: 39ddbf80ddb1
Create Date: 2025-12-25 01:42:05.715420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d20b7896f0b'
down_revision: Union[str, Sequence[str], None] = '39ddbf80ddb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracker_points", sa.Column("probe_id", sa.String(length=64), nullable=True))
    op.create_index("ix_tracker_points_probe_id", "tracker_points", ["probe_id"])



def downgrade() -> None:
    op.drop_index("ix_tracker_points_probe_id", table_name="tracker_points")
    op.drop_column("tracker_points", "probe_id")

