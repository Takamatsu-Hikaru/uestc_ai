"""Admin-configurable mail delivery (Resend or SMTP)."""
from alembic import op
import sqlalchemy as sa
from migrations.schema_helpers import ensure_index, ensure_table

revision = "d5b8e3a91c47"
down_revision = "c9f1a6e2087b"
branch_labels = None
depends_on = None


def upgrade():
    # Local development may already have created the current model schema.
    ensure_table("mail_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("sender", sa.String(200), nullable=False),
        sa.Column("fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resend_secret", sa.Text()),
        sa.Column("smtp_host", sa.String(200)),
        sa.Column("smtp_port", sa.Integer()),
        sa.Column("smtp_security", sa.String(16)),
        sa.Column("smtp_username", sa.String(200)),
        sa.Column("smtp_secret", sa.Text()),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_test", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    ensure_index("ix_mail_settings_updated_by", "mail_settings", ["updated_by"])


def downgrade():
    # The stored row is operator configuration, not user data, so dropping the
    # table is reversible: the platform falls back to the RESEND_* environment.
    op.drop_index("ix_mail_settings_updated_by", table_name="mail_settings")
    op.drop_table("mail_settings")
