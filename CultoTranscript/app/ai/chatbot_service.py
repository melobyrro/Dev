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
from app.ai.gemini_client import get_gemini_client
from app.ai.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Channel-specific chatbot using RAG (Retrieval-Augmented Generation)

    Features:
    - Retrieves relevant sermon segments using embeddings
    - Generates contextual answers with Gemini
    - Maintains conversation history
    - Cites specific sermons and timestamps
    """

    def __init__(self):
        """Initialize chatbot service"""
        self.gemini = get_gemini_client()
        self.embedding_service = EmbeddingService()
        logger.info("Chatbot service initialized")

    def chat(
        self,
        channel_id: int,
        user_message: str,
        session_id: str = None
    ) -> Dict:
        """
        Handle a chat message

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

        # Generate response
        response_text = self.gemini.generate_content(prompt)

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
            'relevance_scores': [s['relevance'] for s in relevant_segments]
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
Responda a pergunta do usuário baseando-se APENAS nos sermões fornecidos abaixo.

REGRAS:
1. Cite o sermão específico ao responder (use o título fornecido)
2. Se a informação não estiver nos sermões, diga "Não encontrei isso nos sermões disponíveis"
3. Seja conciso mas informativo
4. Use linguagem pastoral e respeitosa
5. Quando relevante, conecte diferentes sermões

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
