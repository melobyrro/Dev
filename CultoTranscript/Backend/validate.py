#!/usr/bin/env python3
"""
Backend Phase 1 Validation Script

Validates that all Backend components are properly implemented and can be imported.
Run this before integration to catch any issues.
"""
import sys
import os
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def validate_imports():
    """Test that all modules can be imported"""
    print("=" * 80)
    print("Backend Phase 1 - Validation Script")
    print("=" * 80)
    print()

    errors = []

    # Test DTOs
    print("✓ Testing DTOs import...")
    try:
        from Backend.dtos import (
            VideoStatus, EventType,
            VideoDTO, SummaryDTO, BiblicalPassageDTO, CitationDTO,
            VideoDetailDTO, ChannelDTO,
            EventDTO, VideoStatusEventDTO, SummaryReadyEventDTO,
            ErrorEventDTO, HeartbeatEventDTO,
            ApiSuccessResponse, ApiErrorResponse
        )
        print("  ✓ All DTOs imported successfully")
    except Exception as e:
        errors.append(f"DTOs import failed: {e}")
        print(f"  ✗ ERROR: {e}")

    # Test Services
    print("\n✓ Testing Services import...")
    try:
        from Backend.services import SSEManager
        from Backend.services.sse_manager import sse_manager
        print("  ✓ SSEManager imported successfully")
        print(f"  ✓ Singleton instance created: {type(sse_manager).__name__}")
    except Exception as e:
        errors.append(f"Services import failed: {e}")
        print(f"  ✗ ERROR: {e}")

    # Test Middleware
    print("\n✓ Testing Middleware import...")
    try:
        from Backend.middleware import setup_cors, CSRFMiddleware
        print("  ✓ CORS middleware imported successfully")
        print("  ✓ CSRF middleware imported successfully")
    except Exception as e:
        errors.append(f"Middleware import failed: {e}")
        print(f"  ✗ ERROR: {e}")

    # Test API endpoints
    print("\n✓ Testing API endpoints import...")
    try:
        from Backend.api.v2 import events_router
        from Backend.api.v2.events import router as events_router_direct
        from Backend.api.v2.videos import router as videos_router
        print("  ✓ Events router imported successfully")
        print("  ✓ Videos router imported successfully")
    except Exception as e:
        errors.append(f"API endpoints import failed: {e}")
        print(f"  ✗ ERROR: {e}")

    print("\n" + "=" * 80)
    if errors:
        print("VALIDATION FAILED")
        print("=" * 80)
        for error in errors:
            print(f"  ✗ {error}")
        return False
    else:
        print("VALIDATION PASSED - All components imported successfully")
        print("=" * 80)
        return True


def validate_dto_serialization():
    """Test DTO serialization"""
    print("\n" + "=" * 80)
    print("Testing DTO Serialization")
    print("=" * 80)

    try:
        from Backend.dtos import (
            VideoDTO, VideoStatus, VideoStatusEventDTO,
            EventType, HeartbeatEventDTO
        )

        # Test VideoDTO
        print("\n✓ Creating VideoDTO...")
        video = VideoDTO(
            id="test-123",
            title="Test Video",
            youtube_id="dQw4w9WgXcQ",
            status=VideoStatus.PROCESSING,
            duration=3600,
            created_at=datetime.utcnow().isoformat() + "Z",
            channel_id="channel-456"
        )
        print(f"  ✓ VideoDTO created: {video.title}")

        # Test serialization
        print("  ✓ Testing JSON serialization...")
        video_dict = video.model_dump(mode="json")
        print(f"  ✓ Serialized: {video_dict['status']}")

        # Test VideoStatusEventDTO
        print("\n✓ Creating VideoStatusEventDTO...")
        event = VideoStatusEventDTO(
            type=EventType.VIDEO_STATUS,
            timestamp=datetime.utcnow().isoformat() + "Z",
            video_id="test-123",
            status=VideoStatus.PROCESSING,
            progress=50,
            message="Processing video..."
        )
        print(f"  ✓ Event created: {event.type}")

        event_dict = event.model_dump(mode="json")
        print(f"  ✓ Event serialized with progress: {event_dict['progress']}%")

        # Test HeartbeatEventDTO
        print("\n✓ Creating HeartbeatEventDTO...")
        heartbeat = HeartbeatEventDTO(
            type=EventType.HEARTBEAT,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        print(f"  ✓ Heartbeat created: {heartbeat.type}")

        print("\n✓ All DTO serialization tests passed")
        return True

    except Exception as e:
        print(f"\n✗ DTO serialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_sse_manager():
    """Test SSE Manager basic functionality"""
    print("\n" + "=" * 80)
    print("Testing SSE Manager")
    print("=" * 80)

    try:
        from Backend.services.sse_manager import SSEManager

        print("\n✓ Creating SSEManager instance...")
        manager = SSEManager()
        print(f"  ✓ Manager created with {manager.get_client_count()} clients")

        # Note: Can't fully test async methods in sync context
        print("  ✓ SSEManager structure validated")
        print("  ⚠ Full async testing requires running server")

        return True

    except Exception as e:
        print(f"\n✗ SSE Manager validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validations"""
    print()

    results = []

    # Run validations
    results.append(("Import Validation", validate_imports()))
    results.append(("DTO Serialization", validate_dto_serialization()))
    results.append(("SSE Manager", validate_sse_manager()))

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<50} {status}")

    print("=" * 80)

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r Backend/requirements.txt")
        print("  2. Follow INTEGRATION.md to integrate into app/web/main.py")
        print("  3. Test SSE endpoint: curl -N http://localhost:8000/api/v2/events/stream")
        print()
        return 0
    else:
        print("\n❌ SOME VALIDATIONS FAILED")
        print("\nPlease fix the errors above before proceeding.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
