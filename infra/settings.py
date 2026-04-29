import os


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = get_env_int("APP_PORT", 8000)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:123456@localhost:5432/agentic_store"
)

OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3:8b")
# Default reasoning model: use the smaller 8b variant for lower latency
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "llama3:8b")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "all-minilm:latest")


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_env_list(name: str, default_csv: str) -> list[str]:
    value = os.getenv(name, default_csv)
    return [x.strip() for x in str(value).split(",") if x.strip()]


ENABLE_DYNAMIC_METADATA_PLANNER = get_env_bool("ENABLE_DYNAMIC_METADATA_PLANNER", False)
ENABLE_MATRIX_GATE = get_env_bool("ENABLE_MATRIX_GATE", True)
MATRIX_MIN_TOOL_ACCURACY = get_env_float("MATRIX_MIN_TOOL_ACCURACY", 0.8)
MATRIX_MIN_PATH_SUCCESS = get_env_float("MATRIX_MIN_PATH_SUCCESS", 0.75)
MATRIX_MIN_CHOICE_SUCCESS = get_env_float("MATRIX_MIN_CHOICE_SUCCESS", 0.7)
MATRIX_MIN_ENTITY_MATCH_RATE = get_env_float("MATRIX_MIN_ENTITY_MATCH_RATE", 0.8)
MATRIX_DEFAULT_THRESHOLD = get_env_float("MATRIX_DEFAULT_THRESHOLD", 0.8)
MATRIX_METRICS_TO_CHECK = [
    m.strip()
    for m in os.getenv(
        "MATRIX_METRICS_TO_CHECK",
        "tool_accuracy,path_resolution_success,choice_constraint_success,entity_match_rate",
    ).split(",")
    if m.strip()
]

MATRIX_MAX_PATH_DEPTH = get_env_int("MATRIX_MAX_PATH_DEPTH", 4)
MATRIX_KNOWLEDGE_HITS_LIMIT = get_env_int("MATRIX_KNOWLEDGE_HITS_LIMIT", 3)
MATRIX_DEFAULT_TOOL = os.getenv("MATRIX_DEFAULT_TOOL", "list_accounts")
MATRIX_ALLOWED_TOOLS = {
    t.strip()
    for t in os.getenv(
        "MATRIX_ALLOWED_TOOLS",
        "list_accounts,create_account,compare_account_stats,list_contacts,get_contact_details,create_contact,compare_contact_stats,list_contracts,create_contract,compare_contract_stats,get_contract_details,list_opportunities,create_opportunity,compare_opportunity_stats,get_account_overview,get_account_360,dynamic_query,final_answer",
    ).split(",")
    if t.strip()
}

ENABLE_TRACE_TOKEN_STATS = get_env_bool("ENABLE_TRACE_TOKEN_STATS", True)
ENABLE_MATRIX_IO_TRACE = get_env_bool("ENABLE_MATRIX_IO_TRACE", True)
MATRIX_CASE_PRIOR_WEIGHT = get_env_float("MATRIX_CASE_PRIOR_WEIGHT", 4.0)
MATRIX_CASE_MIN_SIMILARITY = get_env_float("MATRIX_CASE_MIN_SIMILARITY", 0.35)
STRICT_LEARNED_ONLY_MODE = get_env_bool("STRICT_LEARNED_ONLY_MODE", True)
STRICT_MIN_EVIDENCE_SIMILARITY = get_env_float("STRICT_MIN_EVIDENCE_SIMILARITY", 0.45)
UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE = get_env_float("UNCERTAINTY_BASE_ASK_CLARIFY_EVIDENCE", 0.45)
UNCERTAINTY_LEARNING_SCORE_BONUS_MAX = get_env_float("UNCERTAINTY_LEARNING_SCORE_BONUS_MAX", 0.15)
UNCERTAINTY_CASE_SUCCESS_BONUS_MAX = get_env_float("UNCERTAINTY_CASE_SUCCESS_BONUS_MAX", 0.1)
LEARNING_TEXT_MATCH_MIN = get_env_float("LEARNING_TEXT_MATCH_MIN", 0.25)
LEARNING_SCORE_WEIGHT = get_env_float("LEARNING_SCORE_WEIGHT", 0.6)
LEARNING_TEXT_WEIGHT = get_env_float("LEARNING_TEXT_WEIGHT", 0.4)
LEARNING_FINAL_MATCH_MIN = get_env_float("LEARNING_FINAL_MATCH_MIN", 0.35)
AUTO_MATRIX_LEARNING = get_env_bool("AUTO_MATRIX_LEARNING", True)
AUTO_MATRIX_EVAL_REFRESH = get_env_bool("AUTO_MATRIX_EVAL_REFRESH", True)

