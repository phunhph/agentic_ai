import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def _load_env_file() -> None:
    """
    Lightweight .env loader so scripts can run directly without shell export.
    Priority:
    1) Existing process env (do not override)
    2) Root .env
    """
    root_env = Path(".env")
    if not root_env.exists():
        return
    for raw_line in root_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class DataverseConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    env_url: str
    api_version: str = "v9.2"
    timeout_seconds: int = 30

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    @property
    def scope(self) -> str:
        return f"{self.env_url}/.default"

    @property
    def api_base(self) -> str:
        return f"{self.env_url}/api/data/{self.api_version}"


class DataverseClient:
    def __init__(self, config: DataverseConfig) -> None:
        self.config = config
        self._access_token = ""

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", {})
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Accept", "application/json")
        headers.setdefault("OData-MaxVersion", "4.0")
        headers.setdefault("OData-Version", "4.0")
        # Ask Dataverse to include formatted labels for choice/lookups.
        headers.setdefault('Prefer', 'odata.include-annotations="OData.Community.Display.V1.FormattedValue"')
        resp = requests.request(
            method,
            url,
            headers=headers,
            timeout=self.config.timeout_seconds,
            **kwargs,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = resp.text[:1000]
            except Exception:
                detail = ""
            if detail:
                raise requests.HTTPError(f"{exc}. Response: {detail}", response=resp) from exc
            raise
        return resp

    def get_access_token(self) -> str:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "scope": self.config.scope,
        }
        resp = requests.post(self.config.token_url, data=payload, timeout=self.config.timeout_seconds)
        resp.raise_for_status()
        token = resp.json().get("access_token", "")
        if not token:
            raise RuntimeError("Cannot get Dataverse access token")
        self._access_token = token
        return token

    def list_tables_metadata(self, table_prefix: str = "", include_tables: set[str] | None = None) -> list[dict[str, Any]]:
        """
        Read table metadata from EntityDefinitions.
        """
        select = "LogicalName,SchemaName,PrimaryIdAttribute,PrimaryNameAttribute,EntitySetName"
        url = f"{self.config.api_base}/EntityDefinitions?$select={select}"
        rows: list[dict[str, Any]] = []
        while url:
            data = self._request("GET", url).json()
            values = data.get("value", [])
            for item in values:
                logical = str(item.get("LogicalName", ""))
                if table_prefix and not logical.startswith(table_prefix):
                    continue
                if include_tables is not None and logical not in include_tables:
                    continue
                rows.append(
                    {
                        "name": logical,
                        "schema_name": item.get("SchemaName"),
                        "entity_set_name": item.get("EntitySetName"),
                        "primary_key": item.get("PrimaryIdAttribute"),
                        "primary_name": item.get("PrimaryNameAttribute"),
                    }
                )
            url = data.get("@odata.nextLink")
        return rows

    def list_table_columns(self, table_logical_name: str) -> list[dict[str, Any]]:
        # Dataverse metadata shape can differ by attribute subtype.
        # Querying Attributes without a strict $select is more compatible.
        url = (
            f"{self.config.api_base}/EntityDefinitions(LogicalName='{table_logical_name}')"
            f"/Attributes"
        )
        values: list[dict[str, Any]] = []
        while url:
            data = self._request("GET", url).json()
            page_values = data.get("value", [])
            if isinstance(page_values, list):
                values.extend([x for x in page_values if isinstance(x, dict)])
            url = data.get("@odata.nextLink")
        out: list[dict[str, Any]] = []
        for item in values:
            required_level = ""
            rl = item.get("RequiredLevel")
            if isinstance(rl, dict):
                required_level = str(rl.get("Value", ""))
            out.append(
                {
                    "name": item.get("LogicalName"),
                    "attribute_type": item.get("AttributeType"),
                    "required_level": required_level,
                    "is_valid_for_read": item.get("IsValidForRead"),
                    "max_length": item.get("MaxLength"),
                    "precision": item.get("Precision"),
                }
            )
        return out

    def fetch_records_page(
        self,
        entity_set_name: str,
        select_columns: list[str] | None = None,
        filter_clause: str = "",
        order_by: str = "",
        top: int = 500,
        next_link: str = "",
    ) -> dict[str, Any]:
        if next_link:
            return self._request("GET", next_link).json()

        selected = list(dict.fromkeys(select_columns or []))
        invalid_prop_pattern = r"Could not find a property named '([^']+)'"

        while True:
            query: list[str] = [f"$top={int(top)}"]
            if selected:
                query.append(f"$select={','.join(selected)}")
            if filter_clause:
                query.append(f"$filter={filter_clause}")
            if order_by:
                query.append(f"$orderby={order_by}")
            url = f"{self.config.api_base}/{entity_set_name}?{'&'.join(query)}"

            try:
                return self._request("GET", url).json()
            except requests.HTTPError as exc:
                detail = str(exc)
                match = re.search(invalid_prop_pattern, detail)
                if not match:
                    raise
                bad_prop = match.group(1).strip()
                if not bad_prop or bad_prop not in selected:
                    raise
                print(f"[DataverseClient] Skip invalid select property: {bad_prop}")
                selected = [x for x in selected if x != bad_prop]
                if not selected:
                    # No valid select columns left; fallback to default payload.
                    fallback_url = f"{self.config.api_base}/{entity_set_name}?$top={int(top)}"
                    if filter_clause:
                        fallback_url += f"&$filter={filter_clause}"
                    if order_by:
                        fallback_url += f"&$orderby={order_by}"
                    return self._request("GET", fallback_url).json()


