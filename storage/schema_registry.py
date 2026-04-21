from __future__ import annotations

from dataclasses import dataclass

from storage.schema_loader import load_schema_spec


@dataclass(frozen=True)
class TableRegistry:
    name: str
    primary_key: str
    fields: set[str]


@dataclass(frozen=True)
class SchemaRegistry:
    tables: dict[str, TableRegistry]
    aliases: dict[str, str]

    def has_field(self, table: str, field: str) -> bool:
        t = self.tables.get(table)
        return bool(t and field in t.fields)


def _build_aliases() -> dict[str, str]:
    # Alias xác định field canonical theo domain CRM
    return {
        "account": "hbl_account.hbl_account_name",
        "account_name": "hbl_account.hbl_account_name",
        "ten account": "hbl_account.hbl_account_name",
        "tên account": "hbl_account.hbl_account_name",
        "ten khach hang": "hbl_account.hbl_account_name",
        "tên khách hàng": "hbl_account.hbl_account_name",
        "khach hang": "hbl_account.hbl_account_name",
        "customer": "hbl_account.hbl_account_name",
        "contract": "hbl_contract.hbl_contract_name",
        "contract_name": "hbl_contract.hbl_contract_name",
        "hop dong": "hbl_contract.hbl_contract_name",
        "hợp đồng": "hbl_contract.hbl_contract_name",
        "contact": "hbl_contact.hbl_contact_name",
        "contact_name": "hbl_contact.hbl_contact_name",
        "opportunity": "hbl_opportunities.hbl_opportunities_name",
        "opportunity_name": "hbl_opportunities.hbl_opportunities_name",
        "status": "choice_option.choice_label",
        "contract_id": "hbl_contract.hbl_contractid",
        "id": "hbl_contract.hbl_contractid",
    }


def build_schema_registry() -> SchemaRegistry:
    spec = load_schema_spec()
    tables: dict[str, TableRegistry] = {}
    for t in spec.tables:
        fields = {f.name for f in t.fields}
        tables[t.name] = TableRegistry(name=t.name, primary_key=t.primary_key, fields=fields)
    return SchemaRegistry(tables=tables, aliases=_build_aliases())


REGISTRY = build_schema_registry()
