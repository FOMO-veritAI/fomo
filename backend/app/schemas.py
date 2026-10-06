from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from .veritai_contrato import host_valido


# Mesmos limites do contrato da VeritAI, para não receber 422 dela.
CLAIM_MIN = 10
CLAIM_MAX = 500


class ArticleCreate(BaseModel):
    publisher: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=12, max_length=300)
    summary: str = Field(min_length=20, max_length=1000)
    body: str = Field(min_length=30, max_length=30000)
    topic: str = Field(min_length=2, max_length=80)
    claims: list[str] = Field(min_length=1, max_length=8)

    @field_validator("claims")
    @classmethod
    def claims_validas(cls, claims: list[str]) -> list[str]:
        cleaned = [claim.strip() for claim in claims if claim.strip()]
        if not cleaned:
            raise ValueError("Informe pelo menos uma afirmação factual.")
        for number, claim in enumerate(cleaned, start=1):
            if not CLAIM_MIN <= len(claim) <= CLAIM_MAX:
                raise ValueError(f"A afirmação {number} precisa ter entre {CLAIM_MIN} e {CLAIM_MAX} caracteres (tem {len(claim)}).")
        return cleaned


class EvidenceLink(BaseModel):
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def dominio_valido(cls, url: HttpUrl) -> HttpUrl:
        if url.scheme not in {"http", "https"} or not url.host or not host_valido(url.host):
            raise ValueError("O link precisa começar com http:// ou https:// e ter um domínio válido.")
        return url


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject", "request_evidence"]
    note: str = Field(min_length=8, max_length=2000)
