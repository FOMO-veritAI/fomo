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
        CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
        CREATE INDEX IF NOT EXISTS idx_claims_article ON claims(article_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_article ON evidence(article_id);
        """)


def article_record(db: sqlite3.Connection, article_id: int):
    row = db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["search_errors"] = json.loads(result["search_errors"])
    result["claims"] = []
    for claim in db.execute("SELECT * FROM claims WHERE article_id=? ORDER BY id", (article_id,)):
        item = dict(claim)
        item["evidence"] = [
            {key: value for key, value in dict(source).items() if key not in {"full_text", "file_path"}}
            for source in db.execute("SELECT * FROM evidence WHERE claim_id=? ORDER BY similarity DESC", (claim["id"],))
        ]
        result["claims"].append(item)
    result["attachments"] = [
        {key: value for key, value in dict(source).items() if key not in {"full_text", "file_path"}}
        for source in db.execute("SELECT * FROM evidence WHERE article_id=? AND claim_id IS NULL", (article_id,))
    ]
    return result
