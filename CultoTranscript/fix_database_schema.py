#!/usr/bin/env python3
"""
Database schema fix script
Adds missing confidence_score and audio_quality columns to transcripts table
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.common.database import engine

def fix_schema():
    """Add missing columns to transcripts table"""

    sql_commands = """
    -- Add missing columns to transcripts table
    ALTER TABLE transcripts
        ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0
            CHECK (confidence_score >= 0 AND confidence_score <= 1),
        ADD COLUMN IF NOT EXISTS audio_quality VARCHAR(10) DEFAULT 'medium'
            CHECK (audio_quality IN ('low', 'medium', 'high'));

    COMMENT ON COLUMN transcripts.confidence_score IS 'Estimated transcription accuracy (0-1 scale)';
    COMMENT ON COLUMN transcripts.audio_quality IS 'Detected audio quality level';
    """

    print("Connecting to database...")
    print(f"Database URL: {engine.url}")

    try:
        with engine.connect() as conn:
            print("\n✓ Connected successfully!")
            print("\nExecuting SQL commands to add missing columns...")

            # Execute the SQL
            conn.execute(sql_commands)
            conn.commit()

            print("✓ SQL commands executed successfully!")

            # Verify the columns were added
            print("\nVerifying columns were added...")
            result = conn.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'transcripts'
                AND column_name IN ('confidence_score', 'audio_quality')
                ORDER BY ordinal_position;
            """)

            columns = result.fetchall()

            if columns:
                print("\n✓ Verification successful! Columns found:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]} (default: {col[2]})")
            else:
                print("\n⚠ Warning: Columns not found in verification query")

            print("\n✓ Database schema fix completed successfully!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_schema()
