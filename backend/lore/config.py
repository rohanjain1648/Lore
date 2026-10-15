import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6391"))
FALKORDB_USERNAME = os.getenv("FALKORDB_USERNAME") or None
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None

DATA_DIR = Path(os.getenv("LORE_DATA_DIR", ROOT / "data"))
DEFAULT_TENANT = os.getenv("LORE_DEFAULT_TENANT", "northwind")

# LLM providers: Groq is primary, OpenAI is the fallback. Either, both or neither may be configured;
# with neither, Lore runs its deterministic offline agent and rule extractor.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_AGENT_MODEL = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b")
GROQ_EXTRACT_MODEL = os.getenv("GROQ_EXTRACT_MODEL", "openai/gpt-oss-20b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-5.4-mini")
OPENAI_EXTRACT_MODEL = os.getenv("OPENAI_EXTRACT_MODEL", "gpt-5.4-mini")
HAS_LLM = bool(GROQ_API_KEY or OPENAI_API_KEY)
# "rules" (deterministic, no key needed) or "llm" (structured extraction with the LLM chain)
EXTRACTOR = os.getenv("LORE_EXTRACTOR", "llm" if HAS_LLM else "rules")

EMBED_MODEL = os.getenv("LORE_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384

# Expertise decays with a ~4 month half-life-ish time constant
EXPERTISE_TAU_DAYS = 120.0


def graph_name(tenant: str) -> str:
    return f"lore_{tenant}"
