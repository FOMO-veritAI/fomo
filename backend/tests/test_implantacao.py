import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import apoio  # noqa: F401  (configura banco temporário e VeritAI simulada antes de importar o app)
from fastapi.testclient import TestClient

from backend.app.db import connection, now

RAIZ = Path(__file__).resolve().parents[2]


class DeployTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.app.main import app
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def insert_article(self, status: str) -> int:
        with connection() as db:
            return db.execute(
                "INSERT INTO articles (publisher,title,body,summary,topic,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                ("Jornal de teste", "Notícia em análise no reinício", "Texto da notícia.", "Resumo.", "Sociedade", status, now(), now()),
            ).lastrowid

    def status(self, article_id: int) -> tuple[str, list[str]]:
        with connection() as db:
            row = db.execute("SELECT status,search_errors FROM articles WHERE id=?", (article_id,)).fetchone()
        return row["status"], json.loads(row["search_errors"] or "[]")

    def test_restart_turns_interrupted_analysis_into_error(self):
        from backend.app.main import INTERRUPTED_MESSAGE, recover_interrupted_verifications
        interrupted, draft = self.insert_article("VERIFYING"), self.insert_article("DRAFT")
        recover_interrupted_verifications()
        self.assertEqual(self.status(interrupted), ("ERROR", [INTERRUPTED_MESSAGE]))
        self.assertEqual(self.status(draft)[0], "DRAFT")

    def test_service_mode_does_not_import_torch(self):
        # Em processo novo: outro teste poderia ter importado torch neste.
        codigo = "import sys; import backend.app.main; sys.exit(1 if 'torch' in sys.modules else 0)"
        resultado = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=os.environ.copy(), capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr or "torch foi importado com VERITAI_MODO=servico")


if __name__ == "__main__":
    unittest.main()
