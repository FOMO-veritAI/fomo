export type FopStatus = 'DRAFT' | 'VERIFYING' | 'NEEDS_EVIDENCE' | 'AWAITING_REVIEW' | 'BLOCKED' | 'PUBLISHED' | 'REJECTED' | 'ERROR';
export type FopVerdict = 'SUPPORTED' | 'REFUTED' | 'NOT_ENOUGH_EVIDENCE' | 'CONFLICTING_EVIDENCE';

export interface FopEvidence {
  id: number;
  origin: string;
  source_url: string;
  source_title: string;
  source_domain: string;
  excerpt: string;
  relation: string;
  similarity: number;
  nli_score: number;
  file_type: string;
  data_publicacao?: string | null;
}

// Contrato da VeritAI (backend/app/veritai_contrato.py): só os campos que a interface usa.
export interface VeritaiEvidencia {
  fonte: string;
  url: string;
  data_publicacao: string | null;
  trecho: string;
  relacao: 'apoia' | 'contradiz' | 'neutro';
  origem: 'busca_web' | 'checagem_externa' | 'link_publisher' | 'anexo' | 'base_propria';
}

export interface VeritaiChecagem {
  agencia: string;
  data: string | null;
  url: string;
  alegacao_checada: string;
  veredito: string;
}

export interface VeritaiRelatorioAfirmacao {
  afirmacao: string;
  resultado: FopVerdict;
  texto_publico: string;
  avaliavel: boolean;
  porcentagem: number | null;
  motivo_nao_avaliavel: 'modelo_nao_calibrado' | 'evidencia_insuficiente' | 'so_anexo_sem_texto' | null;
  fontes_independentes: number;
  evidencias: VeritaiEvidencia[];
  checagens_anteriores: VeritaiChecagem[];
  justificativa: string;
  limitacoes: string[];
}

export interface FopAnalise {
  id: number;
  modo: string;
  data_noticia: string;
  criado_em: string;
  versoes: Record<string, string>;
  avisos: string[];
}

export interface FopClaim {
  id: number;
  text: string;
  verdict: FopVerdict;
  explanation: string;
  confidence: string;
  texto_publico: string;
  relatorio: VeritaiRelatorioAfirmacao | null;
  evidence: FopEvidence[];
}

export interface FopArticle {
  id: number;
  publisher: string;
  title: string;
  summary: string;
  body: string;
  topic: string;
  status: FopStatus;
  created_at: string;
  updated_at: string;
  review_note: string;
  search_errors: string[];
  claims: FopClaim[];
  attachments: FopEvidence[];
  analise: FopAnalise | null;
}

// O que o leitor recebe: texto público por afirmação e fontes, sem relatório interno.
export interface FopPublicSource {
  titulo: string;
  url: string;
  data_publicacao: string | null;
}

export interface FopPublicArticle {
  id: number;
  publisher: string;
  title: string;
  summary: string;
  body: string;
  topic: string;
  created_at: string;
  claims: { id: number; text: string; origem_analise: 'veritai' | 'pipeline_anterior'; texto_publico: string; fontes: FopPublicSource[] }[];
  verificado_pela_veritai: boolean;
  manual_review: boolean;
  anexo_sem_texto: boolean;
}

const API = 'http://127.0.0.1:8000';

// Erros de validação do FastAPI chegam como lista; mostra só as mensagens.
function errorDetail(detail: unknown): string {
  if (Array.isArray(detail)) return detail.map((item) => String(item?.msg ?? '').replace(/^Value error, /, '')).filter(Boolean).join(' ');
  return typeof detail === 'string' ? detail : '';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, options);
  } catch {
    throw new Error('API do FOMO indisponível. Inicie o servidor Python na porta 8000.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(errorDetail(data.detail) || `Erro ${response.status} ao consultar a API.`);
  }
  return response.json() as Promise<T>;
}

export const fopApi = {
  published: () => request<FopPublicArticle[]>('/articles'),
  publisherList: (key: string) => request<FopArticle[]>('/publisher/articles', { headers: { 'X-Publisher-Key': key } }),
  publisherArticle: (key: string, id: number) => request<FopArticle>(`/publisher/articles/${id}`, { headers: { 'X-Publisher-Key': key } }),
  create: (key: string, payload: {publisher: string; title: string; summary: string; body: string; topic: string; claims: string[]}) => request<FopArticle>('/publisher/articles', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Publisher-Key': key }, body: JSON.stringify(payload) }),
  addUrl: (key: string, id: number, url: string) => request<FopArticle>(`/publisher/articles/${id}/evidence/url`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Publisher-Key': key }, body: JSON.stringify({ url }) }),
  addFile: (key: string, id: number, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<FopArticle>(`/publisher/articles/${id}/evidence/file`, { method: 'POST', headers: { 'X-Publisher-Key': key }, body });
  },
  verify: (key: string, id: number) => request<{id: number; status: FopStatus}>(`/publisher/articles/${id}/verify`, { method: 'POST', headers: { 'X-Publisher-Key': key } }),
  reviewList: (key: string) => request<FopArticle[]>('/review/articles', { headers: { 'X-Reviewer-Key': key } }),
  async downloadAttachment(key: string, attachment: FopEvidence): Promise<void> {
    const response = await fetch(`${API}/review/attachments/${attachment.id}`, { headers: { 'X-Reviewer-Key': key } });
    if (!response.ok) throw new Error('Não foi possível baixar o anexo.');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = attachment.source_title;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
  decide: (key: string, id: number, decision: 'approve' | 'reject' | 'request_evidence', note: string) => request<FopArticle>(`/review/articles/${id}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Reviewer-Key': key }, body: JSON.stringify({ decision, note }) }),
};
