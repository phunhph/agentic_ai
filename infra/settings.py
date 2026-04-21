import os


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = get_env_int("APP_PORT", 8000)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:123456@localhost:5432/agentic_store"
)

OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3:latest")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "gemma3:4b")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "llama3:latest")


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


ENABLE_DYNAMIC_METADATA_PLANNER = get_env_bool("ENABLE_DYNAMIC_METADATA_PLANNER", False)
ENABLE_MATRIX_GATE = get_env_bool("ENABLE_MATRIX_GATE", True)
MATRIX_MIN_TOOL_ACCURACY = float(os.getenv("MATRIX_MIN_TOOL_ACCURACY", "0.8"))
MATRIX_MIN_PATH_SUCCESS = float(os.getenv("MATRIX_MIN_PATH_SUCCESS", "0.75"))
MATRIX_MIN_CHOICE_SUCCESS = float(os.getenv("MATRIX_MIN_CHOICE_SUCCESS", "0.7"))
