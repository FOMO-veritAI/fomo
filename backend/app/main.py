import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pypdf import PdfReader

from . import config, veritai_client
from .config import DB_PATH, GOOGLE_FACT_CHECK_API_KEY, PUBLISHER_KEY, REVIEWER_KEY, UPLOAD_DIR
from .db import article_record, connection, init_db, now
from .fop import compare, verdict
from .retrieval import RetrievedSource, fetch_page, search_sources
from .schemas import ArticleCreate, EvidenceLink, ReviewDecision
from .veritai_client import VeritAIErro

# O contrato da VeritAI aceita até 20 evidências e 20 anexos sem texto por análise.
MAX_ATTACHMENTS = 20


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="TAKTA FOP", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
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


def public_source(source: dict) -> dict:
    # Documentos anexados não expõem nome de arquivo nem conteúdo ao leitor.
    if source["origin"] in {"anexo", "publisher_document"}:
        return {"titulo": "Documento enviado pelo publisher", "url": "", "data_publicacao": None}
    return {"titulo": source["source_title"], "url": source["source_url"], "data_publicacao": source.get("data_publicacao")}


def public_record(article: dict) -> dict:
    """Expõe só o texto público por afirmação e as fontes; nada de relatório interno, notas ou anexos."""
    result = {key: article[key] for key in ("id", "publisher", "title", "summary", "body", "topic", "status", "created_at", "updated_at")}
    # Só afirmações com relatório da VeritAI são atribuídas a ela; o resto veio do pipeline anterior (modo embutido).
    result["claims"] = [
        {"id": claim["id"], "text": claim["text"],
         "origem_analise": "veritai" if claim["relatorio"] else "pipeline_anterior",
         "texto_publico": claim["texto_publico"] if claim["relatorio"] else f"Resultado da verificação automática anterior (sem VeritAI): {claim['explanation']}",
         "fontes": list({(item["titulo"], item["url"]): item for item in map(public_source, claim["evidence"])}.values())}
        for claim in article["claims"]
    ]
    result["verificado_pela_veritai"] = all(claim["relatorio"] for claim in article["claims"])
    result["manual_review"] = any(claim["verdict"] == "NOT_ENOUGH_EVIDENCE" for claim in article["claims"])
    # Imagens e documentos sem texto não passam pela IA, qualquer que seja o resultado das afirmações.
    result["anexo_sem_texto"] = any(item["origin"] == "manual_attachment" for item in article["attachments"])
    return result


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": str(DB_PATH),
        "publisher_key_configured": bool(PUBLISHER_KEY),
        "reviewer_key_configured": bool(REVIEWER_KEY),
        "google_fact_check_configured": bool(GOOGLE_FACT_CHECK_API_KEY),
        "veritai_modo": config.VERITAI_MODO,
        "veritai_url": config.VERITAI_URL if config.VERITAI_MODO == "servico" else None,
        "veritai_buscar_web": config.VERITAI_BUSCAR_WEB,
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
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO articles (publisher,title,body,summary,topic,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (payload.publisher.strip(), payload.title.strip(), payload.body.strip(), payload.summary.strip(), payload.topic.strip(), "DRAFT", now(), now()),
        )
        article_id = cursor.lastrowid
        for claim in payload.claims:
            db.execute("INSERT INTO claims (article_id,text) VALUES (?,?)", (article_id, claim))
        return article_record(db, article_id)


def ensure_editable(article):
    if article["status"] not in {"DRAFT", "NEEDS_EVIDENCE", "BLOCKED", "ERROR", "REJECTED"}:
        raise HTTPException(409, "Esta notícia não pode receber novas fontes neste estado.")
    if len(article["attachments"]) >= MAX_ATTACHMENTS:
        raise HTTPException(409, f"Cada notícia aceita até {MAX_ATTACHMENTS} fontes enviadas pelo publisher.")


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


def status_after_analysis(verdicts: list[str]) -> str:
    # A análise nunca publica nem bloqueia: tudo vai para o revisor humano. Contradição aparece em destaque na revisão.
    return "NEEDS_EVIDENCE" if "NOT_ENOUGH_EVIDENCE" in verdicts else "AWAITING_REVIEW"


async def verify_embedded(article: dict, attachments: list[dict]) -> list[str]:
    """Pipeline antigo (VERITAI_MODO=embutido), mantido até o serviço estar estável."""
    errors: list[str] = []
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
                    (article["id"], claim["id"], item.source.origin, item.source.url, item.source.title, item.source.domain, item.excerpt, item.relation, item.similarity, item.nli_score, now()),
                )
    return errors


