import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pypdf import PdfReader

from .config import DB_PATH, GOOGLE_FACT_CHECK_API_KEY, PUBLISHER_KEY, REVIEWER_KEY, UPLOAD_DIR
from .db import article_record, connection, init_db, now
from .fop import compare, verdict
from .retrieval import RetrievedSource, fetch_page, search_sources
from .schemas import ArticleCreate, EvidenceLink, ReviewDecision


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="TAKTA FOP", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Publisher-Key", "X-Reviewer-Key", "Content-Type"],
)


def require_publisher(x_publisher_key: str = Header(default="")):
    if not PUBLISHER_KEY or not secrets.compare_digest(x_publisher_key, PUBLISHER_KEY):
        raise HTTPException(401, "Chave do publisher ausente ou incorreta.")


def require_reviewer(x_reviewer_key: str = Header(default="")):
    if not REVIEWER_KEY or not secrets.compare_digest(x_reviewer_key, REVIEWER_KEY):
        raise HTTPException(401, "Chave do revisor ausente ou incorreta.")


def get_article_or_404(db, article_id: int):
    article = article_record(db, article_id)
    if article is None:
        raise HTTPException(404, "Notícia não encontrada.")
    return article


def public_record(article: dict) -> dict:
    """Expose the reviewed claims and sources, without internal notes or uploads."""
    result = {key: value for key, value in article.items() if key not in {"review_note", "search_errors", "attachments"}}
    result["manual_review"] = any(claim["verdict"] == "NOT_ENOUGH_EVIDENCE" for claim in article["claims"])
    return result


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": str(DB_PATH),
        "publisher_key_configured": bool(PUBLISHER_KEY),
        "reviewer_key_configured": bool(REVIEWER_KEY),
        "google_fact_check_configured": bool(GOOGLE_FACT_CHECK_API_KEY),
        "model_loading": "on_first_verification",
    }


@app.get("/articles")
def public_articles():
    with connection() as db:
        ids = [row["id"] for row in db.execute("SELECT id FROM articles WHERE status='PUBLISHED' ORDER BY id DESC")]
        return [public_record(article_record(db, article_id)) for article_id in ids]


@app.get("/articles/{article_id}")
def public_article(article_id: int):
    with connection() as db:
        article = get_article_or_404(db, article_id)
        if article["status"] != "PUBLISHED":
            raise HTTPException(404, "Notícia ainda não foi publicada.")
        return public_record(article)


@app.get("/publisher/articles", dependencies=[Depends(require_publisher)])
def publisher_articles():
    with connection() as db:
        ids = [row["id"] for row in db.execute("SELECT id FROM articles ORDER BY id DESC")]
        return [article_record(db, article_id) for article_id in ids]


@app.get("/publisher/articles/{article_id}", dependencies=[Depends(require_publisher)])
def publisher_article(article_id: int):
    with connection() as db:
        return get_article_or_404(db, article_id)


@app.post("/publisher/articles", status_code=201, dependencies=[Depends(require_publisher)])
def create_article(payload: ArticleCreate):
    cleaned_claims = [claim.strip() for claim in payload.claims if claim.strip()]
    if not cleaned_claims:
        raise HTTPException(422, "Informe pelo menos uma afirmação factual.")
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO articles (publisher,title,body,summary,topic,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (payload.publisher.strip(), payload.title.strip(), payload.body.strip(), payload.summary.strip(), payload.topic.strip(), "DRAFT", now(), now()),
        )
        article_id = cursor.lastrowid
        for claim in cleaned_claims:
            db.execute("INSERT INTO claims (article_id,text) VALUES (?,?)", (article_id, claim[:500]))
        return article_record(db, article_id)


def ensure_editable(article):
    if article["status"] not in {"DRAFT", "NEEDS_EVIDENCE", "BLOCKED", "ERROR", "REJECTED"}:
        raise HTTPException(409, "Esta notícia não pode receber novas fontes neste estado.")


@app.post("/publisher/articles/{article_id}/evidence/url", dependencies=[Depends(require_publisher)])
async def add_evidence_url(article_id: int, payload: EvidenceLink):
    with connection() as db:
        ensure_editable(get_article_or_404(db, article_id))
    try:
        source = await fetch_page(str(payload.url), "publisher_url")
    except Exception as exc:
        raise HTTPException(422, f"A fonte não pôde ser lida: {exc}") from exc
    with connection() as db:
        db.execute(
            "INSERT INTO evidence (article_id,origin,source_url,source_title,source_domain,full_text,created_at) VALUES (?,?,?,?,?,?,?)",
            (article_id, source.origin, source.url, source.title, source.domain, source.text, now()),
        )
        return article_record(db, article_id)


