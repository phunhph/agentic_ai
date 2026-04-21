import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    nullable: bool = True


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: str
    fields: list[FieldSpec]


@dataclass(frozen=True)
class LookupRelationSpec:
    from_table: str
    from_field: str
    to_table: str
    to_field: str


@dataclass(frozen=True)
class ChoiceRelationSpec:
    left_table: str
    right_table: str
    join_table: str
    left_fk: str
    right_fk: str
    right_group: str


@dataclass(frozen=True)
class DbSchemaSpec:
    version: int
    tables: list[TableSpec]
    lookup_relations: list[LookupRelationSpec]
    choice_relations: list[ChoiceRelationSpec]
    choice_options: dict[str, list[dict[str, str]]]


TYPE_MAP: dict[str, type[sa.types.TypeEngine[Any]]] = {
    "uuid": sa.String,
    "text": sa.Text,
    "richtext": sa.Text,
    "decimal": sa.Float,
    "int": sa.Integer,
    "datetime": sa.DateTime,
}


def _db_json_path() -> Path:
    return Path(__file__).resolve().parent.parent / "db.json"


def map_sqlalchemy_type(type_name: str) -> sa.types.TypeEngine[Any]:
    normalized = (type_name or "").strip().lower()
    if normalized not in TYPE_MAP:
        raise ValueError(f"Unsupported field type: {type_name}")
    mapped = TYPE_MAP[normalized]
    if mapped is sa.String:
        return sa.String(64)
    return mapped()


def load_schema_spec(path: Path | None = None) -> DbSchemaSpec:
    schema_path = path or _db_json_path()
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    return _parse_spec(raw)


def _parse_spec(raw: dict[str, Any]) -> DbSchemaSpec:
    tables = [
        TableSpec(
            name=t["name"],
            primary_key=t["primary_key"],
            fields=[FieldSpec(**f) for f in t["fields"]],
        )
        for t in raw.get("tables", [])
    ]
    lookups = [LookupRelationSpec(**r) for r in raw.get("relations", {}).get("lookup", [])]
    choices = [ChoiceRelationSpec(**r) for r in raw.get("relations", {}).get("choice", [])]
    choice_options = raw.get("choice_options", {})

    spec = DbSchemaSpec(
        version=int(raw.get("version", 0)),
        tables=tables,
        lookup_relations=lookups,
        choice_relations=choices,
        choice_options=choice_options,
    )
    validate_schema_spec(spec)
    return spec


def validate_schema_spec(spec: DbSchemaSpec) -> None:
    if spec.version < 2:
        raise ValueError("db.json must use schema version >= 2")

    table_names = [t.name for t in spec.tables]
    if len(table_names) != len(set(table_names)):
        raise ValueError("Duplicate table names in schema")

    table_map = {t.name: t for t in spec.tables}
    for table in spec.tables:
        field_names = [f.name for f in table.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError(f"Duplicate fields in table {table.name}")
        if table.primary_key not in field_names:
            raise ValueError(f"Primary key '{table.primary_key}' missing in table {table.name}")

    for rel in spec.lookup_relations:
        if rel.from_table not in table_map or rel.to_table not in table_map:
            raise ValueError(f"Invalid lookup table reference: {rel}")
        from_fields = {f.name for f in table_map[rel.from_table].fields}
        to_fields = {f.name for f in table_map[rel.to_table].fields}
        if rel.from_field not in from_fields:
            raise ValueError(f"Lookup from_field missing: {rel.from_table}.{rel.from_field}")
        if rel.to_field not in to_fields:
            raise ValueError(f"Lookup to_field missing: {rel.to_table}.{rel.to_field}")

    for rel in spec.choice_relations:
        if not rel.join_table:
            raise ValueError(f"Choice relation missing join_table: {rel}")
        if rel.left_table not in table_map or rel.right_table not in table_map:
            raise ValueError(f"Invalid choice table reference: {rel}")
        left_fields = {f.name for f in table_map[rel.left_table].fields}
        right_fields = {f.name for f in table_map[rel.right_table].fields}
        if rel.left_fk not in left_fields:
            raise ValueError(f"Choice left_fk missing: {rel.left_table}.{rel.left_fk}")
        if rel.right_fk not in right_fields:
            raise ValueError(f"Choice right_fk missing: {rel.right_table}.{rel.right_fk}")
        if rel.right_group not in spec.choice_options:
            raise ValueError(f"Choice right_group '{rel.right_group}' missing in choice_options")
