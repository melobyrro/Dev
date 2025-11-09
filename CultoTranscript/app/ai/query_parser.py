"""
Query parser for extracting dates from Brazilian Portuguese natural language queries.
Used by the chatbot to filter videos by date when users ask about specific sermons.

Phase 2: Advanced Date Handling
- Date ranges (last month, last week, month ranges)
- Smart "last" queries (último sermão, último domingo)
- Enhanced relative dates (anteontem, semana retrasada)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from dateutil.relativedelta import relativedelta
import pytz

logger = logging.getLogger(__name__)

# Brazil timezone for proper date handling
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')


@dataclass
class DateExtractionResult:
    """Details about the extracted date (legacy, single date)."""

    date: datetime
    explicit_year: bool
    source: str
    ambiguous: bool = False
    alternatives: Optional[List[datetime]] = None
    raw_text: Optional[str] = None


@dataclass
class DateRangeResult:
    """
    Enhanced date extraction result supporting ranges and special queries.

    Supports:
    - Date ranges (last month, last week, specific month ranges)
    - Smart queries (último sermão, último domingo)
    - Single dates (backward compatible)
    """
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    is_range: bool
    range_type: Optional[str] = None  # 'month', 'week', 'year', 'custom', 'last_n_days'
    query_type: Optional[str] = None  # 'last_sermon', 'last_sunday', 'last_month', etc.
    original_text: str = ""
    explicit_year: bool = False
    ambiguous: bool = False
    alternatives: Optional[List[tuple]] = None  # List of (start, end) tuples

    def to_legacy_result(self) -> Optional[DateExtractionResult]:
        """Convert to legacy DateExtractionResult for backward compatibility."""
        if not self.start_date:
            return None
        return DateExtractionResult(
            date=self.start_date,
            explicit_year=self.explicit_year,
            source=self.range_type or 'unknown',
            ambiguous=self.ambiguous,
            alternatives=[alt[0] for alt in (self.alternatives or [])],
            raw_text=self.original_text
        )

# Brazilian Portuguese month names
MONTH_NAMES = {
    'janeiro': 1, 'jan': 1,
    'fevereiro': 2, 'fev': 2,
    'março': 3, 'mar': 3,
    'abril': 4, 'abr': 4,
    'maio': 5, 'mai': 5,
    'junho': 6, 'jun': 6,
    'julho': 7, 'jul': 7,
    'agosto': 8, 'ago': 8,
    'setembro': 9, 'set': 9,
    'outubro': 10, 'out': 10,
    'novembro': 11, 'nov': 11,
    'dezembro': 12, 'dez': 12
}

# Relative date words - extended for Phase 2
RELATIVE_DATES = {
    'ontem': lambda: datetime.now() - timedelta(days=1),
    'hoje': lambda: datetime.now(),
    'anteontem': lambda: datetime.now() - timedelta(days=2),
}


def _get_brazil_now() -> datetime:
    """Get current datetime in Brazil timezone."""
    return datetime.now(BRAZIL_TZ)


def _get_last_sunday(reference_date: Optional[datetime] = None) -> datetime:
    """
    Get the most recent Sunday before the reference date.

    Args:
        reference_date: Reference date (defaults to now)

    Returns:
        datetime of last Sunday
    """
    if reference_date is None:
        reference_date = _get_brazil_now()

    days_since_sunday = (reference_date.weekday() + 1) % 7
    if days_since_sunday == 0:
        days_since_sunday = 7  # If today is Sunday, get previous Sunday

    return reference_date - timedelta(days=days_since_sunday)


def _get_next_sunday(reference_date: Optional[datetime] = None) -> datetime:
    """
    Get the next Sunday after the reference date.

    Args:
        reference_date: Reference date (defaults to now)

    Returns:
        datetime of next Sunday
    """
    if reference_date is None:
        reference_date = _get_brazil_now()

    days_until_sunday = (6 - reference_date.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7  # If today is Sunday, get next Sunday

    return reference_date + timedelta(days=days_until_sunday)


def _get_month_range(month: int, year: Optional[int] = None) -> tuple:
    """
    Get first and last day of a specific month.

    Args:
        month: Month number (1-12)
        year: Year (defaults to current year)

    Returns:
        Tuple of (start_date, end_date)
    """
    if year is None:
        year = _get_brazil_now().year

    start_date = datetime(year, month, 1)

    # Last day of month
    if month == 12:
        end_date = datetime(year, 12, 31)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    return start_date, end_date


def _parse_month_range(query_lower: str) -> Optional[tuple]:
    """
    Parse month range queries like "março a maio" or "de março a maio".

    Returns:
        Tuple of (start_month, end_month) or None
    """
    # Pattern: "março a maio" or "de março a maio"
    month_range_pattern = r'(?:de\s+)?(\w+)\s+a\s+(\w+)'
    match = re.search(month_range_pattern, query_lower)

    if not match:
        return None

    start_month_name, end_month_name = match.groups()

    # Look up month numbers
    start_month = MONTH_NAMES.get(start_month_name.lower())
    end_month = MONTH_NAMES.get(end_month_name.lower())

    # Try partial match if exact match failed
    if not start_month:
        for m_name, m_num in MONTH_NAMES.items():
            if m_name.startswith(start_month_name.lower()):
                start_month = m_num
                break

    if not end_month:
        for m_name, m_num in MONTH_NAMES.items():
            if m_name.startswith(end_month_name.lower()):
                end_month = m_num
                break

    if start_month and end_month:
        return start_month, end_month

    return None


def _normalize_year(year_str: str) -> int:
    """Normalize year strings like '24' into 2024."""
    if len(year_str) == 2:
        return int('20' + year_str)
    return int(year_str)


def extract_date_range(query: str) -> Optional[DateRangeResult]:
    """
    Extract date range from Brazilian Portuguese query with advanced handling.

    Phase 2 Features:
    - Date ranges: "último mês", "última semana", "março a maio"
    - Smart queries: "último sermão", "último domingo", "penúltimo sermão"
    - Enhanced relative: "anteontem", "semana retrasada", "mês passado"

    Returns:
        DateRangeResult with start/end dates and metadata, or None if no date found
    """
    if not query:
        return None

    query_lower = query.lower()
    now = _get_brazil_now()
    current_year = now.year

    try:
        # =================================================================
        # PRIORITY 1: Smart "Last" Queries (database-dependent)
        # =================================================================

        # "último sermão" or "sermão mais recente"
        if re.search(r'\b(último|ultima|mais\s+recente)\s+(sermão|pregação|mensagem|culto)', query_lower):
            logger.info("Detected 'último sermão' query - requires database lookup")
            return DateRangeResult(
                start_date=None,
                end_date=None,
                is_range=False,
                range_type=None,
                query_type='last_sermon',
                original_text=query,
                explicit_year=True
            )

        # "penúltimo sermão"
        if re.search(r'\bpenúltim[oa]\s+(sermão|pregação|mensagem|culto)', query_lower):
            logger.info("Detected 'penúltimo sermão' query - requires database lookup")
            return DateRangeResult(
                start_date=None,
                end_date=None,
                is_range=False,
                range_type=None,
                query_type='second_last_sermon',
                original_text=query,
                explicit_year=True
            )

        # "último domingo" or "domingo passado"
        if re.search(r'\b(último|ultimo)\s+domingo', query_lower) or 'domingo passado' in query_lower:
            last_sunday = _get_last_sunday(now)
            logger.info(f"Detected 'último domingo': {last_sunday.date()}")
            return DateRangeResult(
                start_date=last_sunday,
                end_date=last_sunday,
                is_range=False,
                range_type='specific_day',
                query_type='last_sunday',
                original_text=query,
                explicit_year=True
            )

        # "próximo domingo"
        if re.search(r'\bpróxim[oa]\s+domingo', query_lower):
            next_sunday = _get_next_sunday(now)
            logger.info(f"Detected 'próximo domingo': {next_sunday.date()}")
            return DateRangeResult(
                start_date=next_sunday,
                end_date=next_sunday,
                is_range=False,
                range_type='specific_day',
                query_type='next_sunday',
                original_text=query,
                explicit_year=True
            )

        # =================================================================
        # PRIORITY 2: Date Ranges
        # =================================================================

        # "último mês" or "mês passado" - previous calendar month
        if 'último mês' in query_lower or 'ultimo mes' in query_lower or 'mês passado' in query_lower or 'mes passado' in query_lower:
            previous_month_date = now - relativedelta(months=1)
            start_date, end_date = _get_month_range(previous_month_date.month, previous_month_date.year)
            logger.info(f"Detected 'mês passado': {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='month',
                query_type='last_month',
                original_text=query,
                explicit_year=True
            )

        # "este mês" or "neste mês" - current calendar month
        if re.search(r'\b(este|neste)\s+mês', query_lower):
            start_date, end_date = _get_month_range(now.month, now.year)
            # Don't include future dates
            if end_date > now:
                end_date = now
            logger.info(f"Detected 'este mês': {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='month',
                query_type='current_month',
                original_text=query,
                explicit_year=True
            )

        # "última semana" or "semana passada" - last 7 days
        if 'última semana' in query_lower or 'ultima semana' in query_lower or 'semana passada' in query_lower:
            end_date = now
            start_date = now - timedelta(days=7)
            logger.info(f"Detected 'última semana': {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='week',
                query_type='last_week',
                original_text=query,
                explicit_year=True
            )

        # "semana retrasada" - two weeks ago
        if 'semana retrasada' in query_lower:
            end_date = now - timedelta(days=7)
            start_date = now - timedelta(days=14)
            logger.info(f"Detected 'semana retrasada': {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='week',
                query_type='two_weeks_ago',
                original_text=query,
                explicit_year=True
            )

        # "deste ano" or "neste ano" - current year
        if re.search(r'\b(deste|neste)\s+ano', query_lower):
            start_date = datetime(now.year, 1, 1)
            end_date = now  # Don't include future dates
            logger.info(f"Detected 'deste ano': {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='year',
                query_type='current_year',
                original_text=query,
                explicit_year=True
            )

        # Month range: "março a maio" or "de março a maio"
        month_range = _parse_month_range(query_lower)
        if month_range:
            start_month, end_month = month_range
            # Determine year - check if query mentions a year
            year_match = re.search(r'\b(20\d{2}|\d{2})\b', query)
            if year_match:
                year = _normalize_year(year_match.group(1))
                explicit_year = True
            else:
                year = current_year
                explicit_year = False

            start_date, _ = _get_month_range(start_month, year)
            _, end_date = _get_month_range(end_month, year)

            logger.info(f"Detected month range: {start_date.date()} to {end_date.date()}")
            return DateRangeResult(
                start_date=start_date,
                end_date=end_date,
                is_range=True,
                range_type='custom',
                query_type='month_range',
                original_text=query,
                explicit_year=explicit_year
            )

        # Single month: "janeiro", "de janeiro", "em janeiro"
        single_month_pattern = r'\b(?:de|em|durante)?\s*(\w+)\b'
        for month_name, month_num in MONTH_NAMES.items():
            if month_name in query_lower:
                # Make sure it's not part of another word
                if re.search(r'\b' + month_name + r'\b', query_lower):
                    # Check if year is mentioned
                    year_match = re.search(r'\b(de\s+)?(20\d{2}|\d{2})\b', query)
                    if year_match:
                        year = _normalize_year(year_match.group(2) if year_match.group(1) else year_match.group(1))
                        explicit_year = True
                    else:
                        # Determine if we should use current or previous year
                        # If the month hasn't occurred yet this year, use previous year
                        if month_num > now.month:
                            year = current_year - 1
                        else:
                            year = current_year
                        explicit_year = False

                    start_date, end_date = _get_month_range(month_num, year)
                    logger.info(f"Detected single month '{month_name}': {start_date.date()} to {end_date.date()}")
                    return DateRangeResult(
                        start_date=start_date,
                        end_date=end_date,
                        is_range=True,
                        range_type='month',
                        query_type='single_month',
                        original_text=query,
                        explicit_year=explicit_year
                    )

        # =================================================================
        # PRIORITY 3: Enhanced Relative Dates (backward compatible)
        # =================================================================

        # Check enhanced relative dates
        if 'anteontem' in query_lower:
            date = now - timedelta(days=2)
            logger.info(f"Detected 'anteontem': {date.date()}")
            return DateRangeResult(
                start_date=date,
                end_date=date,
                is_range=False,
                range_type='relative',
                query_type='day_before_yesterday',
                original_text=query,
                explicit_year=True
            )

        if 'ontem' in query_lower:
            date = now - timedelta(days=1)
            logger.info(f"Detected 'ontem': {date.date()}")
            return DateRangeResult(
                start_date=date,
                end_date=date,
                is_range=False,
                range_type='relative',
                query_type='yesterday',
                original_text=query,
                explicit_year=True
            )

        if 'hoje' in query_lower:
            date = now
            logger.info(f"Detected 'hoje': {date.date()}")
            return DateRangeResult(
                start_date=date,
                end_date=date,
                is_range=False,
                range_type='relative',
                query_type='today',
                original_text=query,
                explicit_year=True
            )

        # =================================================================
        # PRIORITY 4: Explicit dates (DD/MM/YYYY, etc.) - use legacy parser
        # =================================================================

        # Fallback to legacy extraction for explicit dates
        legacy_result = extract_date_details(query)
        if legacy_result:
            logger.info(f"Using legacy date extraction: {legacy_result.date.date()}")
            return DateRangeResult(
                start_date=legacy_result.date,
                end_date=legacy_result.date,
                is_range=False,
                range_type=legacy_result.source,
                query_type='explicit_date',
                original_text=legacy_result.raw_text or query,
                explicit_year=legacy_result.explicit_year,
                ambiguous=legacy_result.ambiguous,
                alternatives=[(alt, alt) for alt in (legacy_result.alternatives or [])]
            )

        # No date found
        logger.debug(f"No date range found in query: {query}")
        return None

    except Exception as e:
        logger.error(f"Error extracting date range from query: {e}", exc_info=True)
        return None


def extract_date_details(query: str) -> Optional[DateExtractionResult]:
    """
    Extract date details from a Brazilian Portuguese query.
    Returns metadata so callers can understand whether the year was explicit.
    """
    if not query:
        return None

    query_lower = query.lower()
    current_year = datetime.now().year

    try:
        # Check for relative dates first
        for word, date_func in RELATIVE_DATES.items():
            if word in query_lower:
                extracted = date_func()
                logger.info(f"Extracted relative date '{word}': {extracted.date()}")
                return DateExtractionResult(
                    date=extracted,
                    explicit_year=True,
                    source='relative',
                    raw_text=word
                )

        # Pattern 1: DD/MM/YYYY or DD/MM
        date_pattern = r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?\b'
        match = re.search(date_pattern, query)
        if match:
            day_str, month_str, year = match.groups()
            day = int(day_str)
            month = int(month_str)
            explicit_year = bool(year)
            if year:
                if len(year) == 2:
                    year = '20' + year
            else:
                year = str(current_year)

            ambiguous = False
            alternatives: List[datetime] = []

            # Ambiguous when no year provided and both numbers <= 12 but describe different days
            if not explicit_year and day <= 12 and month <= 12 and day != month:
                try:
                    alt_date = datetime(int(year), day, month)
                    ambiguous = True
                    alternatives.append(alt_date)
                except ValueError:
                    # Ignore invalid swapped date
                    pass

            try:
                extracted = datetime(int(year), month, day)
                logger.info(f"Extracted date from pattern DD/MM/YYYY: {extracted.date()}")
                return DateExtractionResult(
                    date=extracted,
                    explicit_year=explicit_year,
                    source='numeric',
                    ambiguous=ambiguous,
                    alternatives=alternatives or None,
                    raw_text=match.group(0)
                )
            except ValueError:
                logger.warning(f"Invalid date values: day={day}, month={month}, year={year}")

        # Pattern 2: "dia X de MÊS" or "dia X" (with optional year)
        day_month_pattern = r'\bdia\s+(\d{1,2})(?:\s+de\s+(\w+)(?:\s+de\s+(\d{2,4}))?)?'
        match = re.search(day_month_pattern, query_lower)
        if match:
            day, month_name, year_str = match.groups()

            if month_name:
                # Match month name
                month = MONTH_NAMES.get(month_name.lower())
                if not month:
                    # Try partial match
                    for m_name, m_num in MONTH_NAMES.items():
                        if m_name.startswith(month_name.lower()):
                            month = m_num
                            break
            else:
                # If no month specified, use current month
                month = datetime.now().month

            if month:
                try:
                    if year_str:
                        year = _normalize_year(year_str)
                        explicit_year = True
                    else:
                        year = current_year
                        explicit_year = False
                    extracted = datetime(year, month, int(day))
                    logger.info(f"Extracted date from 'dia X de MÊS': {extracted.date()}")
                    source = 'day_month_name' if month_name else 'day_only'
                    return DateExtractionResult(
                        date=extracted,
                        explicit_year=explicit_year,
                        source=source,
                        raw_text=match.group(0)
                    )
                except ValueError:
                    logger.warning(f"Invalid date values: day={day}, month={month}")

        # Pattern 3: "X de MÊS" (without "dia")
        pattern_month = r'\b(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{2,4}))?'
        match = re.search(pattern_month, query_lower)
        if match:
            day, month_name, year_str = match.groups()
            month = MONTH_NAMES.get(month_name.lower())

            if not month:
                # Try partial match
                for m_name, m_num in MONTH_NAMES.items():
                    if m_name.startswith(month_name.lower()):
                        month = m_num
                        break

            if month:
                try:
                    if year_str:
                        year = _normalize_year(year_str)
                        explicit_year = True
                    else:
                        year = current_year
                        explicit_year = False
                    extracted = datetime(year, month, int(day))
                    logger.info(f"Extracted date from 'X de MÊS': {extracted.date()}")
                    return DateExtractionResult(
                        date=extracted,
                        explicit_year=explicit_year,
                        source='month_day_name',
                        raw_text=match.group(0)
                    )
                except ValueError:
                    logger.warning(f"Invalid date values: day={day}, month={month}")

        # Pattern 4: Check for relative week/month references
        if 'semana passada' in query_lower:
            # Get last Sunday
            today = datetime.now()
            days_since_sunday = (today.weekday() + 1) % 7
            last_sunday = today - timedelta(days=days_since_sunday + 7)
            logger.info(f"Extracted 'semana passada' as last Sunday: {last_sunday.date()}")
            return DateExtractionResult(
                date=last_sunday,
                explicit_year=True,
                source='relative_week',
                raw_text='semana passada'
            )

        if 'domingo passado' in query_lower:
            # Get last Sunday
            today = datetime.now()
            days_since_sunday = (today.weekday() + 1) % 7
            if days_since_sunday == 0:
                days_since_sunday = 7  # If today is Sunday, get previous Sunday
            last_sunday = today - timedelta(days=days_since_sunday)
            logger.info(f"Extracted 'domingo passado': {last_sunday.date()}")
            return DateExtractionResult(
                date=last_sunday,
                explicit_year=True,
                source='relative_week',
                raw_text='domingo passado'
            )

        if 'mês passado' in query_lower:
            # Get first day of last month
            today = datetime.now()
            last_month = today - relativedelta(months=1)
            first_day = last_month.replace(day=1)
            logger.info(f"Extracted 'mês passado': {first_day.date()}")
            return DateExtractionResult(
                date=first_day,
                explicit_year=True,
                source='relative_month',
                raw_text='mês passado'
            )

        # If no patterns matched, return None
        logger.debug(f"No date found in query: {query}")
        return None

    except Exception as e:
        logger.error(f"Error extracting date from query: {e}")
        return None


def extract_date_from_query(query: str) -> Optional[datetime]:
    """Backward-compatible helper that returns only the datetime."""
    result = extract_date_details(query)
    return result.date if result else None


def format_date_for_display(date: datetime) -> str:
    """
    Format date for display in Brazilian format.

    Args:
        date: datetime object

    Returns:
        Formatted date string (DD/MM/YYYY)
    """
    return date.strftime('%d/%m/%Y')


# Test the module if run directly
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("PHASE 2: ADVANCED DATE HANDLING TESTS")
    print("=" * 80)

    # Test cases for Phase 2
    test_queries = [
        # Smart "last" queries
        "qual foi o último sermão?",
        "penúltimo sermão sobre fé",
        "o que foi pregado no último domingo?",
        "sermão do domingo passado",
        "próximo domingo tem culto?",

        # Date ranges
        "sermões do último mês",
        "pregações da última semana",
        "mensagens deste ano",
        "sermões de março a maio",
        "cultos de janeiro",
        "pregações do mês passado",
        "sermões deste mês",

        # Enhanced relative dates
        "sermão de anteontem",
        "pregação da semana retrasada",
        "culto de ontem",
        "mensagem de hoje",

        # Legacy support (explicit dates)
        "qual foi a mensagem do dia 10/05?",
        "o que foi pregado dia 15 de março?",
        "sermão de 7 de outubro de 2024",
        "mensagem do dia 31/12/2024",

        # No date
        "uma mensagem qualquer sem data",
        "qual o tema principal?"
    ]

    for query in test_queries:
        result = extract_date_range(query)
        if result:
            if result.is_range:
                start = result.start_date.strftime('%d/%m/%Y') if result.start_date else 'N/A'
                end = result.end_date.strftime('%d/%m/%Y') if result.end_date else 'N/A'
                print(
                    f"\n✓ Query: '{query}'\n"
                    f"  → Range: {start} to {end}\n"
                    f"  → Type: {result.query_type} ({result.range_type})"
                )
            elif result.query_type in ['last_sermon', 'second_last_sermon']:
                print(
                    f"\n✓ Query: '{query}'\n"
                    f"  → Database lookup required\n"
                    f"  → Type: {result.query_type}"
                )
            else:
                date_str = result.start_date.strftime('%d/%m/%Y') if result.start_date else 'N/A'
                print(
                    f"\n✓ Query: '{query}'\n"
                    f"  → Date: {date_str}\n"
                    f"  → Type: {result.query_type} ({result.range_type})"
                )
        else:
            print(f"\n✗ Query: '{query}' -> No date found")

    print("\n" + "=" * 80)