@app.post("/publisher/articles/{article_id}/evidence/file", dependencies=[Depends(require_publisher)])
async def add_evidence_file(article_id: int, file: UploadFile = File(...)):
    with connection() as db:
        ensure_editable(get_article_or_404(db, article_id))
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".txt", ".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(422, "Envie TXT, PDF, PNG ou JPG.")
    content = await file.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(413, "O arquivo deve ter até 5 MB.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / f"{secrets.token_hex(16)}{extension}"
    destination.write_bytes(content)
    extracted = ""
    try:
        if extension == ".txt":
            extracted = content.decode("utf-8")[:40000]
        elif extension == ".pdf":
            extracted = " ".join(page.extract_text() or "" for page in PdfReader(destination).pages[:20])[:40000]
    except Exception:
        extracted = ""
    with connection() as db:
        db.execute(
            "INSERT INTO evidence (article_id,origin,source_title,source_domain,full_text,file_path,file_type,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (article_id, "publisher_document" if extracted else "manual_attachment", file.filename or destination.name, "publisher-document", extracted, str(destination), extension, now()),
        )
        return article_record(db, article_id)


async def run_verification(article_id: int):
    errors: list[str] = []
    try:
        with connection() as db:
            article = get_article_or_404(db, article_id)
            attachments = db.execute("SELECT * FROM evidence WHERE article_id=? AND claim_id IS NULL", (article_id,)).fetchall()
        publisher_sources = [
            RetrievedSource(row["source_url"], row["source_title"], row["source_domain"], row["full_text"], row["origin"])
            for row in attachments if row["full_text"]
        ]
        if any(row["origin"] == "manual_attachment" for row in attachments):
            errors.append("Há imagens ou documentos sem texto que exigem revisão humana.")
        for claim in article["claims"]:
            discovered, search_errors = await search_sources(claim["text"])
            errors.extend(search_errors)
            scored = await asyncio.to_thread(compare, claim["text"], discovered + publisher_sources)
            claim_verdict, explanation, confidence = verdict(scored)
            with connection() as db:
                db.execute("DELETE FROM evidence WHERE claim_id=?", (claim["id"],))
                db.execute("UPDATE claims SET verdict=?,explanation=?,confidence=? WHERE id=?", (claim_verdict, explanation, confidence, claim["id"]))
                for item in scored:
                    db.execute(
                        "INSERT INTO evidence (article_id,claim_id,origin,source_url,source_title,source_domain,excerpt,relation,similarity,nli_score,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (article_id, claim["id"], item.source.origin, item.source.url, item.source.title, item.source.domain, item.excerpt, item.relation, item.similarity, item.nli_score, now()),
                    )
        with connection() as db:
            statuses = [row["verdict"] for row in db.execute("SELECT verdict FROM claims WHERE article_id=?", (article_id,))]
            if "REFUTED" in statuses:
                status = "BLOCKED"
            elif "NOT_ENOUGH_EVIDENCE" in statuses:
                status = "NEEDS_EVIDENCE"
            else:
                status = "AWAITING_REVIEW"
            db.execute("UPDATE articles SET status=?,updated_at=?,search_errors=? WHERE id=?", (status, now(), json.dumps(list(dict.fromkeys(errors))), article_id))
    except Exception as exc:
        with connection() as db:
            db.execute("UPDATE articles SET status='ERROR',updated_at=?,search_errors=? WHERE id=?", (now(), json.dumps([f"Falha na verificação: {type(exc).__name__}: {exc}"]), article_id))


@app.post("/publisher/articles/{article_id}/verify", dependencies=[Depends(require_publisher)])
def verify_article(article_id: int, background_tasks: BackgroundTasks):
    with connection() as db:
        article = get_article_or_404(db, article_id)
        if article["status"] not in {"DRAFT", "NEEDS_EVIDENCE", "BLOCKED", "ERROR", "REJECTED"}:
            raise HTTPException(409, "Esta notícia já está em análise ou decisão.")
        db.execute("UPDATE articles SET status='VERIFYING',updated_at=? WHERE id=?", (now(), article_id))
    background_tasks.add_task(run_verification, article_id)
    return {"id": article_id, "status": "VERIFYING"}


@app.get("/review/articles", dependencies=[Depends(require_reviewer)])
def review_queue():
    with connection() as db:
        ids = [row["id"] for row in db.execute("SELECT id FROM articles WHERE status IN ('AWAITING_REVIEW','NEEDS_EVIDENCE','BLOCKED') ORDER BY id DESC")]
        return [article_record(db, article_id) for article_id in ids]


@app.get("/review/attachments/{attachment_id}", dependencies=[Depends(require_reviewer)])
def review_attachment(attachment_id: int):
    with connection() as db:
        row = db.execute("SELECT file_path,source_title,file_type FROM evidence WHERE id=? AND claim_id IS NULL", (attachment_id,)).fetchone()
    if not row or not row["file_path"] or not Path(row["file_path"]).is_file():
        raise HTTPException(404, "Anexo não encontrado.")
    return FileResponse(row["file_path"], filename=Path(row["source_title"]).name)


@app.post("/review/articles/{article_id}", dependencies=[Depends(require_reviewer)])
def review_article(article_id: int, payload: ReviewDecision):
    with connection() as db:
        article = get_article_or_404(db, article_id)
        if article["status"] not in {"AWAITING_REVIEW", "NEEDS_EVIDENCE", "BLOCKED"}:
            raise HTTPException(409, "A notícia ainda não está pronta para revisão.")
        if payload.decision == "approve":
            has_attachment = any(item["file_type"] for item in article["attachments"])
            if article["status"] != "AWAITING_REVIEW" and not (article["status"] == "NEEDS_EVIDENCE" and has_attachment):
                raise HTTPException(409, "A aprovação exige análise sem bloqueio ou comprovação anexada e revisada.")
        status = {"approve": "PUBLISHED", "reject": "REJECTED", "request_evidence": "NEEDS_EVIDENCE"}[payload.decision]
        db.execute("UPDATE articles SET status=?,review_note=?,updated_at=? WHERE id=?", (status, payload.note.strip(), now(), article_id))
        return article_record(db, article_id)
