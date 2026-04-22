"""Public API for grouped repository modules."""

from storage.repositories.modules.accounts import (
    compare_account_owner_stats,
    count_accounts,
    create_account,
    search_accounts,
    search_accounts_with_rollup,
)
from storage.repositories.modules.contacts import compare_contact_stats, create_contact as create_contact_repo, list_contacts_with_context
from storage.repositories.modules.contracts import (
    compare_contract_stats,
    create_contract,
    get_contract,
    get_contract_details_with_context,
    get_opportunity_name,
    list_contracts,
    list_contracts_with_context,
)

__all__ = [
    "search_accounts",
    "count_accounts",
    "search_accounts_with_rollup",
    "create_account",
    "compare_account_owner_stats",
    "list_contacts_with_context",
    "create_contact_repo",
    "compare_contact_stats",
    "list_contracts",
    "get_contract",
    "get_opportunity_name",
    "list_contracts_with_context",
    "get_contract_details_with_context",
    "create_contract",
    "compare_contract_stats",
]

