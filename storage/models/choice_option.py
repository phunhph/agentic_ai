import sqlalchemy as sa

from storage.database import Base


class ChoiceOption(Base):
    __tablename__ = "choice_option"

    choice_optionid = sa.Column(sa.String(64), primary_key=True, nullable=False)
    choice_group = sa.Column(sa.Text, nullable=False)
    choice_code = sa.Column(sa.Text, nullable=False)
    choice_label = sa.Column(sa.Text, nullable=False)
