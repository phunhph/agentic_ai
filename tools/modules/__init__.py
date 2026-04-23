"""Public API for grouped tool modules."""

from tools.modules.accounts import compare_account_stats, create_account, get_account_360, get_account_overview, list_accounts
from tools.modules.contacts import compare_contact_stats_tool, create_contact, get_contact_details, list_contacts
from tools.modules.contracts import compare_contract_stats_tool, create_contract_tool, get_contract_details, list_contracts
from tools.modules.dynamic_query import dynamic_query
from tools.modules.opportunities import compare_opportunity_stats_tool, create_opportunity, list_opportunities

__all__ = [
    "list_accounts",
    "get_account_overview",
    "get_account_360",
    "create_account",
    "compare_account_stats",
    "list_contacts",
    "get_contact_details",
    "create_contact",
    "compare_contact_stats_tool",
    "list_contracts",
    "get_contract_details",
    "create_contract_tool",
    "compare_contract_stats_tool",
    "list_opportunities",
    "create_opportunity",
    "compare_opportunity_stats_tool",
    "dynamic_query",
]

