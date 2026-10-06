import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          publisher TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          summary TEXT NOT NULL,
          topic TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          review_note TEXT NOT NULL DEFAULT '',
          search_errors TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS claims (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          article_id INTEGER NOT NULL REFERENCES articles(id),
          text TEXT NOT NULL,
          verdict TEXT NOT NULL DEFAULT 'NOT_ENOUGH_EVIDENCE',
          explanation TEXT NOT NULL DEFAULT '',
          confidence TEXT NOT NULL DEFAULT 'baixa'
        );
        CREATE TABLE IF NOT EXISTS evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          article_id INTEGER NOT NULL REFERENCES articles(id),
          claim_id INTEGER REFERENCES claims(id),
          origin TEXT NOT NULL,
          source_url TEXT NOT NULL DEFAULT '',
          source_title TEXT NOT NULL,
          source_domain TEXT NOT NULL DEFAULT '',
          excerpt TEXT NOT NULL DEFAULT '',
          full_text TEXT NOT NULL DEFAULT '',
          file_path TEXT NOT NULL DEFAULT '',
          file_type TEXT NOT NULL DEFAULT '',
          relation TEXT NOT NULL DEFAULT 'neutral',
          similarity REAL NOT NULL DEFAULT 0,
          nli_score REAL NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analises (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          article_id INTEGER NOT NULL REFERENCES articles(id),
          modo TEXT NOT NULL,
          data_noticia TEXT NOT NULL,
          relatorio_json TEXT NOT NULL,
          versoes_json TEXT NOT NULL,
          criado_em TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
        CREATE INDEX IF NOT EXISTS idx_analises_article ON analises(article_id);
        CREATE INDEX IF NOT EXISTS idx_claims_article ON claims(article_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_article ON evidence(article_id);
        """)
        # Bancos criados antes da integração com a VeritAI não têm estas colunas.
        for table, column, definition in (
            ("claims", "texto_publico", "TEXT NOT NULL DEFAULT ''"),
            ("claims", "relatorio_json", "TEXT NOT NULL DEFAULT ''"),
            ("evidence", "data_publicacao", "TEXT"),
        ):
            if column not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def article_record(db: sqlite3.Connection, article_id: int):
    row = db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["search_errors"] = json.loads(result["search_errors"])
    result["claims"] = []
    for claim in db.execute("SELECT * FROM claims WHERE article_id=? ORDER BY id", (article_id,)):
        item = dict(claim)
        item["relatorio"] = json.loads(item.pop("relatorio_json") or "null")
        item["evidence"] = [
            {key: value for key, value in dict(source).items() if key not in {"full_text", "file_path"}}
            for source in db.execute("SELECT * FROM evidence WHERE claim_id=? ORDER BY similarity DESC", (claim["id"],))
        ]
        result["claims"].append(item)
    result["attachments"] = [
        {key: value for key, value in dict(source).items() if key not in {"full_text", "file_path"}}
        for source in db.execute("SELECT * FROM evidence WHERE article_id=? AND claim_id IS NULL", (article_id,))
    ]
    analise = db.execute("SELECT id,modo,data_noticia,relatorio_json,versoes_json,criado_em FROM analises WHERE article_id=? ORDER BY id DESC LIMIT 1", (article_id,)).fetchone()
    result["analise"] = None
    if analise:
        relatorio = json.loads(analise["relatorio_json"])
        result["analise"] = {
            "id": analise["id"], "modo": analise["modo"], "data_noticia": analise["data_noticia"], "criado_em": analise["criado_em"],
            "versoes": json.loads(analise["versoes_json"]), "avisos": relatorio.get("avisos", []),
        }
    return result
