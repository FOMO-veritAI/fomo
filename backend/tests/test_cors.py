import unittest

import apoio  # noqa: F401  (define FOMO_CORS_ORIGINS antes de importar o app)
from fastapi.testclient import TestClient


class CorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.app.main import app
        cls.client = TestClient(app)

    def preflight(self, origem: str):
        return self.client.options("/articles", headers={"Origin": origem, "Access-Control-Request-Method": "GET"})

    def test_aceita_origens_locais_e_configuradas(self):
        for origem in ("http://localhost:4200", "https://fomo.teste", "https://outro.teste"):
            with self.subTest(origem=origem):
                response = self.preflight(origem)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origem)

    def test_aceita_escrita_com_chaves_da_origem_configurada(self):
        for caminho, chave in (("/publisher/articles", "X-Publisher-Key"), ("/review/articles/1", "X-Reviewer-Key")):
            with self.subTest(caminho=caminho):
                response = self.client.options(caminho, headers={
                    "Origin": "https://fomo.teste", "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": f"{chave}, Content-Type",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("access-control-allow-origin"), "https://fomo.teste")

    def test_recusa_origem_nao_configurada(self):
        response = self.preflight("https://intruso.teste")
        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "https://intruso.teste")


if __name__ == "__main__":
    unittest.main()
