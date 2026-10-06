# FOMO

Plataforma de notícias com verificação pré-publicação (antes chamada TAKTA). O publisher cria uma notícia, informa até oito afirmações factuais (de 10 a 500 caracteres cada) e pode anexar links, documentos ou imagens. A **VeritAI**, serviço de IA separado ([FOMO-veritAI/veritai](https://github.com/FOMO-veritAI/veritai)), analisa cada afirmação e devolve um relatório com evidências, fontes, justificativa e limitações. Toda notícia analisada vai para revisão humana; só a aprovação de um revisor publica a notícia no feed. Instruções para agentes de código estão em `AGENTS.md`.

## Rodar localmente

Requisitos: Node.js compatível com Angular 22, npm, Python 3.11 ou mais recente e a VeritAI rodando (no repositório veritai: `docker compose up -d`, que a expõe em `http://127.0.0.1:8100`). Execute os comandos a partir desta pasta.

No primeiro terminal, instale e inicie a API:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/setup_local.py
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

No segundo terminal, inicie o Angular:

```bash
npm install
npm start
```

Abra `http://localhost:4200` e entre em **Publicar notícia**. As chaves locais para as abas **Publisher** e **Revisão** estão em `backend/.env`. O arquivo é criado só na primeira execução e não deve ser compartilhado. A API oferece documentação interativa em `http://127.0.0.1:8000/docs` e saúde em `http://127.0.0.1:8000/health`.

### Integração com a VeritAI

| Variável | Padrão | Para quê |
|---|---|---|
| `VERITAI_MODO` | `servico` | `servico` chama a VeritAI por HTTP; `embutido` usa o pipeline antigo (`fop.py` e `retrieval.py`), mantido por compatibilidade. |
| `VERITAI_URL` | `http://127.0.0.1:8100` | Endereço da VeritAI. |
| `VERITAI_TIMEOUT` | `600` | Segundos de espera pela análise; a primeira baixa os modelos. |
| `VERITAI_BUSCAR_WEB` | `true` | Se a VeritAI busca fontes na web. Decisão do servidor: o publisher não altera. |

O FOMO extrai o texto de PDF e TXT e envia à VeritAI a notícia (título, texto e data do pedido de verificação, no fuso de São Paulo), as afirmações, as evidências com texto e a quantidade de anexos sem texto. O relatório completo e as versões dos modelos de cada análise ficam na tabela `analises`. Se a VeritAI estiver fora do ar ou devolver algo fora do contrato, a notícia vai para **Erro na análise** e pode ser reenviada.

### Estados e revisão

Se alguma afirmação não tiver evidência suficiente, a notícia vai para **Precisa de evidências**. Nos demais casos, inclusive quando as evidências contradizem uma afirmação, ela vai para **Aguardando revisão**, e a afirmação contradita aparece em destaque para o revisor. Um revisor pode aprovar, devolver ou pedir comprovação; só a aprovação publica. Se houver documento ou imagem anexado, o revisor pode aprovar após conferência manual mesmo quando a comparação textual for insuficiente; a notícia pública identifica essa condição.

## Fontes e limites do MVP

A busca de fontes (Bing News RSS, GDELT, base própria e, opcionalmente, Google Fact Check) é feita pela VeritAI; no modo embutido, pelo `retrieval.py`. O FOMO lê páginas públicas em HTML informadas pelo publisher. Documentos TXT e PDFs com texto extraível entram na comparação; PNG e JPG ficam disponíveis para revisão humana, sem análise automática da imagem.

Os resultados são **por afirmação** e expressam a relação entre ela e os trechos encontrados: evidências que apoiam, contradizem, são insuficientes ou apresentam conclusões diferentes. Enquanto a VeritAI não tiver calibração, não há porcentagem: a interface mostra **"Não avaliável"**. Checagens anteriores aparecem para o revisor como **checagens candidatas, a conferir**, nunca como veredito. Busca incompleta, fontes copiadas umas das outras, documentos falsos e erros dos modelos exigem julgamento humano. Neste MVP, as chaves são locais e compartilhadas; ainda não há cadastro institucional, identidade verificada, isolamento entre publishers, revisão de autenticidade de documentos ou infraestrutura de produção.

As notícias da seção **Exemplos visuais** permanecem fictícias para demonstrar o protótipo. Notícias criadas e aprovadas no fluxo de verificação aparecem separadamente em **Notícias publicadas**, vindas da API local. O frontend usa `http://127.0.0.1:8000` como endereço da API, portanto este setup é para uso local.

## Verificação do projeto

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
npm run build
```

Os testes simulam a VeritAI com `httpx.MockTransport` e não dependem do serviço real.

O build do Angular sai em `dist/`. A versão HTML anterior está preservada em `legacy-static/` como referência de migração.
