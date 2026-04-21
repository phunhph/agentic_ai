"""add_learning_score_fields

Revision ID: 8d2c1e4a5b77
Revises: 4b9d1f72f9c1
Create Date: 2026-04-21 23:58:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2c1e4a5b77"
down_revision: Union[str, Sequence[str], None] = "4b9d1f72f9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_knowledge_base", sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_knowledge_base", sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_knowledge_base", sa.Column("score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("agent_knowledge_base", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("agent_knowledge_base", sa.Column("last_used_at", sa.DateTime(), nullable=True))
    op.alter_column("agent_knowledge_base", "usage_count", server_default=None)
    op.alter_column("agent_knowledge_base", "success_count", server_default=None)
    op.alter_column("agent_knowledge_base", "score", server_default=None)
    op.alter_column("agent_knowledge_base", "is_active", server_default=None)
    op.create_index("ix_agent_knowledge_base_score_active", "agent_knowledge_base", ["is_active", "score", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_knowledge_base_score_active", table_name="agent_knowledge_base")
    op.drop_column("agent_knowledge_base", "last_used_at")
    op.drop_column("agent_knowledge_base", "is_active")
    op.drop_column("agent_knowledge_base", "score")
    op.drop_column("agent_knowledge_base", "success_count")
    op.drop_column("agent_knowledge_base", "usage_count")

