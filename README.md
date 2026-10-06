# TAKTA + FOP

Frontend Angular e API local de verificação pré-publicação. O publisher cria uma notícia, informa até oito afirmações factuais e pode anexar links, documentos ou imagens. A FOP pesquisa fontes públicas, compara trechos por similaridade semântica e NLI e envia a análise para revisão humana. Só a decisão de aprovação publica a notícia no feed.

## Rodar localmente

Requisitos: Node.js compatível com Angular 22, npm e Python 3.11 ou mais recente. Execute os comandos a partir desta pasta.

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

Na primeira análise com fontes, os modelos de linguagem são baixados e a operação pode levar alguns minutos. Sem fontes legíveis, a notícia vai para **Precisa de evidências**. Quando a comparação encontra apoio ou conclusões diferentes, ela vai para **Aguardando revisão**. Contradição detectada bloqueia a publicação até nova análise. Um revisor pode aprovar, devolver ou pedir comprovação; só a aprovação publica. Se houver documento ou imagem anexado, o revisor pode aprovar após conferência manual mesmo quando a comparação textual for insuficiente; a notícia pública identifica essa condição.

## Fontes e limites do MVP

A busca usa Bing News RSS e GDELT; a API do Google Fact Check Tools é opcional. Para ativá-la, preencha `GOOGLE_FACT_CHECK_API_KEY` em `backend/.env` e reinicie a API. O sistema consulta páginas públicas em HTML e aceita links fornecidos pelo publisher. Documentos TXT e PDFs com texto extraível entram na comparação; PNG e JPG ficam disponíveis para revisão humana, sem análise automática da imagem.

Os resultados expressam a relação entre uma afirmação e os trechos encontrados: evidências que apoiam, contradizem, são insuficientes ou apresentam conclusões diferentes. A indicação de confiança mede a consistência dessa comparação textual; **não é porcentagem de verdade nem garantia de veracidade**. Busca incompleta, fontes copiadas umas das outras, documentos falsos e erros dos modelos exigem julgamento humano. Neste MVP, as chaves são locais e compartilhadas; ainda não há cadastro institucional, identidade verificada, isolamento entre publishers, revisão de autenticidade de documentos ou infraestrutura de produção.

As notícias da seção **Exemplos visuais** permanecem fictícias para demonstrar o protótipo. Notícias criadas e aprovadas no fluxo FOP aparecem separadamente em **Notícias publicadas**, vindas da API local. O frontend usa `http://127.0.0.1:8000` como endereço da API, portanto este setup é para uso local.

## Verificação do projeto

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
npm run build
```

O build do Angular sai em `dist/`. A versão HTML anterior está preservada em `legacy-static/` como referência de migração.
