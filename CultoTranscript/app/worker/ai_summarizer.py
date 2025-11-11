"""
AI Sermon Summarizer
Generates narrative summaries of sermons using unified LLM client (Gemini or Ollama)
"""
import logging
from typing import Optional
from app.ai.llm_client import get_llm_client
from app.ai.sermon_detector import get_sermon_portion

logger = logging.getLogger(__name__)


SUMMARY_PROMPT_TEMPLATE = """Você é um assistente especializado em analisar sermões cristãos.

Crie um resumo estruturado do sermão abaixo em formato de tópicos (bullets).

Organize o resumo nas seguintes seções usando bullets:

## 📖 Tema Central
- [Uma linha descrevendo o tema principal do sermão]

## 📕 Texto(s) Bíblico(s)
- [Liste as passagens bíblicas principais usadas como base]
- [Adicione mais se houver múltiplas passagens]

## 💡 Pontos Principais
- [Primeiro ponto principal desenvolvido]
- [Segundo ponto principal]
- [Terceiro ponto principal]
- [Adicione mais conforme necessário]

## ✨ Aplicação Prática
- [Principal aplicação prática sugerida pelo pregador]
- [Outras aplicações relevantes se houver]

IMPORTANTE:
- Use formato de bullets (lista de pontos)
- Seja conciso e objetivo em cada ponto
- Use linguagem acessível (evite jargão teológico complexo)
- Foque no conteúdo do sermão, não na forma de apresentação
- NÃO mencione avisos, músicas ou elementos externos ao sermão

TRANSCRIÇÃO DO SERMÃO:
{transcript}

RESUMO EM BULLETS:"""


def generate_ai_summary(
    transcript_text: str,
    sermon_start_time: Optional[int] = None
) -> str:
    """
    Generate AI-powered narrative summary of a sermon

    Args:
        transcript_text: Full transcript text
        sermon_start_time: Sermon start time in seconds (or None)

    Returns:
        AI-generated summary as plain text
    """
    try:
        logger.info(f"📝 Starting AI summary generation - transcript_length: {len(transcript_text)}, sermon_start: {sermon_start_time}")

        # Extract sermon portion
        sermon_text = get_sermon_portion(transcript_text, sermon_start_time)
        logger.info(f"✂️ Sermon portion extracted - length: {len(sermon_text)} chars")
        logger.debug(f"Sermon text preview: {sermon_text[:300]}...")

        # Truncate if too long (max ~50,000 chars for context window)
        max_chars = 50000
        if len(sermon_text) > max_chars:
            logger.warning(f"⚠️ Sermon text too long ({len(sermon_text)} chars), truncating to {max_chars}")
            sermon_text = sermon_text[:max_chars]
        else:
            logger.info(f"✅ Sermon text fits within limit ({len(sermon_text)} chars)")

        # Generate prompt
        prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=sermon_text)
        logger.info(f"📋 Prompt generated - total length: {len(prompt)} chars")

        # Call unified LLM client
        llm = get_llm_client()
        logger.info("🤖 Generating AI summary with LLM...")
        llm_response = llm.generate(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.7
        )
        summary = llm_response["text"]
        backend_used = llm_response["backend"]

        logger.info(f"📦 LLM response received - backend: {backend_used}, text_length: {len(summary)}")
        logger.debug(f"Summary preview: {summary[:300] if summary else '(empty)'}...")

        # Validate output
        if not summary or len(summary.strip()) < 100:
            logger.warning(f"❌ Generated summary validation FAILED - length: {len(summary) if summary else 0} chars (minimum: 100)")
            logger.warning(f"❌ Summary content: '{summary}'")
            return "Resumo não disponível - falha na geração"

        final_summary = summary.strip()
        logger.info(f"✅ AI summary generated successfully using {backend_used} backend ({len(final_summary)} chars)")
        logger.debug(f"Final summary preview: {final_summary[:200]}...")
        return final_summary

    except Exception as e:
        error_str = str(e)
        logger.error(f"❌ Failed to generate AI summary: {e}", exc_info=True)
        return "Erro ao gerar resumo (tente novamente mais tarde)"


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
    transcript_text: str
) -> str:
    """
    Extract the speaker/preacher name from sermon transcript using LLM

    Args:
        transcript_text: Full transcript text

    Returns:
        Speaker name or "Desconhecido" if not found
    """
    try:
        # Use first 10,000 characters (usually contains introduction)
        sample_text = transcript_text[:10000]

        # Generate prompt
        prompt = SPEAKER_EXTRACTION_PROMPT.format(transcript_sample=sample_text)

        # Call unified LLM client
        llm = get_llm_client()
        logger.info("Extracting speaker name with LLM...")
        llm_response = llm.generate(
            prompt=prompt,
            max_tokens=100,
            temperature=0.3
        )
        response = llm_response["text"]
        backend_used = llm_response["backend"]

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

        logger.info(f"✅ Speaker name extracted using {backend_used} backend: {speaker_name}")
        return speaker_name

    except Exception as e:
        logger.error(f"Failed to extract speaker name: {e}", exc_info=True)
        return "Desconhecido"
