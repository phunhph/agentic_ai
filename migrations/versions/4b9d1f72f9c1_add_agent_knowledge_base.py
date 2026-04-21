"""add_agent_knowledge_base

Revision ID: 4b9d1f72f9c1
Revises: dec5e7bb7491
Create Date: 2026-04-21 23:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b9d1f72f9c1"
down_revision: Union[str, Sequence[str], None] = "dec5e7bb7491"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_knowledge_base",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("context_key", sa.Text(), nullable=True),
        sa.Column("user_role", sa.String(length=16), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("wrong_answer_excerpt", sa.Text(), nullable=True),
        sa.Column("correction_text", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("resolved_intent", sa.String(length=64), nullable=True),
        sa.Column("resolved_entities_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_knowledge_base_role_domain_created",
        "agent_knowledge_base",
        ["user_role", "domain", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_knowledge_base_role_domain_created", table_name="agent_knowledge_base")
    op.drop_table("agent_knowledge_base")

