export type ViewName = 'news' | 'reactions' | 'communities' | 'popular' | 'saved' | 'profile' | 'publisher';

export interface SourceEvidence {
  title: string;
  kind: string;
  excerpt: string;
}

export interface Article {
  id: number;
  publisher: string;
  mark: string;
  logo?: string;
  topic: string;
  time: string;
  image?: string;
  category: string;
  title: string;
  summary: string;
  likes: number;
  comments: number;
  shares: number;
  voices: number;
  claims: string[];
  sources: SourceEvidence[];
}

export interface Critique {
  id: number | string;
  article: number;
  name: string;
  initials: string;
  role: string;
  color: string;
  type: 'text' | 'video';
  text: string;
  body: string;
  likes: number;
  comments: number;
  time: string;
}

export interface Expert {
  initials: string;
  color: string;
  name: string;
  role: string;
  duration: string;
}

export interface ArticleAudio {
  duration: string;
  title: string;
  host: string;
  intro: string;
  experts: Expert[];
}

export interface Publisher {
  name: string;
  mark: string;
  description: string;
}

export interface Community {
  id: string;
  initials: string;
  name: string;
  topic: string;
  color: string;
  accent: string;
  members: string;
  online: string;
  description: string;
  publishers: Publisher[];
  postIds: number[];
}

export interface CommentItem {
  name: string;
  initials: string;
  color: string;
  text: string;
  likes: number;
}
