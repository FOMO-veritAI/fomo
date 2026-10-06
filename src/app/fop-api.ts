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
}

export interface FopClaim {
  id: number;
  text: string;
  verdict: FopVerdict;
  explanation: string;
  confidence: string;
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
  manual_review?: boolean;
}

const API = 'http://127.0.0.1:8000';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, options);
  } catch {
    throw new Error('Backend FOP indisponível. Inicie o servidor Python na porta 8000.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Erro ${response.status} ao consultar a FOP.`);
  }
  return response.json() as Promise<T>;
}

export const fopApi = {
  health: () => request<{status: string; publisher_key_configured: boolean; reviewer_key_configured: boolean; google_fact_check_configured: boolean}>('/health'),
  published: () => request<FopArticle[]>('/articles'),
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
