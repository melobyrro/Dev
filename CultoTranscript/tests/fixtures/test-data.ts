/**
 * Test fixtures and mock data for Playwright tests
 */

import {
  VideoDTO,
  VideoDetailDTO,
  SummaryDTO,
  ChannelDTO,
  VideoStatus,
  BiblicalPassageDTO,
  CitationDTO,
} from '../types';

/**
 * Mock biblical passages
 */
export const mockBiblicalPassages: BiblicalPassageDTO[] = [
  {
    book: 'João',
    chapter: 3,
    verse_start: 16,
    text: 'Porque Deus amou o mundo de tal maneira...',
  },
  {
    book: 'Salmos',
    chapter: 23,
    verse_start: 1,
    verse_end: 6,
  },
  {
    book: 'Romanos',
    chapter: 8,
    verse_start: 28,
  },
];

/**
 * Mock citations
 */
export const mockCitations: CitationDTO[] = [
  {
    text: 'A fé move montanhas',
    context: 'O pastor falou sobre a importância da fé na vida cristã',
    timestamp: 1200,
  },
  {
    text: 'Deus é amor',
    context: 'Reflexão sobre o caráter de Deus',
    timestamp: 2400,
  },
];

/**
 * Mock summary data
 */
export const mockSummary: SummaryDTO = {
  themes: ['Fé', 'Amor de Deus', 'Salvação', 'Esperança'],
  passages: mockBiblicalPassages,
  citations: mockCitations,
  speaker: 'Pastor João Silva',
  word_count: 3500,
  key_points: [
    'A fé é essencial para a vida cristã',
    'Deus nos ama incondicionalmente',
    'A salvação é um dom gratuito',
    'Devemos compartilhar a esperança que temos',
  ],
  suggestions: [
    'Incluir mais exemplos práticos',
    'Explorar mais as passagens de Romanos',
  ],
};

/**
 * Mock video data - processed video
 */
export const mockProcessedVideo: VideoDTO = {
  id: 'video-001',
  title: 'A Fé que Move Montanhas - Culto Domingo',
  youtube_id: 'abc123xyz',
  status: VideoStatus.PROCESSED,
  duration: 3600, // 1 hour
  created_at: '2025-01-15T10:00:00Z',
  processed_at: '2025-01-15T11:30:00Z',
  thumbnail_url: 'https://i.ytimg.com/vi/abc123xyz/default.jpg',
  channel_id: 'channel-001',
};

/**
 * Mock video data - processing video
 */
export const mockProcessingVideo: VideoDTO = {
  id: 'video-002',
  title: 'O Amor de Deus - Culto Quarta-feira',
  youtube_id: 'def456uvw',
  status: VideoStatus.PROCESSING,
  duration: 2700, // 45 minutes
  created_at: '2025-01-16T19:00:00Z',
  thumbnail_url: 'https://i.ytimg.com/vi/def456uvw/default.jpg',
  channel_id: 'channel-001',
};

/**
 * Mock video data - failed video
 */
export const mockFailedVideo: VideoDTO = {
  id: 'video-003',
  title: 'Testemunho - História Inspiradora',
  youtube_id: 'ghi789rst',
  status: VideoStatus.FAILED,
  duration: 1800, // 30 minutes
  created_at: '2025-01-17T14:00:00Z',
  thumbnail_url: 'https://i.ytimg.com/vi/ghi789rst/default.jpg',
  channel_id: 'channel-001',
};

/**
 * Mock video detail (with full transcript and summary)
 */
export const mockVideoDetail: VideoDetailDTO = {
  ...mockProcessedVideo,
  summary: mockSummary,
  transcript:
    'Boa noite a todos! Hoje vamos falar sobre a fé que move montanhas. ' +
    'Em João 3:16, lemos que Deus amou o mundo de tal maneira... ' +
    '[Transcript continues for 3500 words...]',
};

/**
 * Mock channel data
 */
export const mockChannel: ChannelDTO = {
  id: 'channel-001',
  title: 'Igreja Comunidade Cristã',
  youtube_channel_id: 'UC_ABC123XYZ',
  last_checked_at: '2025-01-17T08:00:00Z',
  created_at: '2024-06-01T00:00:00Z',
  total_videos: 150,
  processed_videos: 145,
};

/**
 * Mock video list (for testing pagination and lists)
 */
export const mockVideoList: VideoDTO[] = [
  mockProcessedVideo,
  mockProcessingVideo,
  mockFailedVideo,
  {
    id: 'video-004',
    title: 'Louvor e Adoração - Culto Especial',
    youtube_id: 'jkl012mno',
    status: VideoStatus.PROCESSED,
    duration: 4500, // 1h 15min
    created_at: '2025-01-14T10:00:00Z',
    processed_at: '2025-01-14T12:00:00Z',
    thumbnail_url: 'https://i.ytimg.com/vi/jkl012mno/default.jpg',
    channel_id: 'channel-001',
  },
  {
    id: 'video-005',
    title: 'Escola Bíblica Dominical - Livro de Atos',
    youtube_id: 'pqr345stu',
    status: VideoStatus.PROCESSED,
    duration: 2100, // 35 minutes
    created_at: '2025-01-14T09:00:00Z',
    processed_at: '2025-01-14T09:45:00Z',
    thumbnail_url: 'https://i.ytimg.com/vi/pqr345stu/default.jpg',
    channel_id: 'channel-001',
  },
];

/**
 * Test YouTube URLs for various scenarios
 */
export const testYouTubeUrls = {
  valid: {
    standard: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    short: 'https://youtu.be/dQw4w9WgXcQ',
    withTimestamp: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s',
    embedded: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
  },
  invalid: {
    notYouTube: 'https://vimeo.com/123456789',
    malformed: 'https://youtube.com/invalid',
    empty: '',
  },
  channel: {
    standard: 'https://www.youtube.com/channel/UC_ABC123XYZ',
    handle: 'https://www.youtube.com/@ChurchChannel',
    legacy: 'https://www.youtube.com/user/ChurchUser',
  },
};

/**
 * Mock transcript text (Portuguese sermon)
 */
export const mockTranscriptText = `
Bom dia, igreja! É uma alegria estar aqui com vocês hoje.
Vamos abrir nossas Bíblias em João capítulo 3, versículo 16.

"Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito,
para que todo aquele que nele crê não pereça, mas tenha a vida eterna."

Este versículo é o coração do evangelho. Hoje vamos explorar três aspectos
deste amor maravilhoso:

Primeiro, o ALCANCE do amor de Deus. "O mundo" - não apenas alguns,
mas toda a humanidade.

Segundo, a PROFUNDIDADE do amor de Deus. "De tal maneira" - um amor
que ultrapassa nossa compreensão.

Terceiro, a EXPRESSÃO do amor de Deus. "Deu o seu Filho" - o maior
sacrifício imaginável.

Como diz em Romanos 8:28, sabemos que todas as coisas cooperam para o bem
daqueles que amam a Deus.

Vamos orar juntos...
`.trim();
