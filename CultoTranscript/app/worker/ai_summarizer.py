"""
AI Sermon Summarizer
Generates narrative summaries of sermons using Gemini AI
"""
import logging
from typing import Optional
from app.ai.gemini_client import GeminiClient
from app.ai.sermon_detector import get_sermon_portion

logger = logging.getLogger(__name__)


SUMMARY_PROMPT_TEMPLATE = """Você é um assistente especializado em analisar sermões cristãos.

Sua tarefa é criar um resumo narrativo do sermão abaixo, focando no conteúdo teológico e mensagem principal.

O resumo deve ter 3-4 parágrafos e incluir:
1. **Tema Central**: Qual é o tema principal do sermão?
2. **Texto Bíblico**: Qual(is) texto(s) bíblico(s) foram usados como base?
3. **Pontos Principais**: Quais foram os principais pontos desenvolvidos pelo pregador?
4. **Aplicação Prática**: Qual aplicação prática foi sugerida para os ouvintes?

IMPORTANTE:
- Escreva de forma clara e objetiva
- Use linguagem acessível (evite jargão teológico complexo)
- Foque no conteúdo do sermão, não na forma de apresentação
- NÃO mencione avisos, músicas ou elementos externos ao sermão

TRANSCRIÇÃO DO SERMÃO:
{transcript}

RESUMO (3-4 parágrafos):"""


def generate_ai_summary(
    transcript_text: str,
    sermon_start_time: Optional[int],
    gemini_client: GeminiClient
) -> str:
    """
    Generate AI-powered narrative summary of a sermon

    Args:
        transcript_text: Full transcript text
        sermon_start_time: Sermon start time in seconds (or None)
        gemini_client: Initialized Gemini client

    Returns:
        AI-generated summary as plain text
    """
    try:
        # Extract sermon portion
        sermon_text = get_sermon_portion(transcript_text, sermon_start_time)

        # Truncate if too long (max ~50,000 chars for context window)
        max_chars = 50000
        if len(sermon_text) > max_chars:
            logger.warning(f"Sermon text too long ({len(sermon_text)} chars), truncating to {max_chars}")
            sermon_text = sermon_text[:max_chars]

        # Generate prompt
        prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=sermon_text)

        # Call Gemini
        logger.info("Generating AI summary...")
        summary = gemini_client.generate_content(prompt)

        # Validate output
        if not summary or len(summary.strip()) < 100:
            logger.warning(f"Generated summary is too short ({len(summary)} chars)")
            return "Resumo não disponível - falha na geração"

        logger.info(f"AI summary generated successfully ({len(summary)} chars)")
        return summary.strip()

    except Exception as e:
        error_str = str(e)
        # Check if it's a quota error (429)
        if "429" in error_str or "quota" in error_str.lower():
            logger.warning(f"Gemini API quota exhausted for summary generation: {e}")
            return "Resumo não disponível - cota da API Gemini atingida (reprocesse após 24h)"
        else:
            logger.error(f"Failed to generate AI summary: {e}", exc_info=True)
            return f"Erro ao gerar resumo: {str(e)}"


def generate_short_summary(full_summary: str, max_length: int = 200) -> str:
    """
    Extract first sentence or create short summary from full summary

    Args:
        full_summary: Full AI-generated summary
        max_length: Maximum length for short summary

    Returns:
        Short summary suitable for preview/listing
    """
    if not full_summary:
        return "Resumo não disponível"

    # Try to get first sentence
    sentences = full_summary.split('.')
    if sentences and len(sentences[0]) > 20:
        first_sentence = sentences[0].strip() + '.'
        if len(first_sentence) <= max_length:
            return first_sentence

    # Truncate if needed
    if len(full_summary) <= max_length:
        return full_summary

    return full_summary[:max_length].rsplit(' ', 1)[0] + '...'


SPEAKER_EXTRACTION_PROMPT = """Você é um assistente especializado em analisar sermões cristãos.

Sua tarefa é identificar o nome do pregador/palestrante principal neste sermão.

INSTRUÇÕES:
1. Procure por auto-apresentações (ex: "meu nome é...", "eu sou...")
2. Procure por referências de outras pessoas (ex: "pastor João", "pregador Maria")
3. Se não encontrar o nome claramente, retorne "Desconhecido"
4. Retorne APENAS o nome, sem título (sem "Pastor", "Pr.", "Bispo", etc)
5. Use capitalização apropriada (primeira letra maiúscula)

TRANSCRIÇÃO DO SERMÃO (primeiros minutos):
{transcript_sample}

RESPOSTA (apenas o nome):"""


def extract_speaker_name(
    transcript_text: str,
    gemini_client: GeminiClient
) -> str:
    """
    Extract the speaker/preacher name from sermon transcript using Gemini AI

    Args:
        transcript_text: Full transcript text
        gemini_client: Initialized Gemini client

    Returns:
        Speaker name or "Desconhecido" if not found
    """
    try:
        # Use first 10,000 characters (usually contains introduction)
        sample_text = transcript_text[:10000]

        # Generate prompt
        prompt = SPEAKER_EXTRACTION_PROMPT.format(transcript_sample=sample_text)

        # Call Gemini
        logger.info("Extracting speaker name with Gemini...")
        response = gemini_client.generate_content(prompt)

        # Clean up response
        speaker_name = response.strip()

        # Remove common titles if present
        titles_to_remove = ['pastor', 'pr.', 'pr', 'pregador', 'bispo', 'rev.', 'reverendo', 'irmão', 'irmã']
        for title in titles_to_remove:
            speaker_name = speaker_name.replace(title, '').replace(title.title(), '').strip()

        # Validate result
        if not speaker_name or len(speaker_name) < 2 or len(speaker_name) > 100:
            logger.warning(f"Invalid speaker name extracted: '{speaker_name}'")
            return "Desconhecido"

        # Capitalize properly
        speaker_name = ' '.join(word.capitalize() for word in speaker_name.split())

        logger.info(f"Speaker name extracted: {speaker_name}")
        return speaker_name

    except Exception as e:
        error_str = str(e)
        # Check if it's a quota error (429)
        if "429" in error_str or "quota" in error_str.lower():
            logger.warning(f"Gemini API quota exhausted for speaker extraction: {e}")
        else:
            logger.error(f"Failed to extract speaker name: {e}", exc_info=True)

        return "Desconhecido"
