import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class PublicationFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        os.environ["TAKTA_DB_PATH"] = os.path.join(cls.directory.name, "test.sqlite3")
        os.environ["TAKTA_PUBLISHER_KEY"] = "publisher-test-key"
        os.environ["TAKTA_REVIEWER_KEY"] = "reviewer-test-key"
        from backend.app.main import app
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.directory.cleanup()

    def create_article(self):
        response = self.client.post(
            "/publisher/articles",
            headers={"X-Publisher-Key": "publisher-test-key"},
            json={
                "publisher": "Jornal de teste",
                "title": "A cidade abriu três novos parques públicos",
                "summary": "A prefeitura anunciou três novos parques abertos à população.",
                "body": "O município informou que três parques públicos foram abertos neste mês e divulgou o cronograma da inauguração.",
                "topic": "Sociedade",
                "claims": ["A cidade abriu três novos parques públicos."],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_missing_evidence_never_publishes(self):
        article_id = self.create_article()

        async def empty_search(_claim):
            return [], []

        with patch("backend.app.main.search_sources", empty_search), patch("backend.app.main.compare", return_value=[]):
            response = self.client.post(f"/publisher/articles/{article_id}/verify", headers={"X-Publisher-Key": "publisher-test-key"})
        self.assertEqual(response.status_code, 200)
        article = self.client.get(f"/publisher/articles/{article_id}", headers={"X-Publisher-Key": "publisher-test-key"}).json()
        self.assertEqual(article["status"], "NEEDS_EVIDENCE")
        self.assertEqual(article["claims"][0]["verdict"], "NOT_ENOUGH_EVIDENCE")
        self.assertEqual(self.client.get(f"/articles/{article_id}").status_code, 404)
        denied = self.client.post(
            f"/review/articles/{article_id}",
            headers={"X-Reviewer-Key": "reviewer-test-key"},
            json={"decision": "approve", "note": "A notícia ainda não tem fontes independentes."},
        )
        self.assertEqual(denied.status_code, 409)

    def test_supported_article_requires_review_then_appears_publicly(self):
        from backend.app.fop import ScoredEvidence
        from backend.app.retrieval import RetrievedSource

        article_id = self.create_article()
        source = RetrievedSource("https://example.org/parques", "Documento da cidade", "example.org", "A cidade abriu três novos parques públicos para a população nesta semana.", "web")
        scored = [ScoredEvidence(source, source.text, 0.91, "entailment", 0.98)]

        async def source_search(_claim):
            return [source], []

        with patch("backend.app.main.search_sources", source_search), patch("backend.app.main.compare", return_value=scored):
            self.client.post(f"/publisher/articles/{article_id}/verify", headers={"X-Publisher-Key": "publisher-test-key"})
        article = self.client.get(f"/publisher/articles/{article_id}", headers={"X-Publisher-Key": "publisher-test-key"}).json()
        self.assertEqual(article["status"], "AWAITING_REVIEW")
        self.assertEqual(article["claims"][0]["verdict"], "SUPPORTED")
        self.assertEqual(len(article["claims"][0]["evidence"]), 1)
        self.assertEqual(self.client.get(f"/articles/{article_id}").status_code, 404)
        approved = self.client.post(
            f"/review/articles/{article_id}",
            headers={"X-Reviewer-Key": "reviewer-test-key"},
            json={"decision": "approve", "note": "Fonte consultada e texto da afirmação conferido."},
        )
        self.assertEqual(approved.status_code, 200)
        public = self.client.get(f"/articles/{article_id}")
        self.assertEqual(public.status_code, 200)
        self.assertFalse(public.json()["manual_review"])
        self.assertNotIn("review_note", public.json())
        self.assertNotIn("attachments", public.json())

    def test_image_proof_needs_human_review_before_publication(self):
        article_id = self.create_article()
        uploaded = self.client.post(
            f"/publisher/articles/{article_id}/evidence/file",
            headers={"X-Publisher-Key": "publisher-test-key"},
            files={"file": ("prova.png", b"\x89PNG\r\n\x1a\nexample", "image/png")},
        )
        self.assertEqual(uploaded.status_code, 200)

        async def empty_search(_claim):
            return [], []

        with patch("backend.app.main.search_sources", empty_search):
            self.client.post(f"/publisher/articles/{article_id}/verify", headers={"X-Publisher-Key": "publisher-test-key"})
        reviewed = self.client.get(f"/publisher/articles/{article_id}", headers={"X-Publisher-Key": "publisher-test-key"}).json()
        self.assertEqual(reviewed["status"], "NEEDS_EVIDENCE")
        self.assertEqual(self.client.get(f"/articles/{article_id}").status_code, 404)
        approved = self.client.post(
            f"/review/articles/{article_id}",
            headers={"X-Reviewer-Key": "reviewer-test-key"},
            json={"decision": "approve", "note": "A imagem foi conferida manualmente pelo revisor."},
        )
        self.assertEqual(approved.status_code, 200)
        public = self.client.get(f"/articles/{article_id}").json()
        self.assertTrue(public["manual_review"])
        self.assertNotIn("attachments", public)
        self.assertNotIn("review_note", public)

    def test_private_evidence_url_is_rejected(self):
        from backend.app.retrieval import safe_public_url
        self.assertFalse(safe_public_url("http://127.0.0.1/internal"))
        self.assertFalse(safe_public_url("http://192.168.1.1/"))


if __name__ == "__main__":
    unittest.main()
