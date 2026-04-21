from storage.models.agent_knowledge_base import AgentKnowledgeBase
from storage.models.choice_option import ChoiceOption
from storage.models.hbl_account import HblAccount
from storage.models.hbl_contact import HblContact
from storage.models.hbl_contract import HblContract
from storage.models.hbl_opportunities import HblOpportunities
from storage.models.systemuser import SystemUser

MODEL_MAP = {
    "agent_knowledge_base": AgentKnowledgeBase,
    "systemuser": SystemUser,
    "hbl_account": HblAccount,
    "hbl_contact": HblContact,
    "hbl_opportunities": HblOpportunities,
    "hbl_contract": HblContract,
    "choice_option": ChoiceOption,
}
