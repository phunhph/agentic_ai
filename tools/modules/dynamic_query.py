from __future__ import annotations

from typing import Any

from core.metadata_provider import get_metadata_provider
from storage.database import get_db
from storage.models import MODEL_MAP


def _infer_text_field(table_name: str) -> str | None:
    provider = get_metadata_provider()
    table = next((t for t in provider._schema.tables if t.name == table_name), None)
    if not table:
        return None
    preferred = [f.name for f in table.fields if "name" in f.name or f.name in {"fullname", "title"}]
    if preferred:
        return preferred[0]
    textual = [f.name for f in table.fields if f.type in {"text", "richtext"}]
    return textual[0] if textual else None


def _serialize_rows(table_name: str, rows: list[Any]) -> list[dict[str, Any]]:
    provider = get_metadata_provider()
    table = next((t for t in provider._schema.tables if t.name == table_name), None)
    if not table:
        return []
    field_names = [f.name for f in table.fields]
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for fn in field_names:
            item[fn] = getattr(row, fn, None)
        out.append(item)
    return out


def dynamic_query(plan: dict[str, Any]) -> dict[str, Any]:
    provider = get_metadata_provider()
    root_table = str(plan.get("root_table", "")).strip() or "hbl_account"
    include_tables = [str(x).strip() for x in (plan.get("include_tables") or []) if str(x).strip()]
    keyword = str(plan.get("keyword", "")).strip()
    limit = int(plan.get("limit", 20) or 20)
    id_filters = plan.get("id_filters") if isinstance(plan.get("id_filters"), dict) else {}
    filters = plan.get("filters") if isinstance(plan.get("filters"), list) else []
    limit = max(1, min(limit, 100))

    root_model = MODEL_MAP.get(root_table)
    if root_model is None:
        return {"error": f"Unsupported root_table: {root_table}"}

    root_text_field = _infer_text_field(root_table)
    with get_db() as db:
        query = db.query(root_model)
        for f, v in id_filters.items():
            if hasattr(root_model, str(f)) and v not in (None, "", [], {}):
                query = query.filter(getattr(root_model, str(f)) == v)

        joined_tables: set[str] = set()
        for filt in filters:
            if not isinstance(filt, dict):
                continue
            field = str(filt.get("field", "")).strip()
            op = str(filt.get("op", "contains")).strip().lower()
            value = filt.get("value")
            if "." not in field or value in (None, ""):
                continue
            table_name, col_name = field.split(".", 1)
            if table_name == root_table:
                if hasattr(root_model, col_name):
                    col = getattr(root_model, col_name)
                    query = query.filter(col == value) if op == "eq" else query.filter(col.ilike(f"%{value}%"))
                continue
            rel_model = MODEL_MAP.get(table_name)
            if rel_model is None:
                continue
            relation = next(
                (
                    rel
                    for rel in provider._schema.lookup_relations
                    if rel.from_table == root_table and rel.to_table == table_name
                ),
                None,
            )
            if relation is None:
                relation = next(
                    (
                        rel
                        for rel in provider._schema.lookup_relations
                        if rel.from_table == table_name and rel.to_table == root_table
                    ),
                    None,
                )
            if relation is None:
                continue
            if table_name not in joined_tables:
                if relation.from_table == root_table:
                    if hasattr(root_model, relation.from_field) and hasattr(rel_model, relation.to_field):
                        query = query.join(rel_model, getattr(root_model, relation.from_field) == getattr(rel_model, relation.to_field))
                        joined_tables.add(table_name)
                else:
                    if hasattr(rel_model, relation.from_field) and hasattr(root_model, relation.to_field):
                        query = query.join(rel_model, getattr(rel_model, relation.from_field) == getattr(root_model, relation.to_field))
                        joined_tables.add(table_name)
            if hasattr(rel_model, col_name):
                col = getattr(rel_model, col_name)
                query = query.filter(col == value) if op == "eq" else query.filter(col.ilike(f"%{value}%"))

        if keyword and root_text_field and hasattr(root_model, root_text_field):
            query = query.filter(getattr(root_model, root_text_field).ilike(f"%{keyword}%"))
        root_rows = query.limit(limit).all()
        if not root_rows:
            return {
                "root_table": root_table,
                "root_records": [],
                "related_records": {},
                "plan": {
                    "root_table": root_table,
                    "include_tables": include_tables,
                    "keyword": keyword,
                    "limit": limit,
                    "id_filters": id_filters,
                    "filters": filters,
                },
            }

        root_pk = next((t.primary_key for t in provider._schema.tables if t.name == root_table), "")
        root_ids = [getattr(r, root_pk, None) for r in root_rows if getattr(r, root_pk, None)]
        related_records: dict[str, list[dict[str, Any]]] = {}

        for table_name in include_tables:
            if table_name == root_table:
                continue
            model = MODEL_MAP.get(table_name)
            if model is None:
                continue
            rows: list[Any] = []

            direct = [
                rel
                for rel in provider._schema.lookup_relations
                if rel.from_table == table_name and rel.to_table == root_table
            ]
            for rel in direct:
                if hasattr(model, rel.from_field):
                    rows = (
                        db.query(model)
                        .filter(getattr(model, rel.from_field).in_(root_ids))
                        .limit(limit)
                        .all()
                    )
                    if rows:
                        break

            if not rows and root_table == "hbl_account" and table_name == "hbl_contract":
                opp_model = MODEL_MAP.get("hbl_opportunities")
                if opp_model is not None and hasattr(opp_model, "hbl_opportunities_accountid"):
                    opp_rows = (
                        db.query(opp_model)
                        .filter(getattr(opp_model, "hbl_opportunities_accountid").in_(root_ids))
                        .limit(limit)
                        .all()
                    )
                    opp_ids = [getattr(o, "hbl_opportunitiesid", None) for o in opp_rows if getattr(o, "hbl_opportunitiesid", None)]
                    if opp_ids and hasattr(model, "hbl_contract_opportunityid"):
                        rows = (
                            db.query(model)
                            .filter(getattr(model, "hbl_contract_opportunityid").in_(opp_ids))
                            .limit(limit)
                            .all()
                        )

            related_records[table_name] = _serialize_rows(table_name, rows)

        return {
            "root_table": root_table,
            "root_records": _serialize_rows(root_table, root_rows),
            "related_records": related_records,
            "plan": {
                "root_table": root_table,
                "include_tables": include_tables,
                "keyword": keyword,
                "limit": limit,
                "id_filters": id_filters,
                "filters": filters,
            },
        }


__all__ = ["dynamic_query"]
