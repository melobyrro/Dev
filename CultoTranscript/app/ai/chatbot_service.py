"""
Channel Chatbot Service
Conversational AI for Q&A about channel sermons
"""
import logging
import uuid
from typing import List, Dict
from datetime import datetime

from app.common.database import get_db
from app.common.models import GeminiChatHistory
from app.ai.llm_client import get_llm_client
from app.ai.embedding_service import EmbeddingService
from app.ai.cache_manager import CacheManager

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
        logger.info("Chatbot service initialized with unified LLM client and caching")

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

        # Retrieve relevant sermon segments
        relevant_segments = self.embedding_service.search_similar_segments(
            channel_id=channel_id,
            query=user_message,
            top_k=3
        )

        # Debug logging
        logger.info(f"📊 Found {len(relevant_segments)} relevant segments")
        if relevant_segments:
            logger.info(f"📚 Videos: {[s['video_title'] for s in relevant_segments]}")
            relevance_pcts = [f"{s['relevance']:.2%}" for s in relevant_segments]
            logger.info(f"🎯 Relevance scores: {relevance_pcts}")
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
            with get_db() as db:
                history_entry = GeminiChatHistory(
                    channel_id=channel_id,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=cached_response['response'],
                    cited_videos=cached_response['cited_videos']
                )
                db.add(history_entry)
                db.commit()

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

        # Get conversation history
        conversation_context = self._get_conversation_history(
            channel_id, session_id, limit=3
        )

        # Build prompt with context
        prompt = self._build_prompt(
            user_message,
            relevant_segments,
            conversation_context
        )

        # Generate response using unified LLM client
        llm_response = self.llm.generate(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.7
        )
        response_text = llm_response["text"]
        backend_used = llm_response["backend"]

        logger.info(f"✅ Chatbot response generated using {backend_used} backend")

        # Extract cited videos
        cited_videos = [
            {
                'video_id': seg['video_id'],
                'video_title': seg['video_title'],
                'youtube_id': seg['youtube_id'],
                'timestamp': seg['segment_start']  # In words, convert to seconds
            }
            for seg in relevant_segments
        ]

        # Extract relevance scores
        relevance_scores = [s['relevance'] for s in relevant_segments]

        # Store in cache
        self.cache_manager.store_response(
            user_message,
            video_ids,
            response_text,
            cited_videos,
            relevance_scores
        )

        # Save to history
        with get_db() as db:
            history_entry = GeminiChatHistory(
                channel_id=channel_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=response_text,
                cited_videos=cited_videos
            )
            db.add(history_entry)
            db.commit()

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
        conversation_context: List[Dict]
    ) -> str:
        """Build prompt for Gemini with context"""
        # Format relevant segments
        context_text = "\n\n---\n\n".join([
            f"[Sermão: {seg['video_title']}]\n{seg['segment_text']}"
            for seg in relevant_segments
        ])

        # Format conversation history
        history_text = ""
        if conversation_context:
            history_text = "\n\nConversa anterior:\n" + "\n".join([
                f"Usuário: {msg['user']}\nAssistente: {msg['assistant']}"
                for msg in conversation_context
            ])

        prompt = f"""
Você é um assistente teológico especializado em sermões desta igreja.
Responda a pergunta do usuário baseando-se nos sermões fornecidos abaixo como contexto principal.

REGRAS:
1. Cite o sermão específico ao responder (use o título fornecido entre colchetes)
2. Use os trechos fornecidos como base principal para sua resposta
3. Se não encontrar informação direta, ofereça contexto relacionado dos sermões disponíveis
4. Quando os sermões não cobrem o tema, seja honesto: "Nos sermões disponíveis, não encontrei referência direta a [tema], mas temas relacionados incluem..."
5. Seja conciso mas informativo (máximo 3-4 parágrafos)
6. Use linguagem pastoral e respeitosa
7. Quando relevante, conecte insights de diferentes sermões

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