def _build_config_from_env() -> DataverseConfig:
    _load_env_file()
    required = [
        "DATAVERSE_TENANT_ID",
        "DATAVERSE_CLIENT_ID",
        "DATAVERSE_CLIENT_SECRET",
        "DATAVERSE_ENV_URL",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
    return DataverseConfig(
        tenant_id=os.environ["DATAVERSE_TENANT_ID"],
        client_id=os.environ["DATAVERSE_CLIENT_ID"],
        client_secret=os.environ["DATAVERSE_CLIENT_SECRET"],
        env_url=os.environ["DATAVERSE_ENV_URL"].rstrip("/"),
    )


def _cmd_export_schema(args: argparse.Namespace) -> None:
    config = _build_config_from_env()
    client = DataverseClient(config)
    client.get_access_token()
    include_tables: set[str] | None = None
    if args.tables:
        include_tables = {x.strip() for x in str(args.tables).split(",") if x.strip()}
    tables = client.list_tables_metadata(table_prefix=args.table_prefix, include_tables=include_tables)
    table_limit = int(args.table_limit)
    if table_limit > 0:
        tables = tables[:table_limit]

    for table in tables:
        table["fields"] = client.list_table_columns(table["name"])

    payload = {
        "source": "dataverse",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "table_count": len(tables),
        "tables": tables,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported schema metadata to {output}")


def _cmd_smoke(args: argparse.Namespace) -> None:
    config = _build_config_from_env()
    client = DataverseClient(config)
    client.get_access_token()
    include_tables: set[str] | None = None
    if args.tables:
        include_tables = {x.strip() for x in str(args.tables).split(",") if x.strip()}
    tables = client.list_tables_metadata(table_prefix=args.table_prefix, include_tables=include_tables)
    print(f"OK. Found {len(tables)} tables")
    if tables:
        print(f"First table: {tables[0]['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataverse client helper CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    smoke = sub.add_parser("smoke", help="Check auth and list tables")
    smoke.add_argument("--table-prefix", default="")
    smoke.add_argument("--tables", default="", help="Comma-separated logical table names")
    smoke.set_defaults(func=_cmd_smoke)

    export = sub.add_parser("export-schema", help="Export schema metadata from Dataverse")
    export.add_argument("--table-prefix", default="")
    export.add_argument("--tables", default="", help="Comma-separated logical table names")
    export.add_argument("--table-limit", type=int, default=0, help="0 means no limit")
    export.add_argument(
        "--output",
        default="v3/storage/dataverse_schema_snapshots/latest_schema_snapshot.json",
    )
    export.set_defaults(func=_cmd_export_schema)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
