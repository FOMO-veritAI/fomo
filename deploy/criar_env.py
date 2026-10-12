"""Cria deploy/.env a partir do .env.example, com chaves aleatórias; não imprime os segredos."""

import secrets
from pathlib import Path


pasta = Path(__file__).resolve().parent
destino = pasta / ".env"
if destino.exists():
    print("deploy/.env já existe; nada foi alterado.")
else:
    linhas = []
    for linha in (pasta / ".env.example").read_text(encoding="utf-8").splitlines():
        if linha in {"TAKTA_PUBLISHER_KEY=", "TAKTA_REVIEWER_KEY="}:
            linha += secrets.token_urlsafe(24)
        linhas.append(linha)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    destino.chmod(0o600)
    print("deploy/.env criado com chaves novas. Ajuste o DOMINIO antes de subir.")
