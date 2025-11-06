/**
 * FROZEN DATA TRANSFER OBJECTS (DTOs)
 *
 * These DTOs are the single source of truth for data structures
 * shared between UI Worker and Backend Worker.
 *
 * DO NOT MODIFY after Phase 0 without Orchestrator approval.
 */

// ============================================================================
// ENUMS
// ============================================================================

/**
 * Video processing status enum - Single source of truth
 */
export enum VideoStatus {
  PROCESSING = "PROCESSING",
  PROCESSED = "PROCESSED",
  FAILED = "FAILED",
  PENDING = "PENDING",
  QUEUED = "QUEUED"
}

/**
 * SSE Event types
 */
export enum EventType {
  VIDEO_STATUS = "video.status",
  SUMMARY_READY = "summary.ready",
  ERROR = "error",
  HEARTBEAT = "heartbeat"
}

// ============================================================================
// VIDEO DTOs
// ============================================================================

/**
 * Core video information
 */
export interface VideoDTO {
  id: string;
  title: string;
  youtube_id: string;
  status: VideoStatus;
  duration: number; // in seconds
  published_at?: string; // ISO 8601 datetime - YouTube upload date
  created_at: string; // ISO 8601 datetime
  processed_at?: string; // ISO 8601 datetime
  thumbnail_url?: string;
  channel_id: string;
}

/**
 * Video summary and analytics
 */
export interface SummaryDTO {
  themes: string[]; // Main themes identified
  passages: BiblicalPassageDTO[]; // Biblical references
  citations: CitationDTO[]; // Citations and quotes
  speaker?: string; // Speaker name
  word_count: number; // Total words in transcript
  key_points: string[]; // Summary bullet points
  suggestions?: string[]; // Improvement suggestions
}

/**
 * Biblical passage reference
 */
export interface BiblicalPassageDTO {
  book: string; // e.g., "João", "Gênesis"
  chapter: number;
  verse_start: number;
  verse_end?: number;
  text?: string; // Optional verse text
}

/**
 * Citation or quote from sermon
 */
export interface CitationDTO {
  text: string; // The quoted text
  context?: string; // Surrounding context
  timestamp?: number; // Position in video (seconds)
}

/**
 * Complete video details (combines Video + Summary)
 */
export interface VideoDetailDTO extends VideoDTO {
  summary: SummaryDTO;
  transcript?: string; // Full transcript text
  error_message?: string; // If status is FAILED
}

/**
 * Theme with confidence score
 */
export interface ThemeDTO {
  theme: string;
  score: number; // 0-1 confidence score
}

/**
 * Highlight from sermon
 */
export interface HighlightDTO {
  title: string;
  summary: string;
  timestamp?: number; // Position in seconds
}

/**
 * Discussion question for small groups
 */
export interface DiscussionQuestionDTO {
  question: string;
  passage?: string; // Related biblical passage
}

/**
 * Sermon statistics
 */
export interface SermonStatisticsDTO {
  word_count: number;
  duration_minutes: number;
  wpm: number; // Words per minute
}

/**
 * Comprehensive video detailed report (used for detail drawer)
 */
export interface VideoDetailedReportDTO {
  video_id: string;
  title: string;
  youtube_id: string;
  published_at?: string;
  duration: number;
  status: VideoStatus;
  speaker?: string;
  thumbnail_url?: string;
  ai_summary?: string;
  statistics: SermonStatisticsDTO;
  themes: ThemeDTO[];
  passages: BiblicalPassageDTO[];
  highlights: HighlightDTO[];
  discussion_questions: DiscussionQuestionDTO[];
  transcript?: string; // Lazy loaded separately
  error_message?: string;
}

// ============================================================================
// CHANNEL DTOs
// ============================================================================

export interface ChannelDTO {
  id: string;
  title: string;
  youtube_channel_id: string;
  last_checked_at?: string; // ISO 8601 datetime
  created_at: string;
  total_videos: number;
  processed_videos: number;
}

