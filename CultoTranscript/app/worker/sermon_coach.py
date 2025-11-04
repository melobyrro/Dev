"""
Sermon Coach
Generates actionable improvement suggestions using Gemini AI
"""
import logging
import re
import json
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """Represents an improvement suggestion"""
    category: str  # 'exegesis', 'structure', 'communication'
    impact: str  # 'high', 'medium', 'low'
    suggestion: str
    concrete_action: str
    rewritten_example: str = None


class SermonCoach:
    """
    AI-powered sermon coaching service

    Provides actionable feedback in three categories:
    1. Exegesis: Biblical interpretation and context
    2. Structure: Flow, transitions, organization
    3. Communication: Delivery, pacing, clarity
    """

    def __init__(self, gemini_client):
        """Initialize with Gemini client"""
        self.gemini = gemini_client
        logger.info("Sermon coach initialized")

    def generate_suggestions(
        self,
        text: str,
        word_count: int,
        themes: List[Dict]
    ) -> List[Suggestion]:
        """
        Generate improvement suggestions

        Args:
            text: Sermon transcript
            word_count: Total words
            themes: Detected themes

        Returns:
            List of suggestions
        """
        # Analyze different aspects
        suggestions = []

        # Exegesis suggestions
        suggestions.extend(self._analyze_exegesis(text[:2000]))

        # Structure suggestions
        suggestions.extend(self._analyze_structure(text, word_count))

        # Communication suggestions
        suggestions.extend(self._analyze_communication(text[:2000]))

        # Sort by impact
        suggestions.sort(
            key=lambda s: {'high': 0, 'medium': 1, 'low': 2}.get(s.impact, 3)
        )

        return suggestions[:10]  # Top 10 suggestions

    def _analyze_exegesis(self, text_sample: str) -> List[Suggestion]:
        """Analyze biblical interpretation"""
        prompt = f"""
Como um coach homilético, analise este trecho de sermão e sugira melhorias na EXEGESE bíblica:

TEXTO:
{text_sample}

Forneça 2-3 sugestões focadas em:
- Fortalecer o contexto bíblico
- Adicionar referências cruzadas
- Melhorar a interpretação textual

JSON format:
[{{
  "impacto": "high|medium|low",
  "sugestao": "Descrição da sugestão",
  "acao": "Ação específica que o pastor pode tomar",
  "exemplo": "Exemplo de como reescrever um segmento (opcional)"
}}]

Retorne APENAS o JSON.
"""
        return self._parse_suggestions(prompt, 'exegesis')

    def _analyze_structure(self, text: str, word_count: int) -> List[Suggestion]:
        """Analyze sermon structure"""
        # Extract introduction and conclusion
        intro = ' '.join(text.split()[:200])
        words = text.split()
        concl = ' '.join(words[-200:]) if len(words) > 200 else ''

        prompt = f"""
Analise a ESTRUTURA deste sermão:

INTRODUÇÃO: {intro}
CONCLUSÃO: {concl}
TOTAL DE PALAVRAS: {word_count}

Sugira melhorias em:
- Fluxo e transições
- Chamado à ação
- Coerência estrutural

JSON format:
[{{
  "impacto": "high|medium|low",
  "sugestao": "Descrição",
  "acao": "Ação concreta",
  "exemplo": "Exemplo (opcional)"
}}]

Retorne APENAS JSON com 1-2 sugestões.
"""
        return self._parse_suggestions(prompt, 'structure')

    def _analyze_communication(self, text_sample: str) -> List[Suggestion]:
        """Analyze communication style"""
        # Count repeated words
        words = text_sample.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 4:  # Only significant words
                word_freq[word] = word_freq.get(word, 0) + 1

        most_repeated = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        prompt = f"""
Analise a COMUNICAÇÃO neste sermão:

TRECHO: {text_sample[:1000]}

Palavras mais repetidas: {', '.join(f'{w}({c})' for w, c in most_repeated)}

Sugira melhorias em:
- Ritmo e pausas
- Variedade vocal
- Clareza e concisão
- Evitar repetições excessivas

JSON format:
[{{
  "impacto": "high|medium|low",
  "sugestao": "Descrição",
  "acao": "Ação concreta",
  "exemplo": "Exemplo de reescrita"
}}]

Retorne APENAS JSON com 1-2 sugestões.
"""
        return self._parse_suggestions(prompt, 'communication')

    def _parse_suggestions(self, prompt: str, category: str) -> List[Suggestion]:
        """Parse Gemini response into Suggestion objects"""
        try:
            response = self.gemini.generate_content(prompt)

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []

            items = json.loads(json_match.group())

            suggestions = []
            for item in items:
                suggestions.append(Suggestion(
                    category=category,
                    impact=item.get('impacto', 'medium'),
                    suggestion=item['sugestao'][:500],
                    concrete_action=item['acao'][:500],
                    rewritten_example=item.get('exemplo', '')[:1000]
                ))

            return suggestions

        except Exception as e:
            logger.error(f"Error generating {category} suggestions: {e}")
            return []
