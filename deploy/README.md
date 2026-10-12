# Deploy do FOMO com a VeritAI

Uma máquina, três contêineres, com Docker Compose:

```
internet ──► web (Caddy: HTTPS, frontend em /, API em /api) ──► fomo-api (FastAPI, SQLite) ──► veritai (rede interna)
```

- **web:** frontend Angular e proxy para a API na mesma origem, sem CORS. Certificado HTTPS automático (Let's Encrypt).
- **fomo-api:** API do FOMO, sem torch. Banco e anexos ficam no volume `fomo-data`. Uma réplica só.
- **veritai:** modelos do perfil dentro da imagem e base de evidências no volume `veritai-data`. **Não publica porta**: a API da VeritAI não tem autenticação, e só a API do FOMO a alcança.

## Requisitos

- Linux com Docker e Compose v2, em ARM (Graviton, Ampere) ou x86. As imagens são construídas na própria máquina.
- **RAM:** 8 GB com a V1 (pico medido da VeritAI: 3,6 GB) ou 4 GB com a V0 (2,2 GB). A API do FOMO e o Caddy somam pouco.
- **Disco:** cerca de 10 GB para imagens, modelos e volumes.
- **Domínio** apontando para a máquina, com as portas 80 e 443 abertas, para o HTTPS. Sem domínio próprio, um subdomínio gratuito (DuckDNS, por exemplo) serve.
- O repositório `veritai` ao lado do `fomo`, como em `fomo-veritai-local/` ou nos clones da organização lado a lado: o compose constrói a VeritAI a partir de `../../veritai`.

## Passo a passo

```bash
cd fomo/deploy
python3 criar_env.py                  # cria .env com chaves aleatórias (não as imprime)
nano .env                             # DOMINIO e, se quiser, VERITAI_PERFIL=v0
docker compose build                  # a VeritAI baixa os modelos para dentro da imagem (1,7 GB na V1)
mkdir -p base && cp ../../veritai/data/veritai.sqlite3 base/
docker compose --profile base run --rm carregar-base
docker compose up -d
docker compose ps                     # os três serviços "healthy" ou "running"
```

Abra `https://SEU_DOMINIO`. As chaves das telas Publisher e Revisão estão em `deploy/.env`, que não vai para o git. Não compartilhe esse arquivo fora do grupo.

A primeira análise depois de ligar carrega os modelos e leva de 30 a 90 s a mais. As seguintes levam alguns segundos por afirmação, conforme a CPU.

## Base de evidências

A VeritAI deste repositório usa o esquema 2 da base. A base em `veritai/data/` já foi migrada. Se ela vier de `artefatos/veritai.sqlite3.gz`, migre antes de copiar, no ambiente da VeritAI:

```bash
python -m veritai.base migrar && python -m veritai.base periodos
```

Para atualizar a base, copie o arquivo novo para `deploy/base/`, rode de novo o `carregar-base` e depois `docker compose restart veritai`. Sem base, a VeritAI funciona só com os anexos do publisher (e a web, se ligada).

## Teste na própria máquina

No `.env`: `DOMINIO=http://localhost` e `PORTA_HTTP=8080`. Depois de `docker compose up -d`, abra `http://localhost:8080`. Sem HTTPS, só para testar.

## Frontend no GitHub Pages (opcional)

O Caddy já serve o frontend. Para usar também a página do GitHub Pages:

- defina a variável do repositório `FOMO_API_URL=https://SEU_DOMINIO/api`;
- ponha `FOMO_CORS_ORIGINS=https://fomo-veritai.github.io` no `.env` e rode `docker compose up -d`.

## Operação

| Tarefa | Comando |
|---|---|
| Logs | `docker compose logs -f fomo-api` (ou `veritai`, `web`) |
| Atualizar o código | `git pull && docker compose up -d --build` |
| Trocar de perfil | `VERITAI_PERFIL` no `.env`, depois `docker compose up -d --build` (cada perfil tem o próprio volume de modelos) |
| Backup do banco e dos anexos | `docker run --rm -v fomo_fomo-data:/dados -v "$PWD":/backup alpine tar czf /backup/fomo-data.tgz -C /dados .` |
| Desligar | `docker compose down` (os volumes continuam; `down -v` apaga tudo) |

Se a API reiniciar no meio de uma análise, a notícia vai para **Erro na análise** e pode ser reenviada.

## Segurança e decisões em aberto

- **A VeritAI nunca deve ganhar `ports`** no compose: ela aceita qualquer chamada.
- **As chaves são compartilhadas,** como no MVP local: quem tiver a do publisher envia notícias. Identidade institucional continua planejada.
- **Busca na web desligada por padrão** (`VERITAI_BUSCAR_WEB=false`). Ligada, ela manda termos de notícias ainda não publicadas ao Bing e ao GDELT, o que contraria o item W12 do fluxo de IA. É decisão do grupo.
- **Texto de notícia não publicada fica no servidor:** banco e anexos no volume `fomo-data`. Escolha provedor e região considerando a LGPD (uso acadêmico, sem parecer jurídico ainda).
