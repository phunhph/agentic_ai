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
    "DATABASE_URL", "postgresql://postgres:123456@localhost:5432/agent_db"
)

OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3:latest")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "gemma3:4b")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "llama3:latest")
