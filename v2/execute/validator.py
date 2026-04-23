from __future__ import annotations

from v2.contracts import ExecutionPlan, ValidationResult
from v2.metadata import load_v2_metadata

ALLOWED_FILTER_OPS = {"eq", "contains", "in", "range"}


def validate_execution_plan(plan: ExecutionPlan) -> ValidationResult:
    metadata = load_v2_metadata()
    table_names = metadata.tables
    table_fields = metadata.table_fields
    errors: list[str] = []
    warnings: list[str] = []

    if plan.root_table not in table_names:
        errors.append(f"Unknown root_table: {plan.root_table}")

    if plan.limit < 0:
        errors.append("limit must be >= 0 (0 means no limit)")

    for flt in plan.where_filters:
        if flt.op not in ALLOWED_FILTER_OPS:
            errors.append(f"Unsupported filter op: {flt.op}")
        field = str(flt.field or "").strip()
        if not field:
            errors.append("Filter field cannot be empty")
            continue
        if "." in field:
            table, col = field.split(".", 1)
            if table not in table_names:
                errors.append(f"Unknown filter table: {table}")
            elif col not in table_fields.get(table, set()):
                errors.append(f"Unknown filter column: {table}.{col}")
        else:
            if field not in table_fields.get(plan.root_table, set()):
                errors.append(f"Unknown filter column in root_table: {plan.root_table}.{field}")

    for hop in plan.join_path:
        if not isinstance(hop, dict):
            errors.append("join_path entry must be dict")
            continue
        from_table = str(hop.get("from_table", ""))
        to_table = str(hop.get("to_table", ""))
        if from_table not in table_names or to_table not in table_names:
            errors.append(f"Invalid join path: {from_table}->{to_table}")
        elif (from_table, to_table) not in metadata.lookup_edges:
            errors.append(f"Join path not found in metadata: {from_table}->{to_table}")

    if plan.limit > 200:
        warnings.append("limit is high; consider lowering to improve latency")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)