RAG_EMBEDDING_CACHE_PATH = os.getenv("RAG_EMBEDDING_CACHE_PATH", "storage/schema_embedding_cache.json")
RAG_FORCE_REBUILD = get_env_bool("RAG_FORCE_REBUILD", False)
LEARNING_STORE_DIR = os.getenv("LEARNING_STORE_DIR", "storage/learning")


# Response templates and runtime flags
ENABLE_DEBUG_LOGS = get_env_bool("ENABLE_DEBUG_LOGS", False)
RESPONSES_FILE = os.getenv("RESPONSES_FILE", "infra/responses.json")

def load_response_templates() -> dict:
    import json
    try:
        with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # sensible defaults
        return {
            "clarify_person_question": "Bạn có thể cho tôi biết họ và tên đầy đủ hoặc email của người bán hàng '{candidate}' được không?",
            "find_one": "Dạ, Cindy tìm thấy 1 {entity_label} tên {name}.",
            "find_multiple": "Dạ, Cindy đã tìm thấy {count} {entity_label}. Ví dụ: {examples}.",
            "not_found": "Dạ, Cindy đã tìm nhưng chưa thấy {entity_label} phù hợp cho '{query}'. Bạn muốn thử từ khoá khác không ạ?",
            "generic_processed": "Dạ, Cindy đã xử lý yêu cầu '{query}'. Kết quả: {count}.",
        }

RESPONSE_TEMPLATES = load_response_templates()

PERCEPTION_CREATE_VERBS = get_env_list("PERCEPTION_CREATE_VERBS", "thêm,tao,tạo,create,new")
PERCEPTION_COMPARE_VERBS = get_env_list("PERCEPTION_COMPARE_VERBS", "so sánh,thống kê,compare,ranking,xếp hạng")
PERCEPTION_GENERIC_LIST_KEYWORDS = set(
    get_env_list(
        "PERCEPTION_GENERIC_LIST_KEYWORDS",
        "list,account,accounts,contact,contacts,contract,contracts,opportunity,opportunities,danh sach,danh sách,"
        "danh sach account,danh sách account,danh sach contact,danh sách contact,danh sach contract,danh sách contract,"
        "danh sach opportunity,danh sách opportunity,list account,list accounts,list contact,list contacts,list contract,"
        "list contracts,list opportunity,list opportunities,liet ke account,liệt kê account,lay danh sach account,lấy danh sách account",
    )
)
PLANNER_GENERIC_LIST_KEYWORDS = set(
    get_env_list(
        "PLANNER_GENERIC_LIST_KEYWORDS",
        "list,account,accounts,contact,contacts,contract,contracts,opportunity,opportunities,list account,list accounts,"
        "list contact,list contacts,list contract,list contracts,list opportunity,list opportunities,danh sach,danh sách,"
        "danh sach account,danh sách account,danh sach contact,danh sách contact,danh sach contract,danh sách contract,"
        "danh sach opportunity,danh sách opportunity",
    )
)
PLANNER_COMPLEXITY_BUDGET = get_env_int("PLANNER_COMPLEXITY_BUDGET", 16)
V2_GATE_MIN_PLAN_CORRECTNESS = get_env_float("V2_GATE_MIN_PLAN_CORRECTNESS", 0.8)
V2_GATE_MIN_FILTER_FIDELITY = get_env_float("V2_GATE_MIN_FILTER_FIDELITY", 0.8)
V2_GATE_MIN_JOIN_CORRECTNESS = get_env_float("V2_GATE_MIN_JOIN_CORRECTNESS", 0.8)
