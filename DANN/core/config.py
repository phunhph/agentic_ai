import os

# LLM endpoint (local or remote)
LLM_URL = os.environ.get('DANN_LLM_URL', 'http://localhost:11434/api/generate')

# Database URL (Postgres by default)
DATABASE_URL = os.environ.get('DANN_DATABASE_URL', 'postgresql://postgres:123456@localhost:5432/agentic_store')

# App settings
DEFAULT_MODEL = os.environ.get('DANN_DEFAULT_MODEL', 'llama3')
