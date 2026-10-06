from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ArticleCreate(BaseModel):
    publisher: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=12, max_length=300)
    summary: str = Field(min_length=20, max_length=1000)
    body: str = Field(min_length=30, max_length=30000)
    topic: str = Field(min_length=2, max_length=80)
    claims: list[str] = Field(min_length=1, max_length=8)


class EvidenceLink(BaseModel):
    url: HttpUrl


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject", "request_evidence"]
    note: str = Field(min_length=8, max_length=2000)
