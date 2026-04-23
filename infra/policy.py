from infra.context import normalize_role


ROLE_TOOL_ALLOWLIST = {
    "DEFAULT": {
        "list_accounts",
        "create_account",
        "compare_account_stats",
        "list_contacts",
        "get_contact_details",
        "create_contact",
        "compare_contact_stats",
        "get_account_overview",
        "get_account_360",
        "list_contracts",
        "create_contract",
        "compare_contract_stats",
        "get_contract_details",
        "list_opportunities",
        "create_opportunity",
        "compare_opportunity_stats",
        "dynamic_query",
        "final_answer",
    }
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
