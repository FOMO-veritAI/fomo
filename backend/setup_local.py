"""Cria chaves locais uma vez; não envia nem imprime os segredos."""

import secrets
from pathlib import Path


target = Path(__file__).resolve().parent / ".env"
if target.exists():
    print("Configuração local já existe em backend/.env")
else:
    target.write_text(
        "TAKTA_PUBLISHER_KEY=" + secrets.token_urlsafe(24) + "\n"
        "TAKTA_REVIEWER_KEY=" + secrets.token_urlsafe(24) + "\n"
        "GOOGLE_FACT_CHECK_API_KEY=\n",
        encoding="utf-8",
    )
    target.chmod(0o600)
    print("Chaves criadas em backend/.env. Use-as nas telas Publisher e Revisão.")