// ============================================================================
// SSE EVENT DTOs
// ============================================================================

/**
 * Base SSE event structure
 */
export interface EventDTO {
  type: EventType;
  timestamp: string; // ISO 8601 datetime
}

/**
 * Video status change event
 */
export interface VideoStatusEventDTO extends EventDTO {
  type: EventType.VIDEO_STATUS;
  video_id: string;
  status: VideoStatus;
  progress?: number; // 0-100 percentage
  message?: string; // Status message
}

/**
 * Summary ready event
 */
export interface SummaryReadyEventDTO extends EventDTO {
  type: EventType.SUMMARY_READY;
  video_id: string;
  summary: SummaryDTO;
}

/**
 * Error event
 */
export interface ErrorEventDTO extends EventDTO {
  type: EventType.ERROR;
  video_id?: string;
  error_code: string;
  error_message: string;
}

/**
 * Heartbeat event (connection keep-alive)
 */
export interface HeartbeatEventDTO extends EventDTO {
  type: EventType.HEARTBEAT;
}

/**
 * Union type of all possible SSE events
 */
export type SSEEventDTO =
  | VideoStatusEventDTO
  | SummaryReadyEventDTO
  | ErrorEventDTO
  | HeartbeatEventDTO;

// ============================================================================
// API RESPONSE DTOs
// ============================================================================

/**
 * Standard API success response
 */
export interface ApiSuccessResponse<T = any> {
  success: true;
  data: T;
  message?: string;
}

/**
 * Standard API error response
 */
export interface ApiErrorResponse {
  success: false;
  detail: string;
  error_code?: string;
}

/**
 * Union type for all API responses
 */
export type ApiResponse<T = any> = ApiSuccessResponse<T> | ApiErrorResponse;

// ============================================================================
// CHATBOT DTOs
// ============================================================================

export interface ChatMessageDTO {
  role: "user" | "assistant";
  content: string;
  timestamp: string; // ISO 8601 datetime
}

export interface ChatRequestDTO {
  message: string;
  session_id: string;
  channel_id: string;
}

export interface ChatResponseDTO {
  response: string;
  cited_videos: VideoDTO[];
  relevance_scores: number[];
  session_id: string;
}

// ============================================================================
// PAGINATION DTOs
// ============================================================================

export interface PaginationDTO {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponseDTO<T> {
  items: T[];
  pagination: PaginationDTO;
}

// ============================================================================
// VIDEO GROUPING DTOs
// ============================================================================

export interface MonthlyGroupDTO {
  year: number;
  month: number; // 1-12
  month_label: string; // e.g., "Janeiro 2025"
  videos: VideoDTO[];
  total_duration: number; // Sum of all video durations in seconds
}

// ============================================================================
// STATISTICS DTOs
// ============================================================================

export interface ChannelStatsDTO {
  total_videos: number;
  processed_videos: number;
  processing_videos: number;
  failed_videos: number;
  total_duration: number; // Total seconds of all videos
  average_duration: number; // Average video duration
  last_updated: string; // ISO 8601 datetime
}

// ============================================================================
// TYPE GUARDS (for runtime type checking)
// ============================================================================

export function isVideoStatusEvent(event: SSEEventDTO): event is VideoStatusEventDTO {
  return event.type === EventType.VIDEO_STATUS;
}

export function isSummaryReadyEvent(event: SSEEventDTO): event is SummaryReadyEventDTO {
  return event.type === EventType.SUMMARY_READY;
}

export function isErrorEvent(event: SSEEventDTO): event is ErrorEventDTO {
  return event.type === EventType.ERROR;
}

export function isHeartbeatEvent(event: SSEEventDTO): event is HeartbeatEventDTO {
  return event.type === EventType.HEARTBEAT;
}

export function isApiSuccess<T>(response: ApiResponse<T>): response is ApiSuccessResponse<T> {
  return response.success === true;
}

export function isApiError(response: ApiResponse): response is ApiErrorResponse {
  return response.success === false;
}
