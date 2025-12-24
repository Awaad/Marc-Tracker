"""add platform_probes table

Revision ID: 39ddbf80ddb1
Revises: dba45de921b1
Create Date: 2025-12-25 01:06:28.013380

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '39ddbf80ddb1'
down_revision: Union[str, Sequence[str], None] = 'dba45de921b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_probes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("probe_id", sa.String(length=64), nullable=False),
        sa.Column("platform_message_ts", sa.BigInteger(), nullable=True),
        sa.Column("sent_at_ms", sa.BigInteger(), nullable=False),
        sa.Column("delivered_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("read_at_ms", sa.BigInteger(), nullable=True),
        sa.Column("send_response", sa.JSON(), nullable=True),

    )
    op.create_index("ix_platform_probes_user_id", "platform_probes", ["user_id"])
    op.create_index("ix_platform_probes_contact_id", "platform_probes", ["contact_id"])
    op.create_index("ix_platform_probes_platform", "platform_probes", ["platform"])
    op.create_index("ix_platform_probes_probe_id", "platform_probes", ["probe_id"])
    op.create_index("ix_platform_probes_platform_message_ts", "platform_probes", ["platform_message_ts"])
    op.create_index("ix_platform_probe_unique", "platform_probes", ["platform", "probe_id"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_platform_probe_unique", table_name="platform_probes")
    op.drop_table("platform_probes")
