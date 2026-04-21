from infra.context import normalize_role


ROLE_TOOL_ALLOWLIST = {
    "BUYER": {
        "list_accounts",
        "list_contracts",
        "get_contract_details",
        "final_answer",
    },
    "ADMIN": {
        "list_accounts",
        "get_account_overview",
        "list_contracts",
        "get_contract_details",
        "final_answer",
    },
}


def is_tool_allowed(role: str, tool: str) -> tuple[bool, str]:
    normalized_role = normalize_role(role)
    allowed_tools = ROLE_TOOL_ALLOWLIST.get(normalized_role, set())
    if tool in allowed_tools:
        return True, ""
    return (
        False,
        f"Tool '{tool}' không được phép cho role {normalized_role}. Allowed: {sorted(allowed_tools)}",
    )
