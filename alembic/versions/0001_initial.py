"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

task_status_enum = sa.Enum("todo", "in_progress", "done", name="taskstatus")
task_priority_enum = sa.Enum("low", "medium", "high", name="taskpriority")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("email", sa.String, unique=True, index=True, nullable=False),
        sa.Column("full_name", sa.String, nullable=False),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", task_status_enum, nullable=False, server_default="todo"),
        sa.Column("priority", task_priority_enum, nullable=False, server_default="medium"),
        sa.Column("due_date", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("s3_key", sa.String, nullable=False),
        sa.Column("content_type", sa.String, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("attachments")
    op.drop_table("tasks")
    op.drop_table("projects")
    op.drop_table("users")
    task_status_enum.drop(op.get_bind(), checkfirst=True)
    task_priority_enum.drop(op.get_bind(), checkfirst=True)
