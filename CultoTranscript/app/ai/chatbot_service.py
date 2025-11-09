"""
Channel Chatbot Service
Conversational AI for Q&A about channel sermons
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from app.ai.cache_manager import CacheManager
from app.ai.embedding_service import EmbeddingService
from app.ai.llm_client import get_llm_client
from app.ai.query_classifier import QueryType, get_query_classifier
from app.ai.query_parser import (
    DateExtractionResult,
    DateRangeResult,
    extract_date_details,
    extract_date_range,
    format_date_for_display,
)
from app.ai.speaker_parser import get_speaker_parser
from app.ai.biblical_reference_parser import get_biblical_reference_parser
from app.ai.biblical_passage_service import get_biblical_passage_service
from app.ai.theme_parser import get_theme_parser
from app.ai.theme_service import get_theme_service
from app.common.database import get_db
from app.common.models import GeminiChatHistory, Video

MONTH_NAMES_PT = [
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Channel-specific chatbot using RAG (Retrieval-Augmented Generation)

    Features:
    - Retrieves relevant sermon segments using embeddings
    - Generates contextual answers with unified LLM client (Gemini or Ollama)
    - Maintains conversation history
    - Cites specific sermons and timestamps
    - Automatically falls back to local Ollama when Gemini quota is exhausted
    """

    def __init__(self):
        """Initialize chatbot service"""
        self.llm = get_llm_client()
        self.embedding_service = EmbeddingService()
        self.cache_manager = CacheManager()
        self.query_classifier = get_query_classifier()
        self.speaker_parser = get_speaker_parser()
        self.biblical_parser = get_biblical_reference_parser()
        self.passage_service = get_biblical_passage_service()
        self.theme_parser = get_theme_parser()
        self.theme_service = get_theme_service()
        logger.info("Chatbot service initialized with unified LLM client, caching, query classification, speaker detection, biblical reference parsing, and theme extraction")

    def chat(
        self,
        channel_id: int,
        user_message: str,
        session_id: str = None
    ) -> Dict:
        """
        Handle a chat message with caching

        Args:
            channel_id: Channel ID
            user_message: User's question
            session_id: Optional session ID for conversation history

        Returns:
            Dictionary with response and cited videos
        """
        # Generate or use existing session ID
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Chat request for channel {channel_id}: {user_message[:100]}")

        # Phase 1.1: Extract speaker from query
        speaker_result = self.speaker_parser.extract_speaker(user_message)
        speaker_filter = None

        if speaker_result.found:
            # Convert speaker name to SQL ILIKE pattern for partial matching
            speaker_filter = self.speaker_parser.get_search_pattern(speaker_result.speaker_name)
            logger.info(f"🎤 Speaker filter applied: '{speaker_result.speaker_name}' (pattern: {speaker_filter})")

        # Phase 1.2: Extract biblical reference from query
        biblical_ref = self.biblical_parser.extract_reference(user_message)
        video_ids_filter = None

        if biblical_ref.found:
            # Get videos that reference this passage
            video_ids_filter = self.passage_service.find_sermons_by_reference(
                channel_id=channel_id,
                reference=biblical_ref,
                passage_types=None  # Search all types (citation, reading, mention)
            )

            if video_ids_filter:
                logger.info(f"📖 Biblical filter applied: {biblical_ref.osis_ref} ({len(video_ids_filter)} sermons found)")
            else:
                logger.warning(f"📖 No sermons found referencing {biblical_ref.osis_ref}")

        # Phase 1.3: Extract themes from query
        theme_result = self.theme_parser.extract_themes(user_message)
        theme_video_ids = None

        if theme_result.found:
            # Get videos that match these themes
            theme_video_ids = self.theme_service.find_sermons_by_themes(
                channel_id=channel_id,
                themes=theme_result.themes,
                min_confidence=0.5,  # Use themes with confidence >= 0.5
                use_and_logic=False  # OR logic: match ANY theme by default
            )

            if theme_video_ids:
                logger.info(f"🎨 Theme filter applied: {theme_result.themes} ({len(theme_video_ids)} sermons found)")
            else:
                logger.warning(f"🎨 No sermons found with themes {theme_result.themes}")

            # Combine theme filter with biblical filter if both exist
            if video_ids_filter is not None:
                # Intersection: sermons must match BOTH biblical reference AND themes
                combined_ids = set(video_ids_filter) & set(theme_video_ids)
                video_ids_filter = list(combined_ids)
                logger.info(f"🔗 Combined biblical + theme filters: {len(video_ids_filter)} sermons")
            else:
                # Use theme filter alone
                video_ids_filter = theme_video_ids

        # Phase 2: Use enhanced date range extraction
        date_range = extract_date_range(user_message)

        if date_range:
            if date_range.is_range and date_range.start_date and date_range.end_date:
                logger.info(
                    "📅 Date range detected: %s to %s (type=%s)",
                    date_range.start_date.date(),
                    date_range.end_date.date(),
                    date_range.query_type
                )
            elif date_range.query_type in ['last_sermon', 'second_last_sermon']:
                logger.info(f"🔍 Smart query detected: {date_range.query_type}")
            elif date_range.start_date:
                logger.info(
                    "📅 Single date detected: %s (type=%s)",
                    date_range.start_date.date(),
                    date_range.query_type
                )
        else:
            logger.debug("No date filter found in query - searching all videos")

        # Use Phase 2 search with date range support + Phase 1.1 speaker filter + Phase 1.2 biblical filter
        if date_range:
            relevant_segments = self._search_with_date_range(
                channel_id=channel_id,
                query=user_message,
                date_range=date_range,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
        else:
            # No date filter - search all videos (with optional speaker and biblical filters)
            relevant_segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=user_message,
                top_k=10,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )

        # Debug logging
        logger.info(f"📊 Found {len(relevant_segments)} relevant segments")
        if relevant_segments:
            logger.info(f"📚 Videos: {[s['video_title'] for s in relevant_segments]}")
            # Log speaker information
            speakers = set(s.get('speaker', 'Desconhecido') for s in relevant_segments)
            logger.info(f"🎤 Speakers in results: {speakers}")
            relevance_pcts = [f"{s['relevance']:.2%}" for s in relevant_segments]
            logger.info(f"🎯 Relevance scores: {relevance_pcts}")
        else:
            if speaker_filter:
                logger.warning(f"⚠️ No relevant segments found for query with speaker filter '{speaker_result.speaker_name}': {user_message[:100]}")
            else:
                logger.warning(f"⚠️ No relevant segments found for query: {user_message[:100]}")

        # Extract video IDs for cache key
        video_ids = [seg['video_id'] for seg in relevant_segments]

        # Check cache first
        cached_response = self.cache_manager.get_cached_response(
            user_message,
            video_ids
        )

        if cached_response:
            logger.info(f"Using cached chatbot response (age={cached_response['cache_age_hours']:.1f}h)")

            # Still save to history for conversation tracking
            self._save_history_entry(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=cached_response['response'],
                cited_videos=cached_response['cited_videos']
            )

            return {
                'response': cached_response['response'],
                'cited_videos': cached_response['cited_videos'],
                'session_id': session_id,
                'relevance_scores': cached_response['relevance_scores'],
                'cached': True,
                'cache_age_hours': cached_response['cache_age_hours'],
                'hit_count': cached_response['hit_count']
            }

        # Cache miss - generate new response
        logger.info(f"Generating new chatbot response with LLM")

        # Classify query to determine optimal response configuration
        query_type, response_config = self.query_classifier.classify_and_configure(user_message)
        logger.info(f"🎯 Query classified as {query_type.value}, using max_tokens={response_config.max_tokens}")

        # Get conversation history
        conversation_context = self._get_conversation_history(
            channel_id, session_id, limit=3
        )

        # Build prompt with context and query-type specific instruction
        prompt = self._build_prompt(
            user_message,
            relevant_segments,
            conversation_context,
            query_type=query_type,
            response_instruction=response_config.instruction,
            biblical_ref=biblical_ref if biblical_ref.found else None,
            theme_result=theme_result if theme_result.found else None
        )

        # Generate response using unified LLM client with query-specific max_tokens
        llm_response = self.llm.generate(
            prompt=prompt,
            max_tokens=response_config.max_tokens,
            temperature=0.7
        )
        response_text = llm_response["text"]
        backend_used = llm_response["backend"]

        logger.info(f"✅ Chatbot response generated using {backend_used} backend (query_type={query_type.value})")

        unique_sources = self._build_unique_citations(relevant_segments)
        cited_videos = [entry['citation'] for entry in unique_sources]
        relevance_scores = [entry['relevance'] for entry in unique_sources]

        # Store in cache
        self.cache_manager.store_response(
            user_message,
            video_ids,
            response_text,
            cited_videos,
            relevance_scores
        )

        # Save to history
        self._save_history_entry(
            channel_id=channel_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=response_text,
            cited_videos=cited_videos
        )

        return {
            'response': response_text,
            'cited_videos': cited_videos,
            'session_id': session_id,
            'relevance_scores': relevance_scores,
            'cached': False,
            'backend': backend_used,
            'tokens_used': llm_response.get('tokens_used', 0)
        }

    def _build_prompt(
        self,
        user_message: str,
        relevant_segments: List[Dict],
        conversation_context: List[Dict],
        query_type: QueryType = QueryType.GENERAL,
        response_instruction: str = "",
        biblical_ref = None,
        theme_result = None
    ) -> str:
        """Build prompt for Gemini with context and query-type specific instructions"""
        # Format relevant segments with dates and speaker for clear identification
        context_parts = []
        for seg in relevant_segments:
            # Format date as "DD/MM/YYYY" to match Brazilian format
            date_str = seg['published_at'].strftime('%d/%m/%Y') if seg.get('published_at') else "Data desconhecida"
            speaker = seg.get('speaker', 'Desconhecido')
            sermon_header = f"[Sermão: {seg['video_title']} - {date_str} - Pregador: {speaker}]"
            context_parts.append(f"{sermon_header}\n{seg['segment_text']}")

        context_text = "\n\n---\n\n".join(context_parts)

        # Format conversation history
        history_text = ""
        if conversation_context:
            history_text = "\n\nConversa anterior:\n" + "\n".join([
                f"Usuário: {msg['user']}\nAssistente: {msg['assistant']}"
                for msg in conversation_context
            ])

        # Add query-type specific instruction
        type_specific_rule = ""
        if response_instruction:
            type_specific_rule = f"\n8. FORMATO DA RESPOSTA: {response_instruction}"

        # Add biblical reference context if present
        biblical_context = ""
        if biblical_ref:
            ref_display = biblical_ref.osis_ref
            if biblical_ref.is_whole_book:
                ref_display = f"todo o livro de {biblical_ref.book}"
            elif biblical_ref.is_whole_chapter:
                ref_display = f"{biblical_ref.book} capítulo {biblical_ref.chapter}"
            else:
                chapter = biblical_ref.chapter
                verse_start = biblical_ref.verse_start
                verse_end = biblical_ref.verse_end
                if verse_end and verse_end != verse_start:
                    ref_display = f"{biblical_ref.book} {chapter}:{verse_start}-{verse_end}"
                else:
                    ref_display = f"{biblical_ref.book} {chapter}:{verse_start}"

            biblical_context = f"\n\nCONTEXTO BÍBLICO:\nO usuário perguntou especificamente sobre {ref_display}. Os sermões abaixo foram selecionados porque citam, leem ou mencionam esta passagem bíblica."

        # Add theme context if present (Phase 1.3)
        theme_context = ""
        if theme_result and theme_result.found:
            themes_display = ", ".join(theme_result.themes)
            theme_context = f"\n\nCONTEXTO TEMÁTICO:\nO usuário perguntou especificamente sobre os temas teológicos: {themes_display}. Os sermões abaixo foram selecionados porque abordam estes temas."

        prompt = f"""
Você é um assistente teológico especializado em sermões desta igreja.
Responda a pergunta do usuário baseando-se nos sermões fornecidos abaixo como contexto principal.

REGRAS:
1. Cite o sermão específico ao responder (use o título fornecido entre colchetes)
2. Use os trechos fornecidos como base principal para sua resposta
3. Se não encontrar informação direta, ofereça contexto relacionado dos sermões disponíveis
4. Quando os sermões não cobrem o tema, seja honesto: "Nos sermões disponíveis, não encontrei referência direta a [tema], mas temas relacionados incluem..."
5. Seja conciso mas informativo (ajuste o tamanho conforme o tipo de pergunta)
6. Use linguagem pastoral e respeitosa
7. Quando relevante, conecte insights de diferentes sermões{type_specific_rule}{biblical_context}{theme_context}

SERMÕES RELEVANTES:
{context_text}

{history_text}

PERGUNTA DO USUÁRIO:
{user_message}

RESPOSTA:
"""
        return prompt

    def _get_conversation_history(
        self,
        channel_id: int,
        session_id: str,
        limit: int = 3
    ) -> List[Dict]:
        """Get recent conversation history"""
        with get_db() as db:
            history = db.query(GeminiChatHistory).filter(
                GeminiChatHistory.channel_id == channel_id,
                GeminiChatHistory.session_id == session_id
            ).order_by(
                GeminiChatHistory.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    'user': h.user_message,
                    'assistant': h.assistant_response
                }
                for h in reversed(history)
            ]

    def _should_try_date_fallback(
        self,
        date_info: Optional[DateExtractionResult],
        segments: List[Dict]
    ) -> bool:
        """Only fallback when the user omitted the year and no segments were found."""
        if not date_info or segments:
            return False

        if date_info.explicit_year:
            return False

        return date_info.source in {'numeric', 'day_month_name', 'month_day_name'}

    def _find_latest_matching_date(
        self,
        channel_id: int,
        reference_date: Optional[datetime]
    ) -> Optional[datetime]:
        """
        Look up the most recent year that has a sermon on the requested day/month.
        Ensures the video already has embeddings before falling back.
        """
        if not reference_date:
            return None

        target_date = reference_date.date()
        now = datetime.now(timezone.utc)

        with get_db() as db:
            result = db.execute(text("""
                SELECT COALESCE(v.sermon_actual_date, DATE(v.published_at)) AS sermon_date
                FROM videos v
                WHERE v.channel_id = :channel_id
                  AND COALESCE(v.sermon_actual_date, DATE(v.published_at)) = :target_date
                  AND v.published_at <= :search_limit
                  AND EXISTS (
                      SELECT 1
                      FROM transcript_embeddings te
                      WHERE te.video_id = v.id
                  )
                ORDER BY v.published_at DESC
                LIMIT 1
            """), {
                'channel_id': channel_id,
                'target_date': target_date,
                'search_limit': now
            }).scalar()

        if result:
            return datetime.combine(result, datetime.min.time())

        return None

    def _build_candidate_dates(
        self,
        date_info: Optional[DateExtractionResult]
    ) -> List[datetime]:
        """Return ordered unique list of candidate dates derived from parser info."""
        if not date_info:
            return []

        candidates: List[datetime] = []
        seen = set()
        for dt in [date_info.date] + (date_info.alternatives or []):
            if dt and dt.date() not in seen:
                candidates.append(dt)
                seen.add(dt.date())
        return candidates

    def _search_candidate_dates(
        self,
        channel_id: int,
        query: str,
        candidate_dates: Sequence[datetime]
    ) -> List[Tuple[Optional[datetime], List[Dict]]]:
        """Run embedding search for each candidate date (or all videos when empty)."""
        attempts: List[Tuple[Optional[datetime], List[Dict]]] = []

        if candidate_dates:
            for date_option in candidate_dates:
                segments = self.embedding_service.search_similar_segments(
                    channel_id=channel_id,
                    query=query,
                    top_k=10,
                    date_filter=date_option
                )
                attempts.append((date_option, segments))
        else:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=None
            )
            attempts.append((None, segments))

        return attempts

    def _respond_with_ambiguity(
        self,
        channel_id: int,
        session_id: str,
        user_message: str,
        date_info: DateExtractionResult,
        successful_attempts: Sequence[Tuple[datetime, List[Dict]]]
    ) -> Dict:
        """Ask user to clarify when multiple ambiguous dates yield results."""
        options_text = []
        for dt, _ in successful_attempts:
            formatted = format_date_for_display(dt)
            human = self._format_portuguese_date(dt)
            options_text.append(f"- {formatted} ({human})")

        raw_text = date_info.raw_text or "essa data"
        clarification_message = (
            f"Percebi que \"{raw_text}\" pode se referir a mais de uma data. "
            "Pode confirmar qual delas você deseja consultar?\n\n"
            + "\n".join(options_text)
            + "\n\nExemplo: responda \"02/11/2025\" ou \"11/02/2025\"."
        )

        self._save_history_entry(
            channel_id=channel_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=clarification_message,
            cited_videos=[]
        )

        return {
            'response': clarification_message,
            'cited_videos': [],
            'session_id': session_id,
            'relevance_scores': [],
            'cached': False,
            'clarification_required': True
        }

    def _attempt_year_fallback(
        self,
        channel_id: int,
        query: str,
        date_info: Optional[DateExtractionResult],
        already_tried: Sequence[datetime]
    ) -> Tuple[Optional[datetime], List[Dict]]:
        """Search older sermons for the same day/month when year wasn't specified."""
        if not date_info:
            return None, []

        tried_dates = {dt.date() for dt in already_tried if dt}
        reference_dates = [date_info.date] + (date_info.alternatives or [])

        for reference in reference_dates:
            if not reference:
                continue

            fallback_date = self._find_latest_matching_date(channel_id, reference)
            if not fallback_date or fallback_date.date() in tried_dates:
                continue

            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=fallback_date
            )

            if segments:
                logger.info(
                    "🔁 No sermons found for %s – falling back to available date %s",
                    reference.date(),
                    fallback_date.date()
                )
                return fallback_date, segments

        if reference_dates:
            logger.info("ℹ️ Date fallback unavailable for %s", reference_dates[0].date())
        else:
            logger.info("ℹ️ Date fallback unavailable")

        return None, []

    def _format_portuguese_date(self, value: datetime) -> str:
        """Return a human-readable Portuguese date string."""
        month_name = MONTH_NAMES_PT[value.month]
        return f"{value.day} de {month_name} de {value.year}"

    def _build_unique_citations(
        self,
        segments: List[Dict]
    ) -> List[Dict]:
        """
        Deduplicate citation list so each video appears once with MM/DD/YYYY date.
        Keeps the segment with the highest relevance score.
        Includes speaker information in citation (Phase 1.1).
        """
        unique: Dict[int, Dict] = {}

        for seg in segments:
            video_id = seg['video_id']
            sermon_date = seg.get('sermon_actual_date')
            if not sermon_date:
                published_at = seg.get('published_at')
                sermon_date = published_at.date() if published_at else None

            date_str = sermon_date.strftime('%m/%d/%Y') if sermon_date else "Unknown date"
            speaker = seg.get('speaker', 'Desconhecido')

            # Include speaker in title: "MM/DD/YYYY - Title (Speaker)"
            title_with_date = f"{date_str} - {seg['video_title']}"
            if speaker and speaker != 'Desconhecido':
                title_with_date += f" ({speaker})"

            citation = {
                'video_id': video_id,
                'video_title': title_with_date,
                'youtube_id': seg['youtube_id'],
                'timestamp': seg['segment_start'],
                'speaker': speaker  # Include speaker in citation metadata
            }

            if (
                video_id not in unique
                or seg['relevance'] > unique[video_id]['relevance']
            ):
                unique[video_id] = {
                    'citation': citation,
                    'relevance': seg['relevance']
                }

        return sorted(unique.values(), key=lambda entry: entry['relevance'], reverse=True)

    def _save_history_entry(
        self,
        channel_id: int,
        session_id: str,
        user_message: str,
        assistant_response: str,
        cited_videos: List[Dict]
    ) -> None:
        """Persist conversation turns for continuity."""
        with get_db() as db:
            history_entry = GeminiChatHistory(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=assistant_response,
                cited_videos=cited_videos
            )
            db.add(history_entry)
            db.commit()

    def _get_last_sermon(self, channel_id: int, offset: int = 0) -> Optional[Video]:
        """
        Get the most recent sermon with transcript from database.

        Args:
            channel_id: Channel ID
            offset: Offset for getting nth-last sermon (0=last, 1=second-last, etc.)

        Returns:
            Video object or None
        """
        with get_db() as db:
            sermon = db.query(Video).filter(
                Video.channel_id == channel_id,
                Video.status == 'completed'
            ).join(
                Video.transcript
            ).order_by(
                Video.published_at.desc()
            ).offset(offset).limit(1).first()

            return sermon

    def _search_with_date_range(
        self,
        channel_id: int,
        query: str,
        date_range: DateRangeResult,
        speaker_filter: Optional[str] = None,
        video_ids_filter: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Search segments using date range information from Phase 2 parser.

        Args:
            channel_id: Channel ID
            query: Search query
            date_range: Parsed date range result
            speaker_filter: Optional speaker filter pattern (Phase 1.1)
            video_ids_filter: Optional list of video IDs to restrict search (Phase 1.2)

        Returns:
            List of relevant segments
        """
        # Handle smart "last sermon" queries
        if date_range.query_type == 'last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=0)
            if not sermon:
                return []

            # Search only in this specific sermon
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon.published_at,
                end_date=sermon.published_at,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments in last sermon (video_id={sermon.id})")
            return segments

        elif date_range.query_type == 'second_last_sermon':
            sermon = self._get_last_sermon(channel_id, offset=1)
            if not sermon:
                return []

            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=sermon.published_at,
                end_date=sermon.published_at,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments in second-last sermon (video_id={sermon.id})")
            return segments

        # Handle date range queries
        elif date_range.is_range and date_range.start_date and date_range.end_date:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                start_date=date_range.start_date,
                end_date=date_range.end_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(
                f"Found {len(segments)} segments in date range "
                f"{date_range.start_date.date()} to {date_range.end_date.date()}"
            )
            return segments

        # Handle single date queries
        elif date_range.start_date and not date_range.is_range:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                date_filter=date_range.start_date,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments for date {date_range.start_date.date()}")
            return segments

        # No valid date - search all
        else:
            segments = self.embedding_service.search_similar_segments(
                channel_id=channel_id,
                query=query,
                top_k=10,
                speaker_filter=speaker_filter,
                video_ids_filter=video_ids_filter
            )
            logger.info(f"Found {len(segments)} segments (no date filter)")
            return segments
