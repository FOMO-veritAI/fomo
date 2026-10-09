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

# Serviço de IA. VERITAI_MODO=embutido usa o pipeline antigo (fop.py e retrieval.py).
VERITAI_MODO = os.getenv("VERITAI_MODO", "servico").strip().lower()
VERITAI_URL = os.getenv("VERITAI_URL", "http://127.0.0.1:8100").rstrip("/")
VERITAI_TIMEOUT = float(os.getenv("VERITAI_TIMEOUT", "600"))
# Decisão do servidor, nunca do publisher: ele não pode desligar a busca e enviar só evidências favoráveis.
VERITAI_BUSCAR_WEB = os.getenv("VERITAI_BUSCAR_WEB", "true").strip().lower() not in {"0", "false", "nao", "não", "no"}
FUSO_NOTICIA = "America/Sao_Paulo"

# Origens do frontend local; FOMO_CORS_ORIGINS acrescenta outras (ex.: GitHub Pages), separadas por vírgula.
CORS_ORIGINS = ["http://localhost:4200", "http://127.0.0.1:4200", "http://localhost:4173", "http://127.0.0.1:4173"] + [
    origem.strip().rstrip("/") for origem in os.getenv("FOMO_CORS_ORIGINS", "").split(",") if origem.strip()
]
