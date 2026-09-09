# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Environment/config loading with a loud, fail-fast startup check."""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

MOCK_LLM = os.getenv("MOCK_LLM", "0") == "1"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
VITE_ENABLE_VOICE = os.getenv("VITE_ENABLE_VOICE", "false") == "true"

DB_PATH = os.getenv("VALKA_DB_PATH", "checkpoints.sqlite")

# Comma-separated list, e.g. "https://valka-agent-frontend.onrender.com".
# The localhost defaults keep local dev working; a deployed frontend origin
# gets added on top rather than replacing them, so the same backend still
# works if you run the frontend locally against a deployed API.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
] + ["http://localhost:5173", "http://127.0.0.1:5173"]
KB_DIR = os.getenv("VALKA_KB_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kb"
))


def check_startup_config() -> None:
    """Fail loudly before the server binds if required config is missing.

    This must be called at process startup (API server, CLI, smoke script),
    not lazily on the first LLM call.
    """
    if MOCK_LLM:
        return
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        sys.stderr.write(
            "\n[valka-agent] STARTUP ERROR: no LLM credentials configured.\n"
            "Set GROQ_API_KEY and/or GEMINI_API_KEY in your .env, "
            "or set MOCK_LLM=1 to run without network access.\n\n"
        )
        raise SystemExit(1)
