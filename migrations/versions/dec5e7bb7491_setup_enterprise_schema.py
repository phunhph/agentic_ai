"""reset_to_dbjson_v2

Revision ID: dec5e7bb7491
Revises:
Create Date: 2026-04-20 15:09:35.598109
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from storage.schema_loader import load_schema_spec, map_sqlalchemy_type


revision: str = "dec5e7bb7491"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_all_tables() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    dialect = bind.dialect.name
    for table_name in table_names:
        if table_name == "alembic_version":
            continue
        if dialect == "postgresql":
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        else:
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}"'))


def upgrade() -> None:
    _drop_all_tables()
    spec = load_schema_spec()

    lookup_map: dict[tuple[str, str], tuple[str, str]] = {}
    for rel in spec.lookup_relations:
        lookup_map[(rel.from_table, rel.from_field)] = (rel.to_table, rel.to_field)

    for table in spec.tables:
        columns: list[sa.Column] = []
        for field in table.fields:
            is_pk = field.name == table.primary_key
            fk_target = lookup_map.get((table.name, field.name))
            fk = sa.ForeignKey(f"{fk_target[0]}.{fk_target[1]}") if fk_target else None
            columns.append(
                sa.Column(
                    field.name,
                    map_sqlalchemy_type(field.type),
                    fk,
                    primary_key=is_pk,
                    nullable=(False if is_pk else field.nullable),
                )
            )
        op.create_table(table.name, *columns)

    for rel in spec.choice_relations:
        left_table_pk = next(t.primary_key for t in spec.tables if t.name == rel.left_table)
        right_table_pk = next(t.primary_key for t in spec.tables if t.name == rel.right_table)
        left_type = next(
            f.type for t in spec.tables for f in t.fields if t.name == rel.left_table and f.name == left_table_pk
        )
        right_type = next(
            f.type for t in spec.tables for f in t.fields if t.name == rel.right_table and f.name == right_table_pk
        )
        op.create_table(
            rel.join_table,
            sa.Column(rel.left_fk, map_sqlalchemy_type(left_type), sa.ForeignKey(f"{rel.left_table}.{rel.left_fk}"), primary_key=True),
            sa.Column(rel.right_fk, map_sqlalchemy_type(right_type), sa.ForeignKey(f"{rel.right_table}.{rel.right_fk}"), primary_key=True),
        )


def downgrade() -> None:
    _drop_all_tables()
