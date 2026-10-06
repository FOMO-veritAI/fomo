import { Component, EventEmitter, OnDestroy, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { fopApi, FopArticle, FopEvidence, FopStatus } from '../fop-api';
import { IconComponent } from '../icon/icon';

@Component({
  selector: 'app-publisher-console',
  standalone: true,
  imports: [FormsModule, IconComponent],
  templateUrl: './publisher-console.html',
  styleUrl: './publisher-console.css',
})
export class PublisherConsoleComponent implements OnDestroy {
  @Output() published = new EventEmitter<void>();

  tab: 'publisher' | 'reviewer' = 'publisher';
  publisherKey = '';
  reviewerKey = '';
  publisher = '';
  title = '';
  summary = '';
  body = '';
  topic = 'Sociedade';
  claims = '';
  evidenceUrl = '';
  reviewNote = '';
  file: File | null = null;
  articles: FopArticle[] = [];
  queue: FopArticle[] = [];
  current: FopArticle | null = null;
  busy = false;
  error = '';
  message = '';
  private pollTimer?: ReturnType<typeof setInterval>;

  ngOnDestroy(): void { if (this.pollTimer) clearInterval(this.pollTimer); }

  statusLabel(status: FopStatus): string {
    return {
      DRAFT: 'Rascunho', VERIFYING: 'FOP analisando', NEEDS_EVIDENCE: 'Precisa de evidências',
      AWAITING_REVIEW: 'Aguardando revisão', BLOCKED: 'Publicação bloqueada',
      PUBLISHED: 'Publicada', REJECTED: 'Devolvida ao publisher', ERROR: 'Erro na análise',
    }[status];
  }

  hasReviewableAttachment(article: FopArticle): boolean {
    return article.attachments.some((attachment) => Boolean(attachment.file_type));
  }

  relationLabel(relation: string): string {
    return { entailment: 'Apoia', contradiction: 'Contradiz', neutral: 'Não conclusiva' }[relation] ?? 'Não conclusiva';
  }

  private async run(task: () => Promise<void>): Promise<void> {
    this.busy = true;
    this.error = '';
    this.message = '';
    try { await task(); }
    catch (error) { this.error = error instanceof Error ? error.message : 'Não foi possível concluir a operação.'; }
    finally { this.busy = false; }
  }

  async loadPublisher(): Promise<void> {
    await this.run(async () => { this.articles = await fopApi.publisherList(this.publisherKey); this.message = 'Notícias atualizadas.'; });
  }

  async create(): Promise<void> {
    const claimList = this.claims.split('\n').map((value) => value.trim()).filter(Boolean);
    await this.run(async () => {
      this.current = await fopApi.create(this.publisherKey, { publisher: this.publisher, title: this.title, summary: this.summary, body: this.body, topic: this.topic, claims: claimList });
      this.articles.unshift(this.current);
      this.message = 'Rascunho criado. Agora você pode acrescentar fontes ou iniciar a verificação.';
    });
  }

  async select(article: FopArticle): Promise<void> {
    await this.run(async () => { this.current = await fopApi.publisherArticle(this.publisherKey, article.id); });
  }

  async addUrl(): Promise<void> {
    if (!this.current || !this.evidenceUrl) return;
    await this.run(async () => { this.current = await fopApi.addUrl(this.publisherKey, this.current!.id, this.evidenceUrl); this.evidenceUrl = ''; this.message = 'Fonte anexada ao rascunho.'; });
  }

  chooseFile(event: Event): void { this.file = (event.target as HTMLInputElement).files?.[0] ?? null; }

  async addFile(): Promise<void> {
    if (!this.current || !this.file) return;
    await this.run(async () => { this.current = await fopApi.addFile(this.publisherKey, this.current!.id, this.file!); this.file = null; this.message = 'Documento anexado ao rascunho.'; });
  }

  async verify(): Promise<void> {
    if (!this.current) return;
    await this.run(async () => {
      await fopApi.verify(this.publisherKey, this.current!.id);
      this.current = await fopApi.publisherArticle(this.publisherKey, this.current!.id);
      this.message = 'A FOP iniciou a análise. A primeira execução baixa os modelos e pode demorar alguns minutos.';
      this.startPolling();
    });
  }

  private startPolling(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = setInterval(async () => {
      if (!this.current) return;
      try {
        this.current = await fopApi.publisherArticle(this.publisherKey, this.current.id);
        if (this.current.status !== 'VERIFYING') {
          if (this.pollTimer) clearInterval(this.pollTimer);
          this.pollTimer = undefined;
          this.message = 'Análise concluída. Consulte os resultados abaixo.';
        }
      } catch { if (this.pollTimer) clearInterval(this.pollTimer); }
    }, 3000);
  }

  async loadReview(): Promise<void> {
    await this.run(async () => { this.queue = await fopApi.reviewList(this.reviewerKey); this.message = 'Fila de revisão atualizada.'; });
  }

  async downloadAttachment(attachment: FopEvidence): Promise<void> {
    await this.run(() => fopApi.downloadAttachment(this.reviewerKey, attachment));
  }

  async decide(article: FopArticle, decision: 'approve' | 'reject' | 'request_evidence'): Promise<void> {
    await this.run(async () => {
      await fopApi.decide(this.reviewerKey, article.id, decision, this.reviewNote);
      this.queue = await fopApi.reviewList(this.reviewerKey);
      this.reviewNote = '';
      this.message = decision === 'approve' ? 'Notícia aprovada e publicada.' : 'Decisão registrada.';
      if (decision === 'approve') this.published.emit();
    });
  }
}
