"""Cliente HTTP da VeritAI: monta o pedido, chama POST /analisar e valida o relatório."""

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from . import config
from .veritai_contrato import EvidenciaFornecida, Noticia, PedidoAnalise, RelatorioAnalise


# Os testes trocam por httpx.MockTransport; None usa a rede de verdade.
transporte: httpx.AsyncBaseTransport | None = None

ORIGEM_EVIDENCIA = {"publisher_url": "link_publisher", "publisher_document": "anexo"}


class VeritAIErro(Exception):
    """Falha ao obter um relatório válido; a mensagem é mostrada ao publisher."""


def data_da_verificacao() -> str:
    return datetime.now(ZoneInfo(config.FUSO_NOTICIA)).date().isoformat()


def montar_pedido(article: dict, anexos: list[dict], data: str) -> PedidoAnalise:
    evidencias = [
        EvidenciaFornecida(
            titulo=(anexo["source_title"] or "Documento do publisher")[:300],
            texto=anexo["full_text"][:40000],
            url=anexo["source_url"],
            origem=ORIGEM_EVIDENCIA[anexo["origin"]],
        )
        for anexo in anexos if anexo["full_text"] and anexo["origin"] in ORIGEM_EVIDENCIA
    ]
    try:
        return PedidoAnalise(
            noticia=Noticia(titulo=article["title"][:300], texto=article["body"][:30000], data=data),
            afirmacoes=[claim["text"] for claim in article["claims"]],
            evidencias=evidencias,
            anexos_sem_texto=sum(1 for anexo in anexos if anexo["origin"] == "manual_attachment"),
            buscar_na_web=config.VERITAI_BUSCAR_WEB,
        )
    except ValidationError as exc:
        campos = sorted({".".join(str(parte) for parte in erro["loc"]) for erro in exc.errors()})
        raise VeritAIErro(f"A notícia não atende ao contrato da VeritAI ({', '.join(campos)}). Corrija e envie novamente.") from exc


async def analisar(pedido: PedidoAnalise) -> RelatorioAnalise:
    url = config.VERITAI_URL
    try:
        async with httpx.AsyncClient(base_url=url, timeout=config.VERITAI_TIMEOUT, transport=transporte) as client:
            response = await client.post("/analisar", json=pedido.model_dump())
    except httpx.TimeoutException as exc:
        raise VeritAIErro(f"A VeritAI ({url}) não respondeu em {config.VERITAI_TIMEOUT:.0f} s. Tente novamente.") from exc
    except httpx.HTTPError as exc:
        raise VeritAIErro(f"VeritAI indisponível em {url}. Verifique se o serviço está rodando e tente novamente.") from exc
    if response.status_code != 200:
        raise VeritAIErro(f"A VeritAI recusou a análise (HTTP {response.status_code}). Tente novamente ou revise as afirmações e fontes.")
    try:
        relatorio = RelatorioAnalise.model_validate(response.json())
    except (ValueError, ValidationError) as exc:
        raise VeritAIErro("A resposta da VeritAI não segue o contrato esperado; a análise foi descartada.") from exc
    if [item.afirmacao for item in relatorio.afirmacoes] != pedido.afirmacoes:
        raise VeritAIErro("O relatório da VeritAI não corresponde às afirmações enviadas; a análise foi descartada.")
    return relatorio
