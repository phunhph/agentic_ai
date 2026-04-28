from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class V2Metadata:
    tables: set[str]
    lookup_edges: set[tuple[str, str]]
    table_fields: dict[str, set[str]]


class MetadataProvider:
    def __init__(self, db_json_path: str = "db.json"):
        self.metadata = load_v2_metadata(db_json_path)
        self._alias_map = self._build_alias_map()

    def _build_alias_map(self) -> dict[str, str]:
        am: dict[str, str] = {}
        for table in self.metadata.tables:
            am[table] = table
            # Clean name for alias (e.g. hbl_account -> account)
            clean = table.replace("hbl_", "").replace("cr987_", "").replace("mc_", "").strip("_")
            am[clean] = table
            # Handle plurals
            if clean.endswith("ies"):
                am[clean[:-3] + "y"] = table
            elif clean.endswith("s"):
                am[clean[:-1]] = table
            else:
                am[clean + "s"] = table

        # Add human-friendly aliases for key system tables to match PRD/UX language.
        # NOTE: keep aliases lowercase; parser performs lowercase matching.
        if "systemuser" in self.metadata.tables:
            sys = "systemuser"
            for alias in [
                "user",
                "users",
                "system user",
                "system users",
                "sales",
                "sale",
                "sales rep",
                "sales reps",
                "presales",
                "nhan vien",
                "nhân viên",
                "nhan vien kinh doanh",
                "nhân viên kinh doanh",
                "nhan su",
                "nhân sự",
            ]:
                am[str(alias).strip().lower()] = sys

        # Common shorthand/typos from real chat logs (space_messages.json)
        # Keep minimal and domain-generic.
        if "hbl_opportunities" in self.metadata.tables:
            for alias in ["opps", "ops", "op", "opportunity", "opportunities", "cơ hội", "co hoi"]:
                am[str(alias).strip().lower()] = "hbl_opportunities"
        return am

    def get_table_by_alias(self, alias: str) -> str | None:
        return self._alias_map.get(str(alias).lower().strip())

    def iter_alias_items(self) -> list[tuple[str, str]]:
        return sorted(self._alias_map.items(), key=lambda x: (len(x[0]), x[0]))

    def get_all_aliases(self) -> list[str]:
        return sorted(self._alias_map.keys())

    def is_valid_table(self, table_name: str) -> bool:
        return table_name in self.metadata.tables

    def get_fields(self, table_name: str) -> set[str]:
        return self.metadata.table_fields.get(table_name, set())

    def get_default_root_table(self) -> str:
        candidates = ["hbl_account", "hbl_contact", "hbl_opportunities", "hbl_contract"]
        for c in candidates:
            if c in self.metadata.tables:
                return c
        all_tables = self.get_all_tables()
        return all_tables[0] if all_tables else "hbl_account"

    def get_identity_priority_fields(self, table_name: str) -> list[str]:
        fields = self.get_fields(table_name)
        if not fields:
            return []
        if table_name == "systemuser":
            preferred = [
                "fullname",
                "domainname",
                "internalemailaddress",
                "firstname",
                "lastname",
                "nickname",
            ]
            return [f for f in preferred if f in fields]
        direct = f"{table_name}_name"
        preferred: list[str] = []
        if direct in fields:
            preferred.append(direct)
        preferred.extend(
            f
            for f in ["name", "fullname", "full_name", "title"]
            if f in fields and f not in preferred
        )
        preferred.extend(
            sorted(
                f for f in fields if f.endswith("_name") and f not in preferred
            )
        )
        return preferred

    def resolve_identity_field(self, table_name: str) -> str | None:
        fields = self.get_fields(table_name)
        if not fields:
            return None
        prioritized = self.get_identity_priority_fields(table_name)
        if prioritized:
            return prioritized[0]
        label_like = sorted([f for f in fields if "label" in f or "title" in f])
        if label_like:
            return label_like[0]
        return sorted(fields)[0]

    def resolve_column_alias(self, table_name: str, raw_col: str) -> str | None:
        fields = self.get_fields(table_name)
        col = str(raw_col or "").strip()
        if not fields:
            return None
        if not col:
            return self.resolve_identity_field(table_name)
        if col in fields:
            # Prefer label companion for choice-like fields so natural-language
            # filters (e.g. "market Japan") compare against readable labels.
            if not col.endswith("_label") and f"{col}_label" in fields:
                return f"{col}_label"
            return col
        if col.lower() == "name":
            return self.resolve_identity_field(table_name)
        candidates = [f for f in fields if f.endswith(f"_{col}")]
        if len(candidates) == 1:
            pick = candidates[0]
            if not pick.endswith("_label") and f"{pick}_label" in fields:
                return f"{pick}_label"
            return pick
        contains = [f for f in fields if col in f]
        if contains:
            # Ambiguous case: prefer *_label field first.
            label_contains = [f for f in contains if f.endswith("_label")]
            if len(label_contains) == 1:
                return label_contains[0]
            if len(contains) == 1:
                pick = contains[0]
                if not pick.endswith("_label") and f"{pick}_label" in fields:
                    return f"{pick}_label"
                return pick
        return None

    def resolve_cross_table_identity(self, root_table: str, raw_col: str) -> tuple[str, str] | None:
        owners: list[tuple[str, str]] = []
        for table_name in self.get_all_tables():
            resolved = self.resolve_column_alias(table_name, raw_col)
            if resolved:
                owners.append((table_name, resolved))
        if len(owners) == 1:
            return owners[0]
        if owners:
            # Prefer root table when ambiguity exists.
            for t, c in owners:
                if t == root_table:
                    return (t, c)
        return None

    def normalize_filter_field(self, root_table: str, raw_field: str) -> str:
        field = str(raw_field or "").strip()
        if not field:
            identity = self.resolve_identity_field(root_table)
            return f"{root_table}.{identity}" if identity else f"{root_table}.keyword"
        if "." in field:
            table_name, col_name = field.split(".", 1)
            table_name = table_name.strip() or root_table
            col_name = col_name.strip()
            resolved = self.resolve_column_alias(table_name, col_name)
            if resolved:
                return f"{table_name}.{resolved}"
            cross = self.resolve_cross_table_identity(root_table, col_name)
            if cross:
                return f"{cross[0]}.{cross[1]}"
            identity = self.resolve_identity_field(table_name)
            return f"{table_name}.{identity}" if identity else f"{table_name}.keyword"
        resolved = self.resolve_column_alias(root_table, field)
        if resolved:
            return f"{root_table}.{resolved}"
        identity = self.resolve_identity_field(root_table)
        return f"{root_table}.{identity}" if identity else f"{root_table}.keyword"

    def resolve_bant_column(self, table_name: str, bant_key: str) -> str | None:
        """Dynamically resolve BANT keys (budget, authority, need, timeline) to columns."""
        fields = self.get_fields(table_name)
        # 1. Direct match with prefix
        patterns = {
            "budget": ["estimated_value", "annual_it_budget", "budget"],
            "authority": ["bant_authority", "authority"],
            "need": ["bant_need", "need"],
            "timeline": ["bant_time", "time", "deadline"],
        }
        candidates = patterns.get(bant_key.lower(), [])
        for c in candidates:
            # Try exact, then try with table prefix
            if c in fields: return c
            table_prefix_c = f"{table_name}_{c}"
            if table_prefix_c in fields: return table_prefix_c
            # Try metadata clean match
            for f in fields:
                if c in f: return f
        return None

    def get_all_tables(self) -> list[str]:
        return sorted(list(self.metadata.tables))


