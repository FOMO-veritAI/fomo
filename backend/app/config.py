import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DB_PATH = Path(os.getenv("TAKTA_DB_PATH", str(BASE_DIR / "data" / "takta.sqlite3")))
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
PUBLISHER_KEY = os.getenv("TAKTA_PUBLISHER_KEY", "")
REVIEWER_KEY = os.getenv("TAKTA_REVIEWER_KEY", "")
GOOGLE_FACT_CHECK_API_KEY = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NLI_MODEL = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
