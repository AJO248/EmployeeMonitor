"""Initial EM schema."""

from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260614_0001"
down_revision: Optional[str] = None
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("app_name", sa.String(length=255), nullable=True),
        sa.Column("event_ts", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_entries_app_name", "log_entries", ["app_name"])
    op.create_index("ix_log_entries_device_id", "log_entries", ["device_id"])
    op.create_index("ix_log_entries_domain", "log_entries", ["domain"])
    op.create_index("ix_log_entries_event_ts", "log_entries", ["event_ts"])
    op.create_index("ix_log_entries_event_type", "log_entries", ["event_type"])
    op.create_index("ix_log_entries_id", "log_entries", ["id"])


def downgrade() -> None:
    op.drop_table("log_entries")
    op.drop_table("admin_users")
