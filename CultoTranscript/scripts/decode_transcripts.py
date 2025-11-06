"""
Migration script to decode HTML entities in existing transcripts
Run once after deploying the yt_dlp_service fix

Usage:
    python scripts/decode_transcripts.py
"""
import sys
import os
import html
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.common.database import get_db
from app.common.models import Transcript

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def decode_transcripts():
    """Decode HTML entities in all transcript records"""
    logger.info("=" * 70)
    logger.info("TRANSCRIPT HTML ENTITY DECODER")
    logger.info("=" * 70)

    try:
        with get_db() as db:
            # Get all transcripts
            transcripts = db.query(Transcript).all()
            total = len(transcripts)
            updated_count = 0
            unchanged_count = 0

            logger.info(f"\nProcessing {total} transcripts...")
            logger.info("-" * 70)

            for idx, transcript in enumerate(transcripts, 1):
                # Check if transcript contains HTML entities
                has_entities = any(
                    entity in transcript.text
                    for entity in ['&gt;', '&lt;', '&amp;', '&quot;', '&#']
                )

                if has_entities:
                    original_text = transcript.text
                    decoded_text = html.unescape(original_text)

                    # Only update if text actually changed
                    if decoded_text != original_text:
                        transcript.text = decoded_text
                        transcript.char_count = len(decoded_text)
                        transcript.word_count = len(decoded_text.split())
                        updated_count += 1

                        logger.info(
                            f"[{idx}/{total}] ✓ Updated transcript {transcript.id} "
                            f"(video {transcript.video_id}, source: {transcript.source})"
                        )

                        # Show sample of what changed
                        if '&gt;&gt;' in original_text:
                            logger.info(f"  Sample fix: '&gt;&gt;' → '>>'")
                        if '&lt;&lt;' in original_text:
                            logger.info(f"  Sample fix: '&lt;&lt;' → '<<'")

                        # Commit every 20 records
                        if updated_count % 20 == 0:
                            db.commit()
                            logger.info(f"  💾 Committed batch ({updated_count} updates so far)")
                    else:
                        unchanged_count += 1
                else:
                    unchanged_count += 1

            # Final commit
            db.commit()

            logger.info("-" * 70)
            logger.info("✅ MIGRATION COMPLETE!")
            logger.info(f"   Total transcripts processed: {total}")
            logger.info(f"   Updated (had HTML entities): {updated_count}")
            logger.info(f"   Unchanged (already clean): {unchanged_count}")
            logger.info("=" * 70)

            return updated_count

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


def verify_cleanup():
    """Verify no HTML entities remain"""
    logger.info("\nVerifying cleanup...")

    with get_db() as db:
        remaining = db.query(Transcript).filter(
            (Transcript.text.like('%&gt;%')) |
            (Transcript.text.like('%&lt;%')) |
            (Transcript.text.like('%&amp;%')) |
            (Transcript.text.like('%&quot;%'))
        ).count()

        if remaining == 0:
            logger.info("✅ Verification passed: No HTML entities found")
        else:
            logger.warning(f"⚠️  Found {remaining} transcripts still with HTML entities")

        return remaining


if __name__ == "__main__":
    logger.info("Starting transcript HTML entity decoder...\n")

    try:
        updated = decode_transcripts()
        remaining = verify_cleanup()

        if remaining == 0 and updated > 0:
            logger.info("\n🎉 Success! All transcripts have been decoded.")
        elif remaining == 0 and updated == 0:
            logger.info("\n✓ No transcripts needed updating - all were already clean.")
        else:
            logger.error(f"\n⚠️  Warning: {remaining} transcripts still have HTML entities")
            sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)
