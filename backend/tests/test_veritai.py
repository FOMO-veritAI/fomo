import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import apoio  # noqa: F401  (configura banco temporário e VeritAI simulada antes de importar o app)
import httpx
from apoio import PUBLISHER, REVIEWER, recusar_conexao, relatorio_simulado
from fastapi.testclient import TestClient

from backend.app import veritai_client
from backend.app.db import connection
from backend.app.retrieval import RetrievedSource

CLAIMS = ["A cidade abriu três novos parques públicos.", "A obra custou 12 milhões de reais."]


class VeritAISimulada:
    """Transporte httpx que guarda os pedidos e responde com resultados escolhidos pelo teste."""

    def __init__(self, resultados=None, resposta=None):
        self.resultados = resultados
        self.resposta = resposta
        self.pedidos: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/analisar"
        pedido = json.loads(request.content)
        self.pedidos.append(pedido)
        if self.resposta is not None:
            return self.resposta(pedido)
        return httpx.Response(200, json=relatorio_simulado(pedido["afirmacoes"], self.resultados))


@patch("backend.app.config.VERITAI_MODO", "servico")
class VeritAIIntegrationTest(unittest.TestCase):
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

    def use(self, simulada) -> None:
        veritai_client.transporte = httpx.MockTransport(simulada)

    def create_article(self, claims=CLAIMS):
        response = self.client.post("/publisher/articles", headers=PUBLISHER, json={
            "publisher": "Jornal de teste", "title": "A cidade abriu três novos parques públicos",
            "summary": "A prefeitura anunciou três novos parques abertos à população.",
            "body": "O município informou que três parques públicos foram abertos neste mês.",
            "topic": "Sociedade", "claims": claims,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def verify(self, article_id, **kwargs):
        response = self.client.post(f"/publisher/articles/{article_id}/verify", headers=PUBLISHER, **kwargs)
        self.assertEqual(response.status_code, 200, response.text)
        return self.client.get(f"/publisher/articles/{article_id}", headers=PUBLISHER).json()

    def decide(self, article_id, decision):
        return self.client.post(f"/review/articles/{article_id}", headers=REVIEWER, json={"decision": decision, "note": "Decisão registrada pelo revisor no teste."})

    def assert_not_public(self, article_id):
        self.assertEqual(self.client.get(f"/articles/{article_id}").status_code, 404)
        self.assertNotIn(article_id, [item["id"] for item in self.client.get("/articles").json()])

    # Pedido

    def test_request_is_built_from_article_and_evidence(self):
        article_id = self.create_article()
        page = RetrievedSource("https://example.org/parques", "Prefeitura anuncia parques", "example.org", "A prefeitura abriu três parques públicos neste mês.", "publisher_url")

        async def fake_fetch(url, origin):
            return page

        with patch("backend.app.main.fetch_page", fake_fetch):
            self.assertEqual(self.client.post(f"/publisher/articles/{article_id}/evidence/url", headers=PUBLISHER, json={"url": "https://example.org/parques"}).status_code, 200)
        for name, content, kind in (("relatorio.txt", "Relatório oficial: três parques foram abertos.".encode(), "text/plain"), ("foto.png", b"\x89PNG\r\n\x1a\nexample", "image/png")):
            self.assertEqual(self.client.post(f"/publisher/articles/{article_id}/evidence/file", headers=PUBLISHER, files={"file": (name, content, kind)}).status_code, 200)
        simulada = VeritAISimulada(["SUPPORTED", "SUPPORTED"])
        self.use(simulada)
        self.verify(article_id)

        self.assertEqual(len(simulada.pedidos), 1)
        pedido = simulada.pedidos[0]
        self.assertEqual(set(pedido), {"noticia", "afirmacoes", "evidencias", "anexos_sem_texto", "buscar_na_web"})
        self.assertEqual(pedido["noticia"]["titulo"], "A cidade abriu três novos parques públicos")
        self.assertEqual(pedido["noticia"]["texto"], "O município informou que três parques públicos foram abertos neste mês.")
        self.assertRegex(pedido["noticia"]["data"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(pedido["afirmacoes"], CLAIMS)
        self.assertEqual(pedido["evidencias"], [
            {"titulo": "Prefeitura anuncia parques", "texto": page.text, "url": "https://example.org/parques", "origem": "link_publisher", "data_publicacao": None},
            {"titulo": "relatorio.txt", "texto": "Relatório oficial: três parques foram abertos.", "url": "", "origem": "anexo", "data_publicacao": None},
        ])
        self.assertEqual(pedido["anexos_sem_texto"], 1)
        self.assertIs(pedido["buscar_na_web"], False)

    def test_news_date_is_verification_day_in_sao_paulo(self):
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                # 01:30 UTC de 7/10 ainda é 6/10 em São Paulo (UTC-3).
                return datetime(2026, 10, 7, 1, 30, tzinfo=timezone.utc).astimezone(tz)

        article_id = self.create_article()
        simulada = VeritAISimulada(["SUPPORTED", "SUPPORTED"])
        self.use(simulada)
        with patch("backend.app.veritai_client.datetime", FixedDatetime):
            self.verify(article_id)
        self.assertEqual(simulada.pedidos[0]["noticia"]["data"], "2026-10-06")

    def test_publisher_cannot_change_web_search(self):
        for configured in (True, False):
            article_id = self.create_article()
            simulada = VeritAISimulada(["SUPPORTED", "SUPPORTED"])
            self.use(simulada)
            with patch("backend.app.config.VERITAI_BUSCAR_WEB", configured):
                self.verify(article_id, params={"buscar_na_web": str(not configured).lower()}, json={"buscar_na_web": not configured})
            self.assertIs(simulada.pedidos[0]["buscar_na_web"], configured)

    # Validação antes de chegar à VeritAI

    def test_claims_must_have_10_to_500_characters(self):
        base = {"publisher": "Jornal de teste", "title": "Título com tamanho suficiente", "summary": "Resumo com tamanho suficiente.", "body": "Texto da notícia com tamanho suficiente.", "topic": "Sociedade"}
        for claims, expected in ((["a" * 9], 422), (["a" * 501], 422), (["Afirmação válida.", "curta"], 422), (["a" * 10], 201), (["a" * 500], 201), (["  " + "a" * 10 + "  "], 201)):
            response = self.client.post("/publisher/articles", headers=PUBLISHER, json={**base, "claims": claims})
            self.assertEqual(response.status_code, expected, claims)
            if expected == 422:
                self.assertIn("entre 10 e 500 caracteres", response.text)

    def test_evidence_url_needs_http_and_valid_domain(self):
        article_id = self.create_article()
        for url in ("ftp://example.org/arquivo", "javascript:alert(1)", "https://exemplo_invalido.org/x", "https:///sem-dominio", "notícia sem link"):
            response = self.client.post(f"/publisher/articles/{article_id}/evidence/url", headers=PUBLISHER, json={"url": url})
            self.assertEqual(response.status_code, 422, url)

    # Falhas da VeritAI

    def test_veritai_down_goes_to_error_and_never_publishes(self):
        article_id = self.create_article()
        article = self.verify(article_id)  # transporte padrão: conexão recusada
        self.assertEqual(article["status"], "ERROR")
        self.assertIn("VeritAI indisponível", article["search_errors"][0])
        self.assert_not_public(article_id)
        self.assertNotIn(article_id, [item["id"] for item in self.client.get("/review/articles", headers=REVIEWER).json()])
        self.assertEqual(self.decide(article_id, "approve").status_code, 409)
        self.assert_not_public(article_id)

    def test_veritai_failures_go_to_error(self):
        def timeout(request):
            raise httpx.ReadTimeout("lento", request=request)

        def com_porcentagem_sem_calibracao(pedido):
            relatorio = relatorio_simulado(pedido["afirmacoes"], ["SUPPORTED", "SUPPORTED"])
            relatorio["afirmacoes"][0]["avaliavel"] = True  # avaliável sem porcentagem quebra o contrato
            return httpx.Response(200, json=relatorio)

        casos = [
            ("não respondeu", timeout),
            ("HTTP 500", VeritAISimulada(resposta=lambda pedido: httpx.Response(500, json={"detail": "erro"}))),
            ("HTTP 422", VeritAISimulada(resposta=lambda pedido: httpx.Response(422, json={"detail": []}))),
            ("não segue o contrato", VeritAISimulada(resposta=com_porcentagem_sem_calibracao)),
            ("não segue o contrato", VeritAISimulada(resposta=lambda pedido: httpx.Response(200, text="<html>"))),
            ("não corresponde", VeritAISimulada(resposta=lambda pedido: httpx.Response(200, json=relatorio_simulado(pedido["afirmacoes"][:1], ["SUPPORTED"])))),
        ]
        for trecho, simulada in casos:
            with self.subTest(trecho):
                article_id = self.create_article()
                self.use(simulada)
                article = self.verify(article_id)
                self.assertEqual(article["status"], "ERROR")
                self.assertTrue(any(trecho in erro for erro in article["search_errors"]), article["search_errors"])
                self.assertTrue(all(claim["relatorio"] is None for claim in article["claims"]))
                self.assert_not_public(article_id)

    def test_failed_reanalysis_discards_previous_results(self):
        article_id = self.create_article()
        self.use(VeritAISimulada(["SUPPORTED", "SUPPORTED"]))
        self.verify(article_id)
        self.assertEqual(self.decide(article_id, "reject").status_code, 200)
        veritai_client.transporte = httpx.MockTransport(recusar_conexao)
        article = self.verify(article_id)
        self.assertEqual(article["status"], "ERROR")
        self.assertTrue(all(claim["relatorio"] is None and not claim["evidence"] for claim in article["claims"]))

    # Revisão humana obrigatória

    def test_refuted_claim_goes_to_review_and_needs_approval(self):
        article_id = self.create_article()
        self.use(VeritAISimulada(["REFUTED", "SUPPORTED"]))
        article = self.verify(article_id)
        self.assertEqual(article["status"], "AWAITING_REVIEW")
        self.assertEqual(article["claims"][0]["relatorio"]["resultado"], "REFUTED")
        self.assertIn(article_id, [item["id"] for item in self.client.get("/review/articles", headers=REVIEWER).json()])
        self.assert_not_public(article_id)
        self.assertEqual(self.decide(article_id, "approve").status_code, 200)
        self.assertEqual(self.client.get(f"/articles/{article_id}").status_code, 200)

    def test_refuted_and_missing_evidence_needs_evidence(self):
        article_id = self.create_article()
        self.use(VeritAISimulada(["REFUTED", "NOT_ENOUGH_EVIDENCE"]))
        article = self.verify(article_id)
        self.assertEqual(article["status"], "NEEDS_EVIDENCE")
        self.assertEqual(self.decide(article_id, "approve").status_code, 409)  # sem anexo, não há aprovação manual
        self.assert_not_public(article_id)

    def test_nothing_is_published_without_approval(self):
        for resultados in (["SUPPORTED", "SUPPORTED"], ["REFUTED", "REFUTED"], ["CONFLICTING_EVIDENCE", "SUPPORTED"], ["NOT_ENOUGH_EVIDENCE", "SUPPORTED"]):
            with self.subTest(resultados):
                article_id = self.create_article()
                self.use(VeritAISimulada(resultados))
                article = self.verify(article_id)
                self.assertIn(article["status"], {"AWAITING_REVIEW", "NEEDS_EVIDENCE"})
                self.assert_not_public(article_id)
                for decision in ("request_evidence", "reject"):
                    self.assertEqual(self.decide(article_id, decision).status_code, 200)
                    self.assert_not_public(article_id)
                    article = self.verify(article_id)
                self.assertNotEqual(article["status"], "PUBLISHED")
                self.assert_not_public(article_id)

    def test_report_and_versions_are_stored(self):
        article_id = self.create_article()
        simulada = VeritAISimulada(["SUPPORTED", "CONFLICTING_EVIDENCE"])
        self.use(simulada)
        article = self.verify(article_id)
        esperado = relatorio_simulado(CLAIMS, ["SUPPORTED", "CONFLICTING_EVIDENCE"])
        with connection() as db:
            rows = db.execute("SELECT * FROM analises WHERE article_id=?", (article_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["modo"], "servico")
        self.assertEqual(rows[0]["data_noticia"], simulada.pedidos[0]["noticia"]["data"])
        self.assertEqual(json.loads(rows[0]["relatorio_json"]), esperado)
        self.assertEqual(json.loads(rows[0]["versoes_json"]), esperado["versoes"])
        self.assertEqual(article["analise"]["versoes"], esperado["versoes"])
        self.assertEqual(article["analise"]["avisos"], ["Aviso simulado da análise."])
        claim = article["claims"][0]
        self.assertEqual(claim["relatorio"], esperado["afirmacoes"][0])
        self.assertEqual(claim["texto_publico"], esperado["afirmacoes"][0]["texto_publico"])
        self.assertEqual(claim["evidence"][0]["data_publicacao"], "2026-10-01")

    def test_public_record_shows_only_public_text_and_sources(self):
        article_id = self.create_article()
        self.client.post(f"/publisher/articles/{article_id}/evidence/file", headers=PUBLISHER, files={"file": ("nome-interno.txt", "Documento interno com três parques.".encode(), "text/plain")})

        def com_anexo(pedido):
            relatorio = relatorio_simulado(pedido["afirmacoes"], ["SUPPORTED", "SUPPORTED"])
            relatorio["afirmacoes"][1]["evidencias"][0].update(fonte="nome-interno.txt", url="", origem="anexo")
            return httpx.Response(200, json=relatorio)

        self.use(VeritAISimulada(resposta=com_anexo))
        self.verify(article_id)
        self.assertEqual(self.decide(article_id, "approve").status_code, 200)
        public = self.client.get(f"/articles/{article_id}").json()
        texto = json.dumps(public, ensure_ascii=False)
        self.assertNotIn("analise", public)
        for interno in ("relatorio", "review_note", "attachments", "search_errors", "verdict", "confidence", "checagens", "porcentagem", "nome-interno"):
            self.assertNotIn(interno, texto)
        self.assertEqual(public["claims"][0]["texto_publico"], relatorio_simulado(CLAIMS, ["SUPPORTED", "SUPPORTED"])["afirmacoes"][0]["texto_publico"])
        self.assertEqual(public["claims"][0]["fontes"], [{"titulo": "Diário Oficial do Município", "url": "https://example.org/parques", "data_publicacao": "2026-10-01"}])
        self.assertEqual(public["claims"][1]["fontes"], [{"titulo": "Documento enviado pelo publisher", "url": "", "data_publicacao": None}])
        self.assertTrue(public["verificado_pela_veritai"])
        self.assertEqual({claim["origem_analise"] for claim in public["claims"]}, {"veritai"})
        self.assertFalse(public["anexo_sem_texto"])

    def test_image_without_text_is_flagged_to_reader_even_when_supported(self):
        article_id = self.create_article()
        self.client.post(f"/publisher/articles/{article_id}/evidence/file", headers=PUBLISHER, files={"file": ("foto.png", b"\x89PNG\r\n\x1a\nexample", "image/png")})
        self.use(VeritAISimulada(["SUPPORTED", "SUPPORTED"]))
        self.assertEqual(self.verify(article_id)["status"], "AWAITING_REVIEW")
        self.assertEqual(self.decide(article_id, "approve").status_code, 200)
        public = self.client.get(f"/articles/{article_id}").json()
        self.assertTrue(public["anexo_sem_texto"])
        self.assertFalse(public["manual_review"])
        self.assertNotIn("foto.png", json.dumps(public))


if __name__ == "__main__":
    unittest.main()
