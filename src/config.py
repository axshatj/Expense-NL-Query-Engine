import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DEFAULT_DB_PATH = BASE_DIR / "data" / "expense_tracker.db"
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))

# Ensure data directory exists
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
if OPENAI_BASE_URL.endswith("/chat/completions"):
    OPENAI_BASE_URL = OPENAI_BASE_URL[:-17] # strip "/chat/completions"
if OPENAI_BASE_URL.endswith("/chat/completions/"):
    OPENAI_BASE_URL = OPENAI_BASE_URL[:-18]
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Server & Application Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Configure root logger globally
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True
)

# Fixed Category Taxonomy.env
VALID_CATEGORIES = [
    "groceries",
    "dining",
    "transport",
    "shopping",
    "subscriptions",
    "bills_utilities",
    "entertainment",
    "travel",
    "healthcare",
    "transfers",
    "fees_charges",
    "other",
]
