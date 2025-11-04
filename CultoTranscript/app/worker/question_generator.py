"""
Discussion Question Generator
Creates small group discussion questions from sermons
"""
import logging
import re
import json
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiscussionQuestionData:
    """Represents a discussion question"""
    question: str
    linked_passage_osis: str = None
    question_order: int = 0


class QuestionGenerator:
    """Generates discussion questions for small groups"""

    def __init__(self, gemini_client):
        """Initialize with Gemini client"""
        self.gemini = gemini_client
        logger.info("Question generator initialized")

    def generate_questions(
        self,
        text: str,
        themes: List[str],
        biblical_passages: List[Dict],
        count: int = 6
    ) -> List[DiscussionQuestionData]:
        """Generate discussion questions"""
        # Extract key passages for reference
        passages_text = ', '.join([p.get('osis_ref', '') for p in biblical_passages[:5]])

        prompt = f"""
Gere {count} perguntas de discussão para pequenos grupos baseadas neste sermão:

TEMAS: {', '.join(themes[:5])}
PASSAGENS-CHAVE: {passages_text}

SERMÃO:
{text[:3000]}

Crie perguntas que:
- Estimulem reflexão pessoal
- Promovam compartilhamento de experiências
- Conectem o sermão com a vida prática
- Sejam adequadas para grupos pequenos

JSON format:
[{{
  "pergunta": "Texto da pergunta",
  "passagem_osis": "Passagem bíblica relacionada (opcional)"
}}]

Retorne APENAS o JSON com {count} perguntas variadas.
"""

        try:
            response = self.gemini.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []

            items = json.loads(json_match.group())

            questions = []
            for i, item in enumerate(items, 1):
                questions.append(DiscussionQuestionData(
                    question=item['pergunta'],
                    linked_passage_osis=item.get('passagem_osis'),
                    question_order=i
                ))

            return questions

        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            return []
