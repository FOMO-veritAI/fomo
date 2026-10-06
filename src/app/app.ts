import { CommonModule, DOCUMENT } from '@angular/common';
import { ChangeDetectorRef, Component, ElementRef, HostListener, inject, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AUDIO, ARTICLES, COMMUNITIES, CRITIQUES, VIDEO_CLIPS } from './data';
import { Article, CommentItem, Community, Critique, ViewName } from './models';
import { IconComponent } from './icon/icon';
import { NewsCardComponent } from './news-card/news-card';
import { AudioPlayerComponent } from './audio-player/audio-player';
import { FopPublicArticle, fopApi } from './fop-api';
import { VeritaiMarkComponent } from './veritai-mark/veritai-mark';
import { RELACAO, RESULTADO } from './veritai-mark/veritai-icones';
import { PublisherConsoleComponent } from './publisher-console/publisher-console';

type PanelKind = 'evidence' | 'article' | 'comments' | 'compose' | 'how' | 'video' | 'record' | 'message' | 'liveEvidence' | null;

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, IconComponent, NewsCardComponent, AudioPlayerComponent, PublisherConsoleComponent, VeritaiMarkComponent],
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly document = inject(DOCUMENT);
  // O app roda sem zone.js: respostas assíncronas e timers precisam pedir nova renderização.
  private readonly changes = inject(ChangeDetectorRef);
  @ViewChild('globalSearch') globalSearch?: ElementRef<HTMLInputElement>;

  readonly articles = ARTICLES;
  readonly critiques = CRITIQUES;
  readonly communities = COMMUNITIES;
  readonly clips = VIDEO_CLIPS;
  readonly audio = AUDIO;
  readonly topics = ['Todos', 'Sociedade', 'Tecnologia', 'Ciência', 'Cultura', 'Planeta'];
  readonly filters = ['Todas', 'Em texto', 'Em vídeo'];
  publicArticles: FopPublicArticle[] = [];
  readonly resultados = Object.values(RESULTADO);
  readonly apoia = RELACAO['apoia'];
  // Data do dia no fuso de São Paulo, como "TERÇA-FEIRA, 6 DE OUTUBRO".
  readonly hoje = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Sao_Paulo' }).format(new Date()).toUpperCase();
  liveArticle: FopPublicArticle | null = null;
  readonly nav: { id: ViewName; icon: string; label: string }[] = [
    { id: 'news', icon: 'news', label: 'Notícias' },
    { id: 'reactions', icon: 'critique', label: 'Reactions' },
    { id: 'communities', icon: 'users', label: 'Comunidades' },
    { id: 'popular', icon: 'fire', label: 'Populares' },
    { id: 'saved', icon: 'bookmark', label: 'Salvos' },
    { id: 'profile', icon: 'user', label: 'Meu perfil' },
  ];

  view: ViewName = 'news';
  tab: 'for-you' | 'following' = 'for-you';
  topic = 'Todos';
  query = '';
  saved = new Set<number>();
  liked = new Set<number>();
  following = new Set<string>(['Horizonte']);
  critiqueLikes = new Set<string>();
  comments: Record<number, CommentItem[]> = {};
  ownCritiques: Critique[] = [];
  critiqueFilter = 'Todas';
  articleFilter: number | null = null;
  communityId = 'politics';
  joinedCommunities = new Set<string>(['politics']);
  communityPublishers: Record<string, Set<string>> = {
    politics: new Set(['República', 'Agência Público']),
    gossip: new Set(['Ponto Pop']),
    science: new Set(['Lume', 'Nexo Ciência']),
  };
  audioPlaying: number | null = null;
  panel: PanelKind = null;
  panelArticleId: number | null = null;
  panelTitle = '';
  panelMessage = '';
  toastMessage = '';
  commentDraft = '';
  critiqueDraft = '';
  private toastTimer?: ReturnType<typeof setTimeout>;

  ngOnInit(): void { void this.refreshPublished(); }

  async refreshPublished(): Promise<void> {
    try { this.publicArticles = await fopApi.published(); }
    catch { this.publicArticles = []; }
    this.changes.markForCheck();
  }

  openLiveEvidence(article: FopPublicArticle): void {
    this.liveArticle = article;
    this.open('liveEvidence');
  }

  get currentNavLabel(): string {
    if (this.view === 'publisher') return 'Área do publisher';
    return this.nav.find((item) => item.id === this.view)?.label ?? 'Notícias';
  }

  get greeting(): [string, string, string] {
    const copy: Record<ViewName, [string, string, string]> = {
      news: ['O mundo acontece.', 'A conversa começa aqui.', 'Notícias com base. Espaço para o seu ponto de vista.'],
      reactions: ['Uma notícia.', 'Muitos pontos de vista.', 'Reações em vídeo e texto para descobrir como outras pessoas estão lendo o mundo.'],
      communities: ['Encontre a sua', 'comunidade.', 'Converse sobre os temas que importam, seguindo os portais escolhidos por cada grupo.'],
      popular: ['O que move', 'a conversa de hoje.', 'Notícias e perspectivas que estão fazendo a comunidade pensar.'],
      saved: ['Boas leituras,', 'no seu tempo.', 'Seu espaço para voltar às notícias que merecem outro olhar.'],
      profile: ['Seu espaço.', 'Sua perspectiva.', 'As conversas que você acompanha e as ideias que compartilha.'],
      publisher: ['Sua notícia.', 'Com fontes à vista.', 'Envie afirmações e evidências para análise automática antes da publicação.'],
    };
    return copy[this.view];
  }

  get filteredArticles(): Article[] {
    const normalized = this.query.toLocaleLowerCase('pt-BR');
    return this.articles.filter((article) =>
      (this.topic === 'Todos' || article.topic === this.topic || (this.topic === 'Planeta' && article.id === 2)) &&
      (this.tab !== 'following' || this.following.has(article.publisher)) &&
      (!normalized || `${article.title} ${article.summary} ${article.publisher} ${article.topic}`.toLocaleLowerCase('pt-BR').includes(normalized)),
    );
  }

  get savedArticles(): Article[] {
    return this.articles.filter((article) => this.saved.has(article.id));
  }

  get selectedArticle(): Article | undefined {
    return this.articles.find((article) => article.id === this.panelArticleId);
  }

  get selectedCommunity(): Community {
    return this.communities.find((community) => community.id === this.communityId) ?? this.communities[0];
  }

  get selectedCommunityPublishers() {
    const selected = this.communityPublishers[this.selectedCommunity.id] ?? new Set<string>();
    return this.selectedCommunity.publishers.filter((publisher) => selected.has(publisher.name));
  }

  get filteredCritiques(): Critique[] {
    return [...this.ownCritiques, ...this.critiques].filter((critique) =>
      (!this.articleFilter || critique.article === this.articleFilter) &&
      (this.critiqueFilter === 'Todas' || (this.critiqueFilter === 'Em texto' && critique.type === 'text') || (this.critiqueFilter === 'Em vídeo' && critique.type === 'video')),
    );
  }

  get filteredClips() {
    return this.clips.filter((clip) => !this.articleFilter || this.critiqueById(clip.id)?.article === this.articleFilter);
  }

  navigate(view: ViewName): void {
    this.closePanel();
    this.view = view;
    this.query = '';
    this.topic = 'Todos';
    this.tab = 'for-you';
    this.articleFilter = null;
    this.critiqueFilter = 'Todas';
    if (view === 'news') void this.refreshPublished();
    this.document.defaultView?.scrollTo({ top: 0, behavior: 'instant' });
  }

  setTopic(topic: string): void {
    this.topic = topic;
    if (this.view !== 'news') this.view = 'news';
  }

  toggleSet<T>(set: Set<T>, value: T): boolean {
    if (set.has(value)) {
      set.delete(value);
      return false;
    }
    set.add(value);
    return true;
  }

  toggleLike(id: number): void { this.toggleSet(this.liked, id); }

  toggleSave(id: number): void {
    const added = this.toggleSet(this.saved, id);
    this.toast(added ? 'Notícia salva para ler depois.' : 'Notícia removida dos salvos.');
  }

  toggleFollow(publisher: string): void {
    const added = this.toggleSet(this.following, publisher);
    this.toast(added ? `Agora você segue ${publisher}.` : `Você deixou de seguir ${publisher}.`);
  }

  toggleCritiqueLike(id: number | string): void { this.toggleSet(this.critiqueLikes, String(id)); }

  toggleAudio(id: number): void {
    this.audioPlaying = this.audioPlaying === id ? null : id;
    this.toast(this.audioPlaying ? 'Reprodução visual iniciada. O áudio é demonstrativo.' : 'Reprodução visual pausada.');
  }

  showAudioInfo(id: number): void {
    const item = this.audio[id];
    this.openMessage('Sobre este áudio', `${item.title} é um módulo demonstrativo publicado por ${item.host}. Não há arquivo de áudio nesta versão.`);
  }

  showExpertAudio(value: string): void {
    const [idText, indexText] = value.split('|');
    const expert = this.audio[Number(idText)]?.experts[Number(indexText)];
    if (expert) this.openMessage('Comentário de especialista', `${expert.name}, ${expert.role}. A reprodução é apenas uma simulação visual neste protótipo.`);
  }

  shareArticle(id: number): void {
    const article = this.articleById(id);
    this.toast(article ? `Link demonstrativo de “${article.title.slice(0, 34)}…” copiado.` : 'Link demonstrativo copiado.');
  }

  showReactions(id: number): void {
    this.view = 'reactions';
    this.articleFilter = id;
    this.critiqueFilter = 'Todas';
    this.document.defaultView?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  open(kind: Exclude<PanelKind, null>, articleId?: number): void {
    this.panel = kind;
    this.panelArticleId = articleId ?? null;
    this.document.body.style.overflow = 'hidden';
  }

  openMessage(title: string, message: string): void {
    this.panelTitle = title;
    this.panelMessage = message;
    this.open('message');
  }

  closePanel(): void {
    this.panel = null;
    this.panelArticleId = null;
    this.commentDraft = '';
    this.critiqueDraft = '';
    this.document.body.style.overflow = '';
  }

  addComment(): void {
    if (!this.panelArticleId || !this.commentDraft.trim()) return;
    const list = this.comments[this.panelArticleId] ?? [];
    this.comments[this.panelArticleId] = [...list, { name: 'Charles', initials: 'CH', color: '#e1e1e1', text: this.commentDraft.trim(), likes: 0 }];
    this.commentDraft = '';
    this.toast('Comentário adicionado à demonstração.');
  }

  publishCritique(): void {
    if (!this.panelArticleId || !this.critiqueDraft.trim()) return;
    const text = this.critiqueDraft.trim();
    this.ownCritiques.unshift({ id: `own-${Date.now()}`, article: this.panelArticleId, name: 'Charles', initials: 'CH', role: 'Seu ponto de vista', color: '#e1e1e1', type: 'text', text: text.length > 95 ? `${text.slice(0, 95)}…` : text, body: text.length > 95 ? text : '', likes: 0, comments: 0, time: 'Agora' });
    this.closePanel();
    this.view = 'reactions';
    this.toast('Sua reaction foi adicionada à demonstração.');
  }

  toggleCommunityPublisher(name: string): void {
    this.toggleSet(this.communityPublishers[this.selectedCommunity.id], name);
  }

  communityPostArticle(id: number): Article { return this.articleById(id) ?? this.articles[0]; }

  communityPostPublisher(index: number) {
    const selected = this.selectedCommunityPublishers;
    return selected[index % Math.max(1, selected.length)] ?? this.selectedCommunity.publishers[index % this.selectedCommunity.publishers.length];
  }

  articleById(id: number): Article | undefined { return this.articles.find((article) => article.id === id); }

  critiqueById(id: number | string): Critique | undefined {
    return [...this.ownCritiques, ...this.critiques].find((critique) => String(critique.id) === String(id));
  }

  commentsFor(id: number): CommentItem[] {
    const defaults: CommentItem[] = [
      { name: 'Marina Costa', initials: 'MC', color: '#d1d1d1', text: id === 1 ? 'Gostei de ver a consulta pública entre as evidências. Quero entender como os bairros vão participar dessa decisão.' : 'O ponto principal para mim é saber como as pessoas vão participar. A proposta abre uma boa conversa.', likes: 18 },
      { name: 'João Pedro', initials: 'JP', color: '#d4d4d4', text: 'A notícia traz a proposta, mas acompanhar a execução vai ser tão importante quanto o anúncio.', likes: 12 },
    ];
    return [...defaults, ...(this.comments[id] ?? [])];
  }

  readingParagraph(id: number): string {
    if (id === 1) return 'A proposta coloca a qualidade de vida no centro do planejamento urbano. O projeto demonstrativo combina a criação de três parques de bairro com 12 quilômetros de ciclovias, conectando espaços de lazer a trajetos do dia a dia.';
    if (id === 2) return 'O projeto demonstrativo apresenta um modelo de participação coletiva. Em vez de cada residência instalar um sistema próprio, os participantes compartilham a produção de uma estrutura comunitária.';
    return 'A programação demonstrativa aproxima moradores de diferentes idades da tecnologia, com encontros sobre segurança online, pesquisa de informação e inteligência artificial.';
  }

  toast(message: string): void {
    this.toastMessage = message;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => { this.toastMessage = ''; this.changes.markForCheck(); }, 3300);
  }

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.panel) this.closePanel();
    if (event.key === '/' && !this.panel && !['INPUT', 'TEXTAREA'].includes((this.document.activeElement as HTMLElement)?.tagName)) {
      event.preventDefault();
      this.globalSearch?.nativeElement.focus();
    }
  }
}
