"""Telegram KG Manager Bot Application."""
import os

# Must be first: set before any process imports LangGraph (Procfile also sets this; setdefault keeps Procfile value)
os.environ.setdefault("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "30")

from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (directory containing app/) so API keys and config
# are found when running from any directory (e.g. LUMI_3 or ag-agent-manager).
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")
