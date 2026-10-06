# Instruções para agentes: FOMO

Este arquivo vale para qualquer agente que trabalhe neste repositório (Claude Code, Codex e outros). Responda e escreva em português do Brasil.

## O projeto

O **FOMO** (*Fear of Missing Objectivity*) é uma plataforma de notícias em que nenhuma matéria chega ao leitor sem verificação. Antes se chamava **TAKTA**; nomes antigos ainda aparecem em variáveis (`TAKTA_*`), no banco (`takta.sqlite3`) e no pacote do frontend. O publisher cria uma notícia, informa as afirmações factuais e anexa links, documentos ou imagens. A **VeritAI**, serviço de IA separado ([FOMO-veritAI/veritai](https://github.com/FOMO-veritAI/veritai)), analisa cada afirmação e devolve um relatório. **A decisão de publicar é sempre de um revisor humano**, no FOMO: só a aprovação do revisor publica a notícia no feed.

Contexto acadêmico: Challenge 1 (Fake News / Desinformação) de uma residência em IA. Pergunta central: como a IA ajuda a avaliar a confiabilidade de informações sem substituir o pensamento crítico.

## Arquitetura

- **Frontend** Angular (`src/`): feed do leitor, área do publisher e fila de revisão. Fala com a API em `http://127.0.0.1:8000`.
- **API** FastAPI (`backend/app/`): notícias, afirmações, evidências, anexos, análises e decisões em SQLite (`backend/data/`).
- **VeritAI** (outro repositório): `POST /analisar`, chamada pelo cliente `backend/app/veritai_client.py` em `VERITAI_URL` (padrão `http://127.0.0.1:8100`).

Fluxo: `DRAFT` → `VERIFYING` → `NEEDS_EVIDENCE` (alguma afirmação sem evidência suficiente) ou `AWAITING_REVIEW` (todas as demais, inclusive com afirmação contradita) ou `ERROR` (falha da VeritAI) → decisão do revisor: `PUBLISHED`, `REJECTED` ou `NEEDS_EVIDENCE`.

## Estado atual (diferencie sempre implementado de planejado)

Implementado: cadastro de notícias com até 8 afirmações de 10 a 500 caracteres; evidências por link público (HTML) e por arquivo (TXT e PDF com texto extraído no FOMO; PNG e JPG só para conferência humana); chaves locais de publisher e revisor em `backend/.env`; integração com a VeritAI por HTTP (`VERITAI_MODO=servico`, padrão); relatório completo e `versoes` de cada análise guardados na tabela `analises`; revisão humana obrigatória; feed com o texto público por afirmação e as fontes.

Mantido por compatibilidade: o pipeline antigo embutido (`fop.py` e `retrieval.py`, similaridade + NLI locais), ativado com `VERITAI_MODO=embutido`. Ele não produz relatório da VeritAI e será removido quando o serviço estiver estável. O status `BLOCKED` não é mais gerado; existe só para registros antigos, que podem ser reenviados para análise.

Planejado: identidade institucional de publishers e revisores, isolamento entre publishers, conferência de autenticidade de documentos, infraestrutura de produção.

## Regras que nunca podem ser quebradas

- **Nada é publicado sem aprovação de um revisor humano.** Só `POST /review/articles/{id}` com `approve` grava `PUBLISHED`. Afirmação contradita vai para revisão (em destaque), não é bloqueada nem publicada automaticamente.
- **Esta sessão não altera a IA.** Modelos, limiares, busca e regras de decisão ficam no serviço VeritAI. Aqui só se consome o relatório.
- Falha da VeritAI (fora do ar, timeout, erro HTTP, resposta fora do contrato) leva a notícia para `ERROR` com mensagem clara; nunca para publicação.
- `buscar_na_web` é decidido pelo servidor (`VERITAI_BUSCAR_WEB`, padrão `true`), nunca pelo publisher, para que ele não desligue a busca e envie só evidências favoráveis.
- `noticia.data` é o dia em que a verificação foi pedida (chamada a `/verify`), no fuso `America/Sao_Paulo`, formato AAAA-MM-DD. Não use a data de criação do rascunho.

### Regras de exibição

- Resultado **por afirmação**; nunca média, resumo ou selo por notícia.
- Mostre o `texto_publico` da VeritAI ("Resultado da verificação VeritAI: …"). Não use "Suportada" ou "Refutada" isolados.
- `porcentagem` vem `null` enquanto o modelo não for calibrado: mostre **"Não avaliável"** e o motivo. Nunca invente número.
- `checagens_anteriores` aparecem como **"checagens candidatas, a conferir"**, com o veredito original da agência atribuído a ela; nunca como veredito do FOMO ou da VeritAI.
- Revisor vê: texto público, "Não avaliável", justificativa, fontes independentes, evidências (fonte, data, trecho, relação, origem), checagens candidatas, limitações e avisos.
- Leitor vê: notícia aprovada, texto público por afirmação e as fontes. Notas internas, anexos e o relatório completo não saem na API pública.
- Só atribua à VeritAI o que tem relatório da VeritAI. Afirmações analisadas pelo pipeline embutido ou antigas aparecem como "verificação automática anterior (sem VeritAI)" (`origem_analise` e `verificado_pela_veritai` na API pública).
- Imagens e documentos sem texto não são avaliados pela IA: exigem conferência humana, e a notícia pública indica essa condição (`anexo_sem_texto`) sempre que houver um, qualquer que seja o resultado das afirmações.
- As notícias de "Exemplos visuais" são fictícias e não podem servir de evidência nem de dado de treino.

### Identidade visual

- **FOMO** (cabeçalho, feed, notícia, publisher): pop-art/quadrinhos. Preto `#000`, off-white `#F0F0F0`, vermelho `#FF3333` só em destaque (marca, botão principal, ícones, títulos grandes). Vermelho nunca em texto pequeno; botão vermelho tem texto **preto** (5,8:1). Bangers só em marca e destaques; manchetes e texto em Inter.
- **VeritAI** (bloco do leitor e relatório do revisor): preto sobre branco, sem cor, moldura fina; "*Verit*" em Newsreader itálico + "**AI**" em Inter 900 (`app-veritai-mark`), legenda "(IN FOMO)".
- Resultados (apoiam, contradizem, insuficientes, conclusões diferentes) nunca usam vermelho nem verde: só ícone + texto. O vermelho da marca não pode significar "falso".
- Logos: originais em `public/brand/` (não alterar); versões recortadas em `public/brand/web/`, sempre como imagem com `alt`. Monograma FM! é o favicon.
- Acessibilidade: texto com contraste mínimo de 4,5:1, foco visível (contorno preto + anel branco), sem rolagem horizontal em 360 px. Tokens em `src/styles.css` (`:root`) e camada da marca em `src/brand.css`.

## Contrato com a VeritAI

O contrato é `veritai/relatorio.py` no repositório veritai. A cópia usada aqui está em `backend/app/veritai_contrato.py`, com o commit de origem no cabeçalho; atualize as duas juntas. Não assuma campos que não estejam no contrato. O FOMO valida o pedido antes de enviar (afirmações de 10 a 500 caracteres, URLs http(s) com domínio válido, limites de quantidade) e valida a resposta ao receber.

## Como rodar e testar

Detalhes no `README.md`. Resumo:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/setup_local.py
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm install && npm start
.venv/bin/python -m unittest discover -s backend/tests -v
npm run build
```

A VeritAI precisa estar rodando em `VERITAI_URL` (no repositório veritai: `docker compose up -d`). Os testes simulam a VeritAI com `httpx.MockTransport` e não dependem do serviço real. Rode testes e build antes de considerar qualquer tarefa concluída e informe o resultado real.

## Segurança e git

- Nunca leia, imprima ou envie o conteúdo de `backend/.env`. Segredos só em variáveis de ambiente.
- Não versione `backend/data/` (banco e uploads), `*.sqlite3`, modelos nem ambientes virtuais.
- Mensagens de erro e logs não podem conter chaves nem conteúdo de anexos.
- Commits pequenos, com testes passando. Não faça push sem autorização do desenvolvedor.
- Escreva código no estilo do que já existe; comentários curtos só onde o motivo não é óbvio.
