from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

COOKIE_FILE = PROJECT_DIR / "cookies.json"

APP_NAME = "GroupControler-FB"
APP_VERSION = "0.1.0"

MESSAGE_QUEUE_SIZE = 1000

LOG_DIR = PROJECT_DIR / "logs"
DATA_DIR = PROJECT_DIR / "data"

DRY_RUN = True
BOT_NICKNAME = "🌸 HINATA~"

# Groq AI Configuration
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
GROQ_MODEL = "openai/gpt-oss-120b"

# Group AI Command
GROUP_COMMAND = "/noun"
