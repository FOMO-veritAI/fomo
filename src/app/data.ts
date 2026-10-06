import { Article, ArticleAudio, Community, Critique } from './models';

export const ARTICLES: Article[] = [
  {
    id: 1,
    publisher: 'Horizonte',
    mark: 'h',
    topic: 'Sociedade',
    time: 'Há 32 min',
    image: 'urban-park.jpg',
    category: 'CIDADES & FUTURO',
    title: 'Mais árvores, novos caminhos: projeto vai transformar espaços públicos em áreas verdes',
    summary: 'Plano de requalificação prevê parques de bairro, ciclovias e espaços de convivência. A discussão agora é sobre como incluir toda a cidade.',
    likes: 248,
    comments: 42,
    shares: 18,
    voices: 12,
    claims: ['O projeto prevê a criação de três parques de bairro.', 'O plano inclui 12 quilômetros de novas ciclovias.', 'A proposta está aberta à consulta pública.'],
    sources: [
      { title: 'Plano de requalificação urbana', kind: 'Documento técnico', excerpt: 'O plano descreve três parques de bairro e a conexão entre eles por uma rede cicloviária de 12 quilômetros.' },
      { title: 'Portal da consulta pública', kind: 'Registro primário', excerpt: 'O período de participação pública está previsto no cronograma de implantação do projeto.' },
    ],
  },
  {
    id: 2,
    publisher: 'Lume',
    mark: 'l',
    logo: 'lume',
    topic: 'Ciência',
    time: 'Há 1 hora',
    image: 'solar-energy.jpg',
    category: 'CIÊNCIA & ENERGIA',
    title: 'Energia solar compartilhada chega a novos bairros em projeto comunitário',
    summary: 'Iniciativa reúne moradores para dividir a produção de energia limpa. A adesão começa por cinco comunidades do projeto-piloto.',
    likes: 186,
    comments: 28,
    shares: 12,
    voices: 8,
    claims: ['A iniciativa prevê a participação de cinco comunidades.', 'A produção de energia será compartilhada entre os participantes.', 'A adesão começa na fase de projeto-piloto.'],
    sources: [
      { title: 'Plano do projeto comunitário', kind: 'Documento técnico', excerpt: 'A etapa inicial contempla cinco comunidades e define os critérios de participação na produção compartilhada.' },
      { title: 'Comunicado da cooperativa', kind: 'Fonte primária', excerpt: 'O comunicado apresenta o cronograma de adesão e o modelo de divisão da energia entre os participantes.' },
    ],
  },
  {
    id: 3,
    publisher: 'Ponto',
    mark: 'p.',
    logo: 'ponto',
    topic: 'Tecnologia',
    time: 'Há 2 horas',
    category: 'TECNOLOGIA & SOCIEDADE',
    title: 'Bibliotecas públicas abrem oficinas gratuitas de educação digital',
    summary: 'Da segurança online ao uso responsável da inteligência artificial, a programação quer aproximar diferentes gerações da tecnologia.',
    likes: 94,
    comments: 16,
    shares: 9,
    voices: 6,
    claims: ['As oficinas são gratuitas e abertas ao público.', 'A programação inclui segurança online e inteligência artificial.'],
    sources: [
      { title: 'Programação das bibliotecas', kind: 'Fonte primária', excerpt: 'O calendário apresenta as atividades e informa que a inscrição é gratuita.' },
      { title: 'Guia das oficinas', kind: 'Documento técnico', excerpt: 'Os conteúdos incluem segurança na internet e uma introdução ao uso responsável de inteligência artificial.' },
    ],
  },
];

export const CRITIQUES: Critique[] = [
  { id: 1, article: 1, name: 'Marina Costa', initials: 'MC', role: 'Arquiteta e urbanista', color: '#e5cdb5', type: 'text', text: 'Uma cidade mais verde precisa ser uma cidade para todos.', body: 'O projeto é um avanço. Mas quem mora longe do centro também vai ter acesso? Quero ver a distribuição desses parques nos bairros, além das imagens bonitas.', likes: 86, comments: 14, time: 'Há 18 min' },
  { id: 2, article: 2, name: 'Rafael Lima', initials: 'RL', role: 'Educador ambiental', color: '#cbd5b9', type: 'video', text: 'Energia limpa. Mas acessível para quem?', body: 'A conversa sobre energia compartilhada precisa incluir quem mais sente o peso da conta de luz.', likes: 123, comments: 21, time: 'Há 40 min' },
  { id: 3, article: 3, name: 'Luiza Mendes', initials: 'LM', role: 'Professora e pesquisadora', color: '#e3d4da', type: 'text', text: 'Educação digital é muito mais do que aprender a usar uma ferramenta.', body: 'Entender de onde vem a informação e aprender a fazer boas perguntas são habilidades tão importantes quanto saber usar a tecnologia.', likes: 57, comments: 9, time: 'Há 1 hora' },
];

