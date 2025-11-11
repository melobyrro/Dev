"""Robust JSON parser for LLM responses"""
import json
import re
import logging

logger = logging.getLogger(__name__)


def clean_llm_json(response: str) -> str:
    """
    Clean JSON string from LLM response

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned JSON string

    Raises:
        ValueError: If no JSON found in response
    """
    # First try to find JSON array with bracket matching
    try:
        start_idx = response.find('[')
        if start_idx == -1:
            # Try to find JSON object
            start_idx = response.find('{')
            if start_idx == -1:
                raise ValueError("No JSON found in response")
            bracket_char = '{'
            close_char = '}'
        else:
            bracket_char = '['
            close_char = ']'

        # Find matching closing bracket
        depth = 0
        end_idx = -1
        for i in range(start_idx, len(response)):
            if response[i] == bracket_char:
                depth += 1
            elif response[i] == close_char:
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break

        if end_idx == -1:
            raise ValueError("No matching closing bracket found")

        json_str = response[start_idx:end_idx + 1]
    except (ValueError, IndexError):
        raise ValueError("No valid JSON found in response")

    # Clean common JSON issues from LLMs
    json_str = json_str.replace("'", '"')  # Single to double quotes
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)  # Remove trailing commas
    json_str = json_str.strip()

    return json_str


def parse_llm_json(response: str, expected_type: type = list):
    """
    Parse JSON from LLM response with robust error handling

    Args:
        response: Raw response from LLM
        expected_type: Expected type (list or dict)

    Returns:
        Parsed data or empty instance of expected_type if parsing fails
    """
    try:
        json_str = clean_llm_json(response)
        data = json.loads(json_str)

        if not isinstance(data, expected_type):
            logger.warning(f"Expected {expected_type.__name__}, got {type(data).__name__}")
            return expected_type()  # Return empty list/dict

        return data
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse LLM JSON: {e}")
        logger.error(f"Response preview: {response[:500]}")
        return expected_type()  # Return empty list/dict
