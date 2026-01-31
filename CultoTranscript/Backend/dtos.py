"""
FROZEN DATA TRANSFER OBJECTS (DTOs)

These DTOs are the single source of truth for data structures
shared between UI Worker and Backend Worker.

Python implementation mirroring TypeScript DTOs in shared/dtos.ts
DO NOT MODIFY after Phase 0 without Orchestrator approval.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Union, Literal
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class VideoStatus(str, Enum):
    """Video processing status enum - Single source of truth"""
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    QUEUED = "QUEUED"


class EventType(str, Enum):
    """SSE Event types"""
    VIDEO_STATUS = "video.status"
    SUMMARY_READY = "summary.ready"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


# ============================================================================
# VIDEO DTOs
# ============================================================================

class BiblicalPassageDTO(BaseModel):
    """Biblical passage reference"""
    book: str  # e.g., "João", "Gênesis"
    chapter: int
    verse_start: int
    verse_end: Optional[int] = None
    text: Optional[str] = None


class CitationDTO(BaseModel):
    """Citation or quote from sermon"""
    text: str  # The quoted text
    context: Optional[str] = None  # Surrounding context
    timestamp: Optional[int] = None  # Position in video (seconds)


class SummaryDTO(BaseModel):
    """Video summary and analytics"""
    themes: List[str]  # Main themes identified
    passages: List[BiblicalPassageDTO]  # Biblical references
    citations: List[CitationDTO]  # Citations and quotes
    speaker: Optional[str] = None  # Speaker name
    word_count: int  # Total words in transcript
    key_points: List[str]  # Summary bullet points
    suggestions: Optional[List[str]] = None  # Improvement suggestions


class VideoDTO(BaseModel):
    """Core video information"""
    id: str
    title: str
    youtube_id: str
    status: VideoStatus
    duration: int  # in seconds
    published_at: Optional[str] = None  # ISO 8601 datetime - YouTube upload date
    created_at: str  # ISO 8601 datetime
    processed_at: Optional[str] = None  # ISO 8601 datetime
    thumbnail_url: Optional[str] = None
    channel_id: str


class VideoDetailDTO(VideoDTO):
    """Complete video details (combines Video + Summary)"""
    summary: SummaryDTO
    transcript: Optional[str] = None  # Full transcript text
    error_message: Optional[str] = None  # If status is FAILED


# ============================================================================
# CHANNEL DTOs
# ============================================================================

class ChannelDTO(BaseModel):
    """Channel information"""
    id: str
    title: str
    youtube_channel_id: str
    last_checked_at: Optional[str] = None  # ISO 8601 datetime
    created_at: str
    total_videos: int
    processed_videos: int


# ============================================================================
# SSE EVENT DTOs
# ============================================================================

class EventDTO(BaseModel):
    """Base SSE event structure"""
    type: EventType
    timestamp: str  # ISO 8601 datetime


class VideoStatusEventDTO(EventDTO):
    """Video status change event"""
    type: Literal[EventType.VIDEO_STATUS] = EventType.VIDEO_STATUS
    video_id: str
    status: VideoStatus
    progress: Optional[int] = None  # 0-100 percentage
    message: Optional[str] = None  # Status message


class SummaryReadyEventDTO(EventDTO):
    """Summary ready event"""
    type: Literal[EventType.SUMMARY_READY] = EventType.SUMMARY_READY
    video_id: str
    summary: SummaryDTO


class ErrorEventDTO(EventDTO):
    """Error event"""
    type: Literal[EventType.ERROR] = EventType.ERROR
    video_id: Optional[str] = None
    error_code: str
    error_message: str


class HeartbeatEventDTO(EventDTO):
    """Heartbeat event (connection keep-alive)"""
    type: Literal[EventType.HEARTBEAT] = EventType.HEARTBEAT


# Union type of all possible SSE events
SSEEventDTO = Union[VideoStatusEventDTO, SummaryReadyEventDTO, ErrorEventDTO, HeartbeatEventDTO]


# ============================================================================
# API RESPONSE DTOs
# ============================================================================

class ApiSuccessResponse(BaseModel):
    """Standard API success response"""
    success: Literal[True] = True
    data: Optional[dict] = None
    message: Optional[str] = None


class ApiErrorResponse(BaseModel):
    """Standard API error response"""
    success: Literal[False] = False
    detail: str
    error_code: Optional[str] = None


# ============================================================================
# CHATBOT DTOs
# ============================================================================

class ChatMessageDTO(BaseModel):
    """Chat message"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: str  # ISO 8601 datetime


class ChatRequestDTO(BaseModel):
    """Chat request"""
    message: str
    session_id: str
    channel_id: str
    knowledge_mode: Optional[str] = "database_only"


class ChatResponseDTO(BaseModel):
    """Chat response"""
    response: str
    cited_videos: List[VideoDTO]
    relevance_scores: List[float]
    session_id: str


# ============================================================================
# PAGINATION DTOs
# ============================================================================

class PaginationDTO(BaseModel):
    """Pagination metadata"""
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponseDTO(BaseModel):
    """Paginated response"""
    items: List[dict]
    pagination: PaginationDTO


# ============================================================================
# VIDEO GROUPING DTOs
# ============================================================================

class MonthlyGroupDTO(BaseModel):
    """Monthly video grouping"""
    year: int
    month: int  # 1-12
    month_label: str  # e.g., "Janeiro 2025"
    videos: List[VideoDTO]
    total_duration: int  # Sum of all video durations in seconds


# ============================================================================
# STATISTICS DTOs
# ============================================================================

class ChannelStatsDTO(BaseModel):
    """Channel statistics"""
    total_videos: int
    processed_videos: int
    processing_videos: int
    failed_videos: int
    total_duration: int  # Total seconds of all videos
    average_duration: int  # Average video duration
    last_updated: str  # ISO 8601 datetime


# ============================================================================
# DETAILED REPORT DTOs (for video detail drawer)
# ============================================================================

class ThemeDTO(BaseModel):
    """Theme with confidence score"""
    theme: str
    score: float  # 0-1 confidence score


class HighlightDTO(BaseModel):
    """Highlight from sermon"""
    title: str
    summary: str
    timestamp: Optional[int] = None  # Position in seconds


class DiscussionQuestionDTO(BaseModel):
    """Discussion question for small groups"""
    question: str
    passage: Optional[str] = None  # Related biblical passage


class SermonStatisticsDTO(BaseModel):
    """Sermon statistics"""
    word_count: int
    duration_minutes: int
    wpm: int  # Words per minute


class VideoDetailedReportDTO(BaseModel):
    """Comprehensive video detailed report (used for detail drawer)"""
    video_id: str
    title: str
    youtube_id: str
    published_at: Optional[str] = None
    duration: int
    status: VideoStatus
    speaker: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ai_summary: Optional[str] = None
    statistics: SermonStatisticsDTO
    themes: List[ThemeDTO]
    passages: List[BiblicalPassageDTO]
    highlights: List[HighlightDTO]
    discussion_questions: List[DiscussionQuestionDTO]
    transcript: Optional[str] = None  # Lazy loaded separately
    error_message: Optional[str] = None
