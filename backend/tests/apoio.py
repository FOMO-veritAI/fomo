"""Ambiente comum dos testes: banco temporário, chaves de teste e VeritAI simulada.

Importe este módulo antes de backend.app: a configuração é lida uma única vez, na importação.
"""

import atexit
import os
import tempfile

import httpx

_directory = tempfile.TemporaryDirectory()
atexit.register(_directory.cleanup)
os.environ["TAKTA_DB_PATH"] = os.path.join(_directory.name, "test.sqlite3")
os.environ["TAKTA_PUBLISHER_KEY"] = "publisher-test-key"
os.environ["TAKTA_REVIEWER_KEY"] = "reviewer-test-key"
# Endereço que nunca é usado de verdade: todo tráfego passa pelo transporte simulado abaixo.
os.environ["VERITAI_URL"] = "http://veritai.teste"
os.environ["VERITAI_BUSCAR_WEB"] = "false"

from backend.app import veritai_client  # noqa: E402


def recusar_conexao(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("VeritAI simulada fora do ar", request=request)


# Padrão seguro: sem um transporte explícito no teste, a VeritAI está "fora do ar" e nada sai para a rede.
veritai_client.transporte = httpx.MockTransport(recusar_conexao)

PUBLISHER = {"X-Publisher-Key": "publisher-test-key"}
REVIEWER = {"X-Reviewer-Key": "reviewer-test-key"}

TEXTO_PUBLICO = {
    "SUPPORTED": "Resultado da verificação VeritAI: as evidências encontradas apoiam esta afirmação.",
    "REFUTED": "Resultado da verificação VeritAI: as evidências encontradas contradizem esta afirmação.",
    "NOT_ENOUGH_EVIDENCE": "Resultado da verificação VeritAI: não encontramos evidências suficientes para avaliar esta afirmação.",
    "CONFLICTING_EVIDENCE": "Resultado da verificação VeritAI: as fontes encontradas apresentam conclusões diferentes sobre esta afirmação.",
}


def relatorio_simulado(afirmacoes: list[str], resultados: list[str]) -> dict:
    """Relatório no formato do contrato, com porcentagem null como a VeritAI devolve hoje."""
    itens = []
    for afirmacao, resultado in zip(afirmacoes, resultados):
        evidencias = [] if resultado == "NOT_ENOUGH_EVIDENCE" else [{
            "fonte": "Diário Oficial do Município", "url": "https://example.org/parques", "data_publicacao": "2026-10-01",
            "trecho": "A prefeitura abriu três parques públicos.", "relacao": "contradiz" if resultado == "REFUTED" else "apoia",
            "origem": "link_publisher", "similaridade": 0.81, "pontuacao_nli": 0.93,
        }]
        itens.append({
            "afirmacao": afirmacao, "resultado": resultado, "texto_publico": TEXTO_PUBLICO[resultado],
            "avaliavel": False, "porcentagem": None,
            "motivo_nao_avaliavel": "evidencia_insuficiente" if resultado == "NOT_ENOUGH_EVIDENCE" else "modelo_nao_calibrado",
            "fontes_independentes": len(evidencias), "evidencias": evidencias,
            "checagens_anteriores": [{"agencia": "Agência de Checagem", "data": "2026-09-01", "url": "https://checagem.example.org/1", "alegacao_checada": "Cidade abriu parques", "veredito": "Falso"}],
            "justificativa": f"Justificativa simulada para {resultado}.", "limitacoes": ["Modelo não calibrado."],
        })
    return {"afirmacoes": itens, "avisos": ["Aviso simulado da análise."], "versoes": {"modelo": "veritai-v0", "config": "teste"}}