def load_v2_metadata(db_json_path: str = "db.json") -> V2Metadata:
    path = Path(db_json_path)
    if not path.exists():
        return V2Metadata(tables=set(), lookup_edges=set(), table_fields={})
    raw = json.loads(path.read_text(encoding="utf-8"))
    tables = {str(t.get("name", "")).strip() for t in raw.get("tables", []) if isinstance(t, dict)}
    table_fields: dict[str, set[str]] = {}
    for t in raw.get("tables", []) or []:
        if not isinstance(t, dict):
            continue
        table_name = str(t.get("name", "")).strip()
        if not table_name:
            continue
        fields = {
            str(f.get("name", "")).strip()
            for f in (t.get("fields", []) or [])
            if isinstance(f, dict) and str(f.get("name", "")).strip()
        }
        table_fields[table_name] = fields
    lookup_edges: set[tuple[str, str]] = set()
    for rel in raw.get("relations", {}).get("lookup", []) or []:
        if not isinstance(rel, dict):
            continue
        from_table = str(rel.get("from_table", "")).strip()
        to_table = str(rel.get("to_table", "")).strip()
        if from_table and to_table:
            lookup_edges.add((from_table, to_table))
            lookup_edges.add((to_table, from_table))
    return V2Metadata(tables=tables, lookup_edges=lookup_edges, table_fields=table_fields)
