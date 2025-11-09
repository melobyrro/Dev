"""
Sermon Detection Module
Uses unified LLM client (Gemini or Ollama) to detect when the sermon actually begins in a worship service video
"""
import logging
import re
from typing import Optional, Tuple
from app.ai.llm_client import get_llm_client

logger = logging.getLogger(__name__)


SERMON_DETECTION_PROMPT = """Você é um assistente especializado em analisar transcrições de cultos cristãos.

Sua tarefa é identificar o momento aproximado em que o SERMÃO (pregação) começa na transcrição abaixo.

Contexto: Normalmente, os primeiros 20-40 minutos de um culto incluem:
- Avisos e anúncios da igreja
- Músicas de louvor e adoração
- Oração inicial
- Leitura bíblica preliminar

O SERMÃO geralmente começa quando:
- O pregador apresenta o texto bíblico principal
- Começa a exposição/exegese do texto
- Frases como "vamos abrir", "o texto de hoje", "palavra de Deus", "pregação"
- Mudança de tom: de informal (avisos) para formal (ensino)

INSTRUÇÕES:
1. Analise a transcrição completa
2. Identifique o momento aproximado (em minutos) quando o sermão começa
3. Se o sermão começa imediatamente (sem avisos/músicas), retorne 0
4. Se não conseguir detectar claramente, retorne sua melhor estimativa

IMPORTANTE: Retorne APENAS um número inteiro representando os minutos. Nada mais.
Exemplo de resposta: 28

TRANSCRIÇÃO:
{transcript}

RESPOSTA (apenas o número de minutos):"""


def detect_sermon_start(transcript_text: str, duration_sec: int) -> Optional[int]:
    """
    Detect when the sermon starts in a worship service transcript using Gemini AI

    Args:
        transcript_text: Full transcript text
        duration_sec: Video duration in seconds

    Returns:
        Sermon start time in seconds, or None if detection fails
        Returns 0 if sermon starts immediately
    """
    try:
        # Skip detection for very short videos (< 10 minutes)
        if duration_sec < 600:
            logger.info(f"Video too short ({duration_sec}s), assuming sermon starts at 0:00")
            return 0

        # Truncate transcript if too long (keep first 30 minutes worth of content)
        # Estimate: ~150 words per minute, ~4 chars per word = ~600 chars/min
        max_chars = 30 * 600  # ~18000 chars
        truncated_text = transcript_text[:max_chars] if len(transcript_text) > max_chars else transcript_text

        # Get unified LLM client
        llm = get_llm_client()

        # Generate prompt
        prompt = SERMON_DETECTION_PROMPT.format(transcript=truncated_text)

        # Call LLM
        logger.info("Calling LLM to detect sermon start time...")
        llm_response = llm.generate(
            prompt=prompt,
            max_tokens=20,
            temperature=0.3
        )
        response = llm_response["text"]
        backend_used = llm_response["backend"]

        # Parse response - extract first number found
        match = re.search(r'\d+', response.strip())
        if not match:
            logger.warning(f"Could not parse sermon start time from LLM response: {response}")
            return None

        minutes = int(match.group())
        seconds = minutes * 60

        # Sanity check: sermon start time shouldn't exceed video duration
        if seconds >= duration_sec:
            logger.warning(f"Detected sermon start ({seconds}s) exceeds video duration ({duration_sec}s), using 0")
            return 0

        logger.info(f"✅ Detected sermon start using {backend_used} backend: {minutes} minutes ({seconds} seconds)")
        return seconds

    except Exception as e:
        logger.error(f"Error detecting sermon start: {e}", exc_info=True)
        return None


def format_sermon_time(seconds: Optional[int]) -> str:
    """
    Format sermon start time for display

    Args:
        seconds: Sermon start time in seconds

    Returns:
        Formatted time string (e.g., "28:30")
    """
    if seconds is None:
        return "Não detectado"

    if seconds == 0:
        return "Início (0:00)"

    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def get_sermon_portion(transcript_text: str, sermon_start_time: Optional[int]) -> str:
    """
    Extract the sermon portion of the transcript

    Args:
        transcript_text: Full transcript text
        sermon_start_time: Sermon start time in seconds (or None)

    Returns:
        Sermon portion of transcript (or full transcript if no start time)
    """
    if sermon_start_time is None or sermon_start_time == 0:
        return transcript_text

    # Estimate character position based on sermon start time
    # Rough estimate: ~150 words/min * 4 chars/word = ~600 chars/min
    chars_per_second = 10
    start_char = sermon_start_time * chars_per_second

    # Make sure we don't exceed transcript length
    if start_char >= len(transcript_text):
        logger.warning(f"Sermon start position ({start_char}) exceeds transcript length ({len(transcript_text)})")
        return transcript_text

    return transcript_text[start_char:]
