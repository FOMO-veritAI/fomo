"""Pipeline local de similaridade semântica e NLI, sem probabilidades de verdade."""

import re
import threading
from dataclasses import dataclass

import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import EMBEDDING_MODEL, NLI_MODEL
from .retrieval import RetrievedSource


_load_lock = threading.Lock()
_models = None


def models():
    global _models
    if _models is None:
        with _load_lock:
            if _models is None:
                embedding = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
                tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
                nli = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL).eval()
                _models = embedding, tokenizer, nli
    return _models


def passages(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    return [sentence.strip()[:650] for sentence in sentences if 45 <= len(sentence.strip()) <= 800][:120]


@dataclass
class ScoredEvidence:
    source: RetrievedSource
    excerpt: str
    similarity: float
    relation: str
    nli_score: float


def compare(claim: str, sources: list[RetrievedSource]) -> list[ScoredEvidence]:
    candidates = [(source, sentence) for source in sources for sentence in passages(source.text)]
    if not candidates:
        return []
    embedding, tokenizer, nli = models()
    # O modelo normaliza vetores, então o produto é a similaridade do cosseno.
    vectors = embedding.encode([claim, *[text for _, text in candidates]], normalize_embeddings=True, convert_to_tensor=True)
    scores = (vectors[1:] @ vectors[0]).tolist()
    best_by_domain: dict[str, tuple[RetrievedSource, str, float]] = {}
    for (source, excerpt), score in zip(candidates, scores):
        if score < 0.38:
            continue
        previous = best_by_domain.get(source.domain)
        if previous is None or score > previous[2]:
            best_by_domain[source.domain] = source, excerpt, float(score)
    selected = sorted(best_by_domain.values(), key=lambda item: item[2], reverse=True)[:6]
    result: list[ScoredEvidence] = []
    for source, excerpt, similarity in selected:
        tokens = tokenizer(excerpt, claim, return_tensors="pt", truncation=True, max_length=512)
        with torch.inference_mode():
            probabilities = torch.softmax(nli(**tokens).logits[0], dim=-1).tolist()
        labels = {str(nli.config.id2label[index]).lower(): score for index, score in enumerate(probabilities)}
        relation = max(labels, key=labels.get)
        if relation not in {"entailment", "contradiction", "neutral"}:
            relation = "neutral"
        result.append(ScoredEvidence(source, excerpt, similarity, relation, float(labels.get(relation, 0))))
    return result


def verdict(items: list[ScoredEvidence]) -> tuple[str, str, str]:
    # Limiares conservadores de triagem: nenhum deles representa chance de verdade.
    strong = [item for item in items if item.similarity >= 0.43 and item.nli_score >= 0.72]
    supporters = {item.source.domain for item in strong if item.relation == "entailment"}
    contradictors = {item.source.domain for item in strong if item.relation == "contradiction"}
    if supporters and contradictors:
        return "CONFLICTING_EVIDENCE", "As evidências encontradas apresentam conclusões diferentes.", "baixa"
    if contradictors:
        return "REFUTED", "As evidências encontradas contradizem esta afirmação.", "média" if len(contradictors) == 1 else "alta"
    if supporters:
        return "SUPPORTED", "As evidências encontradas apoiam esta afirmação.", "média" if len(supporters) == 1 else "alta"
    return "NOT_ENOUGH_EVIDENCE", "Ainda não há evidências suficientes para avaliar esta afirmação.", "baixa"
