#!/usr/bin/env python3
"""
Simple database fix script using only psycopg2
No dependencies on the app module
"""
import sys

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 not installed")
    print("\nPlease install it with:")
    print("  pip3 install psycopg2-binary")
    print("\nOr run the migration using the provided shell script:")
    print("  ./RUN_THIS_MIGRATION.sh")
    sys.exit(1)

# Database connection parameters
DB_PARAMS = {
    'host': 'localhost',
    'database': 'culto',
    'user': 'culto_admin',
    'password': 'changeme',
    'port': 5432
}

SQL = """
ALTER TABLE transcripts
    ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    ADD COLUMN IF NOT EXISTS audio_quality VARCHAR(10) DEFAULT 'medium'
        CHECK (audio_quality IN ('low', 'medium', 'high'));

COMMENT ON COLUMN transcripts.confidence_score IS 'Estimated transcription accuracy (0-1 scale)';
COMMENT ON COLUMN transcripts.audio_quality IS 'Detected audio quality level';
"""

VERIFY_SQL = """
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'transcripts'
AND column_name IN ('confidence_score', 'audio_quality')
ORDER BY ordinal_position;
"""

def main():
    print("🔧 CultoTranscript - Database Schema Fix")
    print("=" * 50)

    try:
        print(f"\n📡 Connecting to database at {DB_PARAMS['host']}:{DB_PARAMS['port']}...")
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = True
        cursor = conn.cursor()

        print("✓ Connected successfully!\n")

        print("📝 Executing migration...")
        cursor.execute(SQL)
        print("✓ Migration executed!\n")

        print("🔍 Verifying columns were added...")
        cursor.execute(VERIFY_SQL)
        columns = cursor.fetchall()

        if columns:
            print("✓ Verification successful! Columns found:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} (default: {col[2]})")
        else:
            print("⚠ Warning: Columns not found in verification")

        cursor.close()
        conn.close()

        print("\n✅ Database schema fix completed successfully!")
        print("\nYou can now restart your worker to process videos.")

    except psycopg2.OperationalError as e:
        print(f"❌ Connection error: {e}")
        print("\nPossible issues:")
        print("  1. Database is not running")
        print("  2. Database is running in Docker (use ./RUN_THIS_MIGRATION.sh instead)")
        print("  3. Wrong credentials")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
