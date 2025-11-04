#!/bin/bash
#
# Quick migration script to fix missing database columns
# Run this to add confidence_score and audio_quality to transcripts table
#

set -e

echo "🔧 CultoTranscript - Database Schema Fix"
echo "========================================="
echo ""
echo "This script will add missing columns to the transcripts table:"
echo "  - confidence_score (FLOAT)"
echo "  - audio_quality (VARCHAR)"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker command not found"
    echo ""
    echo "Please run the migration manually:"
    echo "  psql -h localhost -U culto_admin -d culto -f migrations/004_fix_missing_transcript_columns.sql"
    exit 1
fi

# Check if container is running
if ! docker ps | grep -q culto_db; then
    echo "❌ Database container 'culto_db' is not running"
    echo ""
    echo "Please start the database first:"
    echo "  cd docker && docker-compose up -d db"
    exit 1
fi

echo "✓ Database container is running"
echo ""
echo "Executing migration..."
echo ""

# Run the migration
docker exec -i culto_db psql -U culto_admin -d culto < migrations/004_fix_missing_transcript_columns.sql

echo ""
echo "✅ Migration completed!"
echo ""
echo "You can now restart your worker to process videos without errors."
