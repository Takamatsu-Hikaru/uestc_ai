"""Encrypted manual AutoDL accounts per team and problem."""
from alembic import op
import sqlalchemy as sa
from migrations.schema_helpers import ensure_index, ensure_table

revision = "c9f1a6e2087b"
down_revision = "b0479d2e8a61"
branch_labels = None
depends_on = None


def upgrade():
    # Local development may already have created the current model schema.
    ensure_table("compute_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("problem_id", sa.String(36), sa.ForeignKey("problems.id"), nullable=False),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "problem_id", name="uq_compute_account_team_problem"))
    ensure_index("ix_compute_accounts_team_id", "compute_accounts", ["team_id"])
    ensure_index("ix_compute_accounts_problem_id", "compute_accounts", ["problem_id"])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT id FROM compute_accounts LIMIT 1")).first():
        raise RuntimeError("Cannot remove manually issued compute accounts; archive them before downgrade.")
    policies = bind.execute(sa.text("SELECT config FROM compute_policies")).scalars()
    import json
    if any((json.loads(p) if isinstance(p, str) else p).get("mode") == "manual_account" for p in policies):
        raise RuntimeError("Cannot downgrade while manual account delivery policies exist.")
    op.drop_table("compute_accounts")
