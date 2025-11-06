/**
 * Test type definitions - imports shared DTOs for type safety in tests
 */

// Import all DTOs from shared directory
export * from '../../shared/dtos';

// Re-export commonly used types for convenience
export type {
  VideoDTO,
  VideoDetailDTO,
  SummaryDTO,
  ChannelDTO,
  EventDTO,
  VideoStatusEventDTO,
  SummaryReadyEventDTO,
  ErrorEventDTO,
  HeartbeatEventDTO,
  SSEEventDTO,
  ApiSuccessResponse,
  ApiErrorResponse,
  ApiResponse,
  ChatMessageDTO,
  ChatRequestDTO,
  ChatResponseDTO,
  PaginationDTO,
  PaginatedResponseDTO,
  MonthlyGroupDTO,
  ChannelStatsDTO,
} from '../../shared/dtos';

export {
  VideoStatus,
  EventType,
  isVideoStatusEvent,
  isSummaryReadyEvent,
  isErrorEvent,
  isHeartbeatEvent,
  isApiSuccess,
  isApiError,
} from '../../shared/dtos';
