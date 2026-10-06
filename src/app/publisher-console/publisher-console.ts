import { ChangeDetectorRef, Component, EventEmitter, inject, OnDestroy, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { fopApi, FopArticle, FopClaim, FopEvidence, FopStatus, VeritaiRelatorioAfirmacao } from '../fop-api';

// Mesmos limites do backend e do contrato da VeritAI.
const CLAIM_MIN = 10;
const CLAIM_MAX = 500;
const CLAIM_COUNT = 8;
import { IconComponent } from '../icon/icon';
import { VeritaiMarkComponent } from '../veritai-mark/veritai-mark';
import { RELACAO, RESULTADO, SEM_RESULTADO } from '../veritai-mark/veritai-icones';

@Component({
  selector: 'app-publisher-console',
  standalone: true,
  imports: [FormsModule, IconComponent, VeritaiMarkComponent],
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
  // O app roda sem zone.js: respostas assíncronas precisam pedir nova renderização.
  private readonly changes = inject(ChangeDetectorRef);

  ngOnDestroy(): void { if (this.pollTimer) clearInterval(this.pollTimer); }

  statusLabel(status: FopStatus): string {
    return {
      DRAFT: 'Rascunho', VERIFYING: 'Em análise automática', NEEDS_EVIDENCE: 'Precisa de evidências',
      AWAITING_REVIEW: 'Aguardando revisão', BLOCKED: 'Publicação bloqueada',
      PUBLISHED: 'Publicada', REJECTED: 'Devolvida ao publisher', ERROR: 'Erro na análise',
    }[status];
  }

  hasReviewableAttachment(article: FopArticle): boolean {
    return article.attachments.some((attachment) => Boolean(attachment.file_type));
  }

  relationLabel(relation: string): string {
    return (RELACAO[relation] ?? RELACAO['neutro']).text;
  }

  // Resultados e relações sem cor: ícone + texto, com a mesma tabela em todo o app (veritai-icones.ts).
  resultInfo(result: string): { icon: string; text: string } {
    return RESULTADO[result] ?? SEM_RESULTADO;
  }

  relationIcon(relation: string): string {
    return (RELACAO[relation] ?? RELACAO['neutro']).icon;
  }

  originLabel(origin: string): string {
    return ({
      busca_web: 'busca na web', checagem_externa: 'checagem externa', link_publisher: 'link do publisher', anexo: 'anexo do publisher', base_propria: 'base própria',
      publisher_url: 'link do publisher', publisher_document: 'texto extraído', manual_attachment: 'conferência humana',
    } as Record<string, string>)[origin] ?? origin;
  }

  // Sem porcentagem calibrada, nunca mostra número: só "Não avaliável" e o motivo.
  percentLabel(report: VeritaiRelatorioAfirmacao): string {
    if (report.avaliavel && report.porcentagem !== null) return `Porcentagem informada pela VeritAI: ${report.porcentagem}`;
    const reason = ({
      modelo_nao_calibrado: 'o modelo ainda não foi calibrado', evidencia_insuficiente: 'evidência insuficiente', so_anexo_sem_texto: 'só há anexos sem texto, que exigem conferência humana',
    } as Record<string, string>)[report.motivo_nao_avaliavel ?? ''];
    return reason ? `Não avaliável (${reason})` : 'Não avaliável';
  }

  isContradicted(claim: FopClaim): boolean {
    return (claim.relatorio?.resultado ?? claim.verdict) === 'REFUTED';
  }

  hasContradiction(article: FopArticle): boolean {
    return article.claims.some((claim) => this.isContradicted(claim));
  }

  get claimList(): string[] {
    return this.claims.split('\n').map((value) => value.trim()).filter(Boolean);
  }

  get claimProblems(): string[] {
    const claims = this.claimList;
    const problems = claims.flatMap((claim, index) => claim.length < CLAIM_MIN || claim.length > CLAIM_MAX ? [`A afirmação ${index + 1} tem ${claim.length} caracteres; use entre ${CLAIM_MIN} e ${CLAIM_MAX}.`] : []);
    if (claims.length > CLAIM_COUNT) problems.push(`Informe até ${CLAIM_COUNT} afirmações (há ${claims.length}).`);
    return problems;
  }

  private async run(task: () => Promise<void>): Promise<void> {
    this.busy = true;
    this.error = '';
    this.message = '';
    try { await task(); }
    catch (error) { this.error = error instanceof Error ? error.message : 'Não foi possível concluir a operação.'; }
    finally { this.busy = false; this.changes.markForCheck(); }
  }

  async loadPublisher(): Promise<void> {
    await this.run(async () => { this.articles = await fopApi.publisherList(this.publisherKey); this.message = 'Notícias atualizadas.'; });
  }

  async create(): Promise<void> {
    const claimList = this.claimList;
    if (!claimList.length || this.claimProblems.length) {
      this.error = this.claimProblems.join(' ') || 'Informe pelo menos uma afirmação factual.';
      return;
    }
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
      this.message = 'A análise automática começou. A primeira execução baixa os modelos e pode demorar alguns minutos.';
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
          this.message = this.current.status === 'ERROR' ? '' : 'Análise concluída. A notícia aguarda a decisão de um revisor humano.';
          if (this.current.status === 'ERROR') this.error = this.current.search_errors.join(' ') || 'A análise falhou. Tente novamente.';
        }
      } catch { if (this.pollTimer) clearInterval(this.pollTimer); }
      this.changes.markForCheck();
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