export const AUDIO: Record<number, ArticleAudio> = {
  1: { duration: '06:42', title: 'O contexto por trás do projeto', host: 'Redação Horizonte', intro: 'Por que a cidade está redesenhando seus espaços públicos?', experts: [{ initials: 'AC', color: '#d6dfc6', name: 'Ana Carvalho', role: 'Especialista em cidades', duration: '02:18' }, { initials: 'MP', color: '#e4d1be', name: 'Marcelo Paes', role: 'Repórter de urbanismo', duration: '03:06' }] },
  2: { duration: '08:15', title: 'Energia para compartilhar', host: 'Lume Ciência', intro: 'Como funciona o modelo comunitário de energia solar?', experts: [{ initials: 'BS', color: '#d0d9d0', name: 'Bianca Sato', role: 'Pesquisadora de energia', duration: '03:12' }, { initials: 'FN', color: '#eadcc7', name: 'Felipe Nunes', role: 'Jornalista de ciência', duration: '02:41' }] },
  3: { duration: '05:24', title: 'Aprender a navegar no digital', host: 'Ponto de encontro', intro: 'O que muda quando a biblioteca vira espaço de educação digital?', experts: [{ initials: 'IR', color: '#d8d2e1', name: 'Iara Reis', role: 'Pesquisadora de educação', duration: '02:09' }, { initials: 'GV', color: '#d4e0d0', name: 'Gustavo Vale', role: 'Editor de tecnologia', duration: '01:54' }] },
};

export const COMMUNITIES: Community[] = [
  { id: 'politics', initials: 'PB', name: 'Política no Brasil', topic: 'POLÍTICA', color: '#173f36', accent: '#d9e9b3', members: '18,4 mil', online: '312', description: 'Instituições, decisões públicas e o impacto delas na vida real.', publishers: [{ name: 'República', mark: 'R', description: 'Política explicada' }, { name: 'Agência Público', mark: 'A', description: 'Serviço e cidadania' }, { name: 'Carta Aberta', mark: 'C', description: 'Análise e contexto' }], postIds: [1, 3] },
  { id: 'gossip', initials: 'FG', name: 'Fofoca de famosos', topic: 'CULTURA', color: '#632f4b', accent: '#f4d7e1', members: '9,8 mil', online: '184', description: 'Notícias de entretenimento, bastidores e cultura pop com contexto.', publishers: [{ name: 'Ponto Pop', mark: 'P', description: 'Cultura e entretenimento' }, { name: 'Radar 360', mark: 'R', description: 'Bastidores em foco' }, { name: 'Cena Aberta', mark: 'C', description: 'Cinema, música e TV' }], postIds: [2, 3] },
  { id: 'science', initials: 'CT', name: 'Ciência no cotidiano', topic: 'CIÊNCIA', color: '#214755', accent: '#cae8e0', members: '6,2 mil', online: '97', description: 'Evidências, descobertas e perguntas para entender o mundo.', publishers: [{ name: 'Lume', mark: 'l', description: 'Ciência para entender' }, { name: 'Nexo Ciência', mark: 'N', description: 'Pesquisa e contexto' }, { name: 'Futuro Agora', mark: 'F', description: 'Tecnologia responsável' }], postIds: [2, 1] },
];

export const VIDEO_CLIPS = [
  { id: 1, image: 'urban-park.jpg', duration: '0:38', caption: 'Uma cidade mais verde precisa ser uma cidade para todos.' },
  { id: 2, image: 'solar-energy.jpg', duration: '0:42', caption: 'Energia limpa. Mas acessível para quem?' },
  { id: 3, image: 'urban-park.jpg', duration: '0:31', caption: 'Educação digital é muito mais do que aprender uma ferramenta.' },
];
