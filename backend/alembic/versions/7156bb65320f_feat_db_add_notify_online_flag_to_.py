from alembic import op
import sqlalchemy as sa


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1) add column if it doesn't already exist (important because your previous run partially applied it)
    if not _has_column("contacts", "notify_online"):
        op.add_column(
            "contacts",
            sa.Column(
                "notify_online",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),  # SQLite friendly
            ),
        )

    # 2) On SQLite, DO NOT try to drop the default (ALTER COLUMN not supported)
    # On Postgres/MySQL, you can remove the server default if you want
    if dialect != "sqlite":
        op.alter_column("contacts", "notify_online", server_default=None)


def downgrade() -> None:
    # SQLite can't DROP COLUMN on older versions; but modern SQLite can.
    # Alembic will emit DROP COLUMN; if your SQLite is too old, you’ll need batch mode.
    if _has_column("contacts", "notify_online"):
        op.drop_column("contacts", "notify_online")
