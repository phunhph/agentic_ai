import sqlalchemy as sa

from storage.database import Base


class AgentKnowledgeBase(Base):
    __tablename__ = "agent_knowledge_base"

    id = sa.Column(sa.String(64), primary_key=True, nullable=False)
    context_key = sa.Column(sa.Text, nullable=True)
    user_role = sa.Column(sa.String(16), nullable=False, default="BUYER")
    domain = sa.Column(sa.String(32), nullable=False, default="general")
    original_query = sa.Column(sa.Text, nullable=False)
    wrong_answer_excerpt = sa.Column(sa.Text, nullable=True)
    correction_text = sa.Column(sa.Text, nullable=False)
    error_type = sa.Column(sa.String(64), nullable=True)
    resolved_intent = sa.Column(sa.String(64), nullable=True)
    resolved_entities_json = sa.Column(sa.Text, nullable=True)
    usage_count = sa.Column(sa.Integer, nullable=False, default=0)
    success_count = sa.Column(sa.Integer, nullable=False, default=0)
    score = sa.Column(sa.Float, nullable=False, default=0.0)
    is_active = sa.Column(sa.Boolean, nullable=False, default=True)
    last_used_at = sa.Column(sa.DateTime, nullable=True)
    created_at = sa.Column(sa.DateTime, nullable=False)
    updated_at = sa.Column(sa.DateTime, nullable=False)

