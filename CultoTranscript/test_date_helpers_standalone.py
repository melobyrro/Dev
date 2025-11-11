#!/usr/bin/env python3
"""
Standalone test script to verify helper functions for date formatting in video titles.
This version includes the functions inline to avoid import issues.
"""

from datetime import date
import re
from typing import Optional


def remove_existing_date_prefix(title: str) -> str:
    """
    Remove existing date prefixes from title to avoid duplication.

    Handles patterns like:
    - "15/03/2024 - Title"
    - "03/15/2024 - Title"
    - "2024-03-15 - Title"
    - "15/03/24 - Title"
    """
    patterns = [
        r'^\d{1,2}/\d{1,2}/\d{4}\s*-\s*',   # dd/mm/yyyy - or mm/dd/yyyy -
        r'^\d{4}-\d{1,2}-\d{1,2}\s*-\s*',    # yyyy-mm-dd -
        r'^\d{1,2}/\d{1,2}/\d{2}\s*-\s*',    # dd/mm/yy - or mm/dd/yy -
        r'^\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*-\s*',  # "15 de março de 2024 -"
    ]

    for pattern in patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    return title.strip()


def format_title_with_date(title: str, sermon_date: Optional[date]) -> str:
    """
    Format title as 'MM/DD/YYYY - Title'.

    Args:
        title: Original video title (may already have date prefix)
        sermon_date: The sermon actual date to use for prefix

    Returns:
        Formatted title with date prefix
    """
    if not sermon_date:
        return title

    # Remove any existing date prefix to avoid duplication
    cleaned_title = remove_existing_date_prefix(title)

    # Format date as MM/DD/YYYY
    date_str = sermon_date.strftime('%m/%d/%Y')

    # Return formatted title
    return f"{date_str} - {cleaned_title}"


def test_date_removal():
    """Test the remove_existing_date_prefix function"""
    print("Testing date prefix removal...")

    test_cases = [
        ("15/03/2024 - Culto", "Culto"),
        ("03/15/2024 - Culto de Domingo", "Culto de Domingo"),
        ("2024-03-15 - Pregação Especial", "Pregação Especial"),
        ("15/03/24 - Louvor", "Louvor"),
        ("Culto de Domingo", "Culto de Domingo"),  # No prefix
        ("15 de março de 2024 - Culto", "Culto"),  # Portuguese format
    ]

    passed = 0
    failed = 0

    for input_title, expected_output in test_cases:
        result = remove_existing_date_prefix(input_title)
        if result == expected_output:
            print(f"  ✓ PASS: '{input_title}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ FAIL: '{input_title}' -> Expected: '{expected_output}', Got: '{result}'")
            failed += 1

    print(f"\nDate removal tests: {passed} passed, {failed} failed\n")
    return failed == 0


def test_date_formatting():
    """Test the format_title_with_date function"""
    print("Testing date formatting...")

    test_cases = [
        ("Culto de Domingo", date(2024, 3, 15), "03/15/2024 - Culto de Domingo"),
        ("15/03/2024 - Culto", date(2024, 3, 15), "03/15/2024 - Culto"),
        ("Pregação Especial", date(2024, 12, 25), "12/25/2024 - Pregação Especial"),
        ("01/05/2024 - Louvor", date(2024, 1, 5), "01/05/2024 - Louvor"),
        ("Culto", None, "Culto"),  # No date provided
    ]

    passed = 0
    failed = 0

    for input_title, sermon_date, expected_output in test_cases:
        result = format_title_with_date(input_title, sermon_date)
        if result == expected_output:
            print(f"  ✓ PASS: '{input_title}' + {sermon_date} -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ FAIL: '{input_title}' + {sermon_date} -> Expected: '{expected_output}', Got: '{result}'")
            failed += 1

    print(f"\nDate formatting tests: {passed} passed, {failed} failed\n")
    return failed == 0


def main():
    """Run all tests"""
    print("=" * 70)
    print("TESTING DATE HELPER FUNCTIONS")
    print("=" * 70 + "\n")

    test1_passed = test_date_removal()
    test2_passed = test_date_formatting()

    print("=" * 70)
    if test1_passed and test2_passed:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED!")
    print("=" * 70)

    return 0 if (test1_passed and test2_passed) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
