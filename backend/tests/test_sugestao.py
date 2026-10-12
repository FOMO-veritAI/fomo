import json
import unittest
from unittest.mock import patch

import apoio  # noqa: F401  (configura banco temporário e VeritAI simulada antes de importar o app)
import httpx
from apoio import PUBLISHER, recusar_conexao
from fastapi.testclient import TestClient

from backend.app import veritai_client

NOTICIA = {
    "title": "IBGE: desocupação fica em 5,3% no trimestre",
    "body": "A taxa de desocupação ficou em 5,3% no trimestre encerrado em agosto, segundo o IBGE. O resultado é o menor da série.",
}


def extracao_simulada(pedido: dict) -> dict:
    """Resposta no formato do contrato do POST /extrair."""
    return {
        "afirmacoes": [{
            "texto": "A taxa de desocupação ficou em 5,3% no trimestre encerrado em agosto de 2026, segundo o IBGE.",
            "trecho_origem": "A taxa de desocupação ficou em 5,3% no trimestre encerrado em agosto, segundo o IBGE.",
            "posicao": 1, "pontuacao": 5, "sinais": ["número", "período", "atribuição"], "alertas": [], "atribuicao": "IBGE",
        }, {
            "texto": "O resultado é o menor da série histórica.", "trecho_origem": "O resultado é o menor da série.",
            "posicao": 2, "pontuacao": 1, "sinais": ["verbo de fato"],
            "alertas": ["depende da frase anterior: completar o sujeito", "sem período: o verificador não confere a data"], "atribuicao": None,
        }],
        "avisos": ["Afirmações propostas por regras, sem verificação: confirme, edite ou descarte cada uma antes de analisar."],
        "versoes": {"extracao": "regras-teste", "config": "teste"},
    }


class ExtracaoSimulada:
    def __init__(self, resposta=None):
        self.resposta = resposta or (lambda pedido: httpx.Response(200, json=extracao_simulada(pedido)))
        self.pedidos: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/extrair"
        pedido = json.loads(request.content)
        self.pedidos.append(pedido)
        return self.resposta(pedido)


@patch("backend.app.config.VERITAI_MODO", "servico")
class ClaimSuggestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.app.main import app
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def tearDown(self):
        veritai_client.transporte = httpx.MockTransport(recusar_conexao)

    def suggest(self, payload=NOTICIA, headers=PUBLISHER):
        return self.client.post("/publisher/claims/suggest", headers=headers, json=payload)

    def test_returns_candidates_and_sends_news_with_server_date(self):
        simulada = ExtracaoSimulada()
        veritai_client.transporte = httpx.MockTransport(simulada)
        with patch("backend.app.veritai_client.data_da_verificacao", return_value="2026-10-12"):
            response = self.suggest()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["posicao"] for item in response.json()["afirmacoes"]], [1, 2])
        self.assertEqual(simulada.pedidos, [{"noticia": {"titulo": NOTICIA["title"], "texto": NOTICIA["body"], "data": "2026-10-12"}, "maximo": 8}])

    def test_suggestion_does_not_create_article(self):
        veritai_client.transporte = httpx.MockTransport(ExtracaoSimulada())
        antes = self.client.get("/publisher/articles", headers=PUBLISHER).json()
        self.assertEqual(self.suggest().status_code, 200)
        self.assertEqual(self.client.get("/publisher/articles", headers=PUBLISHER).json(), antes)

    def test_requires_publisher_key(self):
        self.assertEqual(self.suggest(headers={}).status_code, 401)
        self.assertEqual(self.suggest(headers={"X-Publisher-Key": "errada"}).status_code, 401)

    def test_requires_title(self):
        self.assertEqual(self.suggest(payload={"title": "   ", "body": "Texto."}).status_code, 422)

    def test_veritai_offline_returns_clear_error(self):
        response = self.suggest()
        self.assertEqual(response.status_code, 502)
        self.assertIn("VeritAI indisponível", response.json()["detail"])

    def test_http_error_and_invalid_response_are_rejected(self):
        casos = [
            ("recusou a sugestão de afirmações (HTTP 500)", lambda pedido: httpx.Response(500, json={})),
            ("não segue o contrato", lambda pedido: httpx.Response(200, json={"afirmacoes": [{"texto": "incompleta"}]})),
        ]
        for mensagem, resposta in casos:
            with self.subTest(mensagem=mensagem):
                veritai_client.transporte = httpx.MockTransport(ExtracaoSimulada(resposta))
                response = self.suggest()
                self.assertEqual(response.status_code, 502)
                self.assertIn(mensagem, response.json()["detail"])

    def test_embedded_mode_has_no_suggestion(self):
        # Dentro do teste: um @patch no método se somaria ao da classe, e o da classe prevaleceria.
        with patch("backend.app.config.VERITAI_MODO", "embutido"):
            self.assertEqual(self.suggest().status_code, 409)


if __name__ == "__main__":
    unittest.main()
