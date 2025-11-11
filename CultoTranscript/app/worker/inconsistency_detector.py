"""
Sermon Inconsistency Detector
Identifies logical, biblical, factual, and language errors using unified LLM client (Gemini or Ollama)
"""
import logging
import re
import json
from typing import List, Dict
from dataclasses import dataclass
from app.ai.llm_client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class Inconsistency:
    """Represents a detected inconsistency"""
    inconsistency_type: str  # 'logical', 'biblical', 'factual', 'language'
    timestamp: int  # Seconds
    evidence: str  # The problematic text
    explanation: str  # Why it's inconsistent
    severity: str  # 'low', 'medium', 'high'


class InconsistencyDetector:
    """
    Detects potential inconsistencies in sermons using Gemini AI

    Categories:
    - Logical: Contradictions, non-sequiturs, hasty generalizations
    - Biblical: Incorrect citations, out-of-context verses
    - Factual: Wrong dates, names, numbers
    - Language: Ambiguous terms, false cognates
    """

    def __init__(self):
        """Initialize detector with unified LLM client"""
        self.llm = get_llm_client()
        logger.info("Inconsistency detector initialized with unified LLM client")

    def detect_inconsistencies(
        self,
        text: str,
        biblical_references: List[Dict]
    ) -> List[Inconsistency]:
        """
        Detect inconsistencies in sermon text

        Args:
            text: Full transcript
            biblical_references: List of detected biblical references

        Returns:
            List of detected inconsistencies
        """
        all_inconsistencies = []

        # Split into chunks for analysis
        chunks = self._split_text(text, 1500)

        for i, (chunk_text, start_pos) in enumerate(chunks):
            logger.debug(f"Analyzing chunk {i+1}/{len(chunks)} for inconsistencies")

            chunk_inconsistencies = self._analyze_chunk(chunk_text, start_pos)
            all_inconsistencies.extend(chunk_inconsistencies)

        # Deduplicate and sort by severity
        all_inconsistencies = self._deduplicate(all_inconsistencies)
        all_inconsistencies.sort(key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x.severity, 3))

        return all_inconsistencies[:20]  # Return top 20

    def _analyze_chunk(self, text: str, start_pos: int) -> List[Inconsistency]:
        """Analyze a text chunk for inconsistencies"""
        prompt = f"""
Analise o seguinte trecho de sermão e identifique possíveis inconsistências ou erros.

Categorias para verificar:
1. LÓGICAS: Contradições, não-sequiturs, generalizações apressadas
2. BÍBLICAS: Citações incorretas, versículos fora de contexto
3. FÁTICAS: Datas, nomes ou números incorretos
4. LINGUÍSTICAS: Termos ambíguos, falsos cognatos

TEXTO:
{text[:2000]}

Retorne JSON com esta estrutura:
[
  {{
    "tipo": "logical|biblical|factual|language",
    "evidencia": "Texto problemático (máx 200 chars)",
    "explicacao": "Por que é inconsistente (máx 300 chars)",
    "gravidade": "low|medium|high"
  }}
]

Retorne APENAS o JSON. Se nenhuma inconsistência significativa for encontrada, retorne [].
"""

        try:
            llm_response = self.llm.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.4
            )
            response = llm_response["text"]
            backend_used = llm_response["backend"]

            # Extract JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []

            items = json.loads(json_match.group())

            inconsistencies = []
            for item in items:
                # Estimate timestamp (words before / 2.5 words per second)
                words_before = len(text[:text.find(item['evidencia'][:50])].split())
                timestamp = int(start_pos / 2.5) + int(words_before / 2.5)

                inconsistencies.append(Inconsistency(
                    inconsistency_type=item['tipo'],
                    timestamp=timestamp,
                    evidence=item['evidencia'][:200],
                    explanation=item['explicacao'][:300],
                    severity=item['gravidade']
                ))

            logger.info(f"✅ Inconsistency analysis completed using {backend_used} backend")
            return inconsistencies

        except Exception as e:
            logger.error(f"Error detecting inconsistencies: {e}")
            return []

    def _split_text(self, text: str, chunk_size: int) -> List[tuple]:
        """Split text into chunks with overlap"""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            chunks.append((chunk_text, start))
            start += int(chunk_size * 0.8)  # 20% overlap
        return chunks

    def _deduplicate(self, inconsistencies: List[Inconsistency]) -> List[Inconsistency]:
        """Remove duplicate inconsistencies"""
        seen = set()
        unique = []
        for inc in inconsistencies:
            # Use evidence as deduplication key
            key = inc.evidence[:100]
            if key not in seen:
                seen.add(key)
                unique.append(inc)
        return unique