async def verify_with_service(article: dict, attachments: list[dict], data_noticia: str) -> list[str]:
    pedido = veritai_client.montar_pedido(article, attachments, data_noticia)
    relatorio = await veritai_client.analisar(pedido)
    with connection() as db:
        db.execute(
            "INSERT INTO analises (article_id,modo,data_noticia,relatorio_json,versoes_json,criado_em) VALUES (?,?,?,?,?,?)",
            (article["id"], "servico", data_noticia, relatorio.model_dump_json(), json.dumps(relatorio.versoes, ensure_ascii=False), now()),
        )
        for claim, item in zip(article["claims"], relatorio.afirmacoes):
            db.execute("DELETE FROM evidence WHERE claim_id=?", (claim["id"],))
            db.execute(
                "UPDATE claims SET verdict=?,explanation=?,confidence=?,texto_publico=?,relatorio_json=? WHERE id=?",
                (item.resultado, item.justificativa, "não avaliável" if item.porcentagem is None else str(item.porcentagem), item.texto_publico, item.model_dump_json(), claim["id"]),
            )
            for source in item.evidencias:
                db.execute(
                    "INSERT INTO evidence (article_id,claim_id,origin,source_url,source_title,source_domain,excerpt,relation,similarity,nli_score,data_publicacao,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (article["id"], claim["id"], source.origem, source.url, source.fonte, urlparse(source.url).hostname or "", source.trecho, source.relacao, source.similaridade, source.pontuacao_nli, source.data_publicacao, now()),
                )
    return relatorio.avisos


async def run_verification(article_id: int, data_noticia: str):
    try:
        with connection() as db:
            article = get_article_or_404(db, article_id)
            attachments = [dict(row) for row in db.execute("SELECT * FROM evidence WHERE article_id=? AND claim_id IS NULL", (article_id,))]
        if config.VERITAI_MODO == "embutido":
            errors = await verify_embedded(article, attachments)
        elif config.VERITAI_MODO == "servico":
            errors = await verify_with_service(article, attachments, data_noticia)
        else:
            raise VeritAIErro("VERITAI_MODO inválido no servidor; use servico ou embutido.")
        with connection() as db:
            verdicts = [row["verdict"] for row in db.execute("SELECT verdict FROM claims WHERE article_id=?", (article_id,))]
            db.execute(
                "UPDATE articles SET status=?,updated_at=?,search_errors=? WHERE id=? AND status='VERIFYING'",
                (status_after_analysis(verdicts), now(), json.dumps(list(dict.fromkeys(errors)), ensure_ascii=False), article_id),
            )
    except Exception as exc:
        message = str(exc) if isinstance(exc, VeritAIErro) else f"Falha inesperada na verificação ({type(exc).__name__}). Tente novamente."
        with connection() as db:
            db.execute("UPDATE articles SET status='ERROR',updated_at=?,search_errors=? WHERE id=?", (now(), json.dumps([message], ensure_ascii=False), article_id))


@app.post("/publisher/articles/{article_id}/verify", dependencies=[Depends(require_publisher)])
def verify_article(article_id: int, background_tasks: BackgroundTasks):
    # Sem corpo nem parâmetros: data e busca na web são decididas pelo servidor, não pelo publisher.
    data_noticia = veritai_client.data_da_verificacao()
    with connection() as db:
        article = get_article_or_404(db, article_id)
        if article["status"] not in {"DRAFT", "NEEDS_EVIDENCE", "BLOCKED", "ERROR", "REJECTED"}:
            raise HTTPException(409, "Esta notícia já está em análise ou decisão.")
        # Resultados anteriores saem antes da nova análise, para não sobrar análise velha se a nova falhar.
        db.execute("DELETE FROM evidence WHERE article_id=? AND claim_id IS NOT NULL", (article_id,))
        db.execute("UPDATE claims SET verdict='NOT_ENOUGH_EVIDENCE',explanation='',confidence='baixa',texto_publico='',relatorio_json='' WHERE article_id=?", (article_id,))
        db.execute("UPDATE articles SET status='VERIFYING',updated_at=?,search_errors='[]' WHERE id=?", (now(), article_id))
    background_tasks.add_task(run_verification, article_id, data_noticia)
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
                raise HTTPException(409, "A aprovação exige análise concluída ou comprovação anexada e conferida. Registros BLOCKED antigos precisam de nova análise.")
        status = {"approve": "PUBLISHED", "reject": "REJECTED", "request_evidence": "NEEDS_EVIDENCE"}[payload.decision]
        db.execute("UPDATE articles SET status=?,review_note=?,updated_at=? WHERE id=?", (status, payload.note.strip(), now(), article_id))
        return article_record(db, article_id)
