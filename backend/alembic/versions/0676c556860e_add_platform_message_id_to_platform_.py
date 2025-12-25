"""add platform_message_id to platform_probes

Revision ID: 0676c556860e
Revises: 1d20b7896f0b
Create Date: 2025-12-25 14:39:34.002381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0676c556860e'
down_revision: Union[str, Sequence[str], None] = '1d20b7896f0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("platform_probes", sa.Column("platform_message_id", sa.String(length=128), nullable=True))
    op.create_index("ix_platform_probes_platform_message_id", "platform_probes", ["platform_message_id"])




def downgrade() -> None:
    op.drop_index("ix_platform_probes_platform_message_id", table_name="platform_probes")
    op.drop_column("platform_probes", "platform_message_id")

