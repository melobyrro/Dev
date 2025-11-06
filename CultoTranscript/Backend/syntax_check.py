#!/usr/bin/env python3
"""
Backend Phase 1 Syntax Check

Validates Python syntax for all Backend files without importing dependencies.
"""
import py_compile
import sys
from pathlib import Path


def check_syntax(file_path):
    """Check Python syntax for a file"""
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)


def main():
    """Check all Python files in Backend/"""
    print("=" * 80)
    print("Backend Phase 1 - Syntax Validation")
    print("=" * 80)
    print()

    backend_dir = Path(__file__).parent
    python_files = list(backend_dir.rglob("*.py"))

    errors = []
    success_count = 0

    for py_file in sorted(python_files):
        relative_path = py_file.relative_to(backend_dir.parent)
        success, error = check_syntax(py_file)

        if success:
            print(f"✓ {relative_path}")
            success_count += 1
        else:
            print(f"✗ {relative_path}")
            print(f"  ERROR: {error}")
            errors.append((relative_path, error))

    print()
    print("=" * 80)
    print(f"Results: {success_count}/{len(python_files)} files passed")
    print("=" * 80)

    if errors:
        print("\nSyntax errors found:")
        for file_path, error in errors:
            print(f"  ✗ {file_path}: {error}")
        return 1
    else:
        print("\n✓ All Python files have valid syntax!")
        print("\nNote: Full validation requires dependencies (run in Docker):")
        print("  docker-compose exec culto_web python Backend/validate.py")
        return 0


if __name__ == "__main__":
    sys.exit(main())
