import unittest

import apoio  # noqa: F401  (configura banco temporário antes de importar o app)
from fastapi.testclient import TestClient


class HealthTest(unittest.TestCase):
    def test_nao_expoe_caminho_do_banco(self):
        from backend.app import config
        from backend.app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn("database", response.json())
        self.assertNotIn(str(config.DB_PATH), response.text)
        self.assertNotIn(str(config.DB_PATH).replace("\\", "\\\\"), response.text)


if __name__ == "__main__":
    unittest.main()
