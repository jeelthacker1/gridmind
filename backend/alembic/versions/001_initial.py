"""Initial versioned schema."""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("password", sa.String(300), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.CheckConstraint("role IN ('admin','analyst','viewer')"),
    )
    op.create_table(
        "login_sessions",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires", sa.Float, nullable=False),
    )
    op.create_table(
        "factories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
        sa.Column("rows", sa.JSON, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_kind", "runs", ["kind"])
    op.create_index("ix_runs_created", "runs", ["created"])
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("cursor", sa.Integer, nullable=False),
        sa.Column("speed", sa.Integer, nullable=False),
        sa.Column("playing", sa.Boolean, nullable=False),
        sa.Column("updated", sa.Float, nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created"])
    op.create_table(
        "energy_assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "factory_id", sa.Integer, sa.ForeignKey("factories.id"), nullable=False
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("configuration", sa.JSON, nullable=False),
    )
    op.create_table(
        "scenario_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("changes", sa.JSON, nullable=False),
    )
    op.create_index("ix_scenario_events_run_id", "scenario_events", ["run_id"])


def downgrade():
    for name in (
        "scenario_events",
        "energy_assets",
        "audit_logs",
        "simulation_runs",
        "runs",
        "datasets",
        "factories",
        "login_sessions",
        "users",
    ):
        op.drop_table(name)
