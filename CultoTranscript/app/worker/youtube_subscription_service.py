"""
YouTube WebSub (PubSubHubbub) Subscription Service

Manages real-time notifications from YouTube for new video uploads.
Implements the PubSubHubbub protocol for subscription management.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from urllib.parse import urlencode

import requests
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.common.database import get_db
from app.common.models import Channel, YouTubeSubscription

logger = logging.getLogger(__name__)

# Constants
PUBSUBHUBBUB_HUB = "https://pubsubhubbub.appspot.com/subscribe"
SUBSCRIPTION_LEASE_SECONDS = 864000  # 10 days (YouTube default)
SUBSCRIPTION_RENEWAL_THRESHOLD_HOURS = 24  # Renew if expires in < 24h


class YouTubeSubscriptionService:
    """
    Service for managing YouTube PubSubHubbub subscriptions.

    Features:
    - Subscribe to YouTube channels for real-time notifications
    - Automatic subscription renewal before expiration
    - Unsubscribe when channels are deleted
    - Track subscription status and notification metrics
    """

    def __init__(self):
        """Initialize subscription service"""
        self.hub_url = PUBSUBHUBBUB_HUB
        self.callback_base_url = os.getenv("WEBSUB_CALLBACK_URL", "https://church.byrroserver.com/api/websub/callback")
        logger.info(f"YouTube subscription service initialized with callback: {self.callback_base_url}")

    def subscribe_to_channel(
        self,
        channel_id: int,
        youtube_channel_id: str,
        db: Optional[Session] = None
    ) -> Dict:
        """
        Subscribe to a YouTube channel for real-time notifications.

        Args:
            channel_id: Internal channel ID
            youtube_channel_id: YouTube channel ID (e.g., UCxxxxx)
            db: Optional database session

        Returns:
            dict with subscription status and details
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            # Check if subscription already exists
            existing = db.query(YouTubeSubscription).filter(
                YouTubeSubscription.youtube_channel_id == youtube_channel_id
            ).first()

            topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={youtube_channel_id}"
            callback_url = f"{self.callback_base_url}/{youtube_channel_id}"

            if existing:
                logger.info(f"Subscription already exists for {youtube_channel_id} (status: {existing.subscription_status})")

                # If active and not expiring soon, return existing
                if existing.subscription_status == "active" and existing.expires_at:
                    time_until_expiry = existing.expires_at - datetime.now(timezone.utc)
                    if time_until_expiry.total_seconds() > SUBSCRIPTION_RENEWAL_THRESHOLD_HOURS * 3600:
                        return {
                            "success": True,
                            "action": "existing",
                            "subscription_id": existing.id,
                            "status": existing.subscription_status,
                            "expires_at": existing.expires_at
                        }

            # Prepare subscription request
            params = {
                "hub.callback": callback_url,
                "hub.topic": topic_url,
                "hub.verify": "async",
                "hub.mode": "subscribe",
                "hub.lease_seconds": SUBSCRIPTION_LEASE_SECONDS
            }

            logger.info(f"Subscribing to YouTube channel {youtube_channel_id}")
            logger.debug(f"Subscription params: {params}")

            # Send subscription request
            response = requests.post(
                self.hub_url,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 202:
                # Subscription request accepted
                logger.info(f"Subscription request accepted for {youtube_channel_id}")

                # Create or update subscription record
                if existing:
                    existing.subscription_status = "pending"
                    existing.callback_url = callback_url
                    existing.topic_url = topic_url
                    existing.updated_at = datetime.now(timezone.utc)
                    subscription = existing
                else:
                    subscription = YouTubeSubscription(
                        channel_id=channel_id,
                        youtube_channel_id=youtube_channel_id,
                        callback_url=callback_url,
                        hub_url=self.hub_url,
                        topic_url=topic_url,
                        subscription_status="pending"
                    )
                    db.add(subscription)

                db.commit()
                db.refresh(subscription)

                return {
                    "success": True,
                    "action": "subscribed",
                    "subscription_id": subscription.id,
                    "status": "pending",
                    "message": "Subscription request sent, awaiting verification"
                }
            else:
                # Subscription failed
                logger.error(f"Subscription failed for {youtube_channel_id}: {response.status_code} {response.text}")

                if existing:
                    existing.subscription_status = "failed"
                    existing.updated_at = datetime.now(timezone.utc)
                    db.commit()

                return {
                    "success": False,
                    "error": f"Subscription request failed: {response.status_code}",
                    "details": response.text
                }

        except Exception as e:
            logger.error(f"Error subscribing to {youtube_channel_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)

    def unsubscribe_from_channel(
        self,
        youtube_channel_id: str,
        db: Optional[Session] = None
    ) -> Dict:
        """
        Unsubscribe from a YouTube channel.

        Args:
            youtube_channel_id: YouTube channel ID
            db: Optional database session

        Returns:
            dict with unsubscription status
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            subscription = db.query(YouTubeSubscription).filter(
                YouTubeSubscription.youtube_channel_id == youtube_channel_id
            ).first()

            if not subscription:
                logger.warning(f"No subscription found for {youtube_channel_id}")
                return {
                    "success": True,
                    "action": "none",
                    "message": "No active subscription found"
                }

            # Prepare unsubscribe request
            params = {
                "hub.callback": subscription.callback_url,
                "hub.topic": subscription.topic_url,
                "hub.verify": "async",
                "hub.mode": "unsubscribe"
            }

            logger.info(f"Unsubscribing from YouTube channel {youtube_channel_id}")

            # Send unsubscribe request
            response = requests.post(
                self.hub_url,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 202:
                logger.info(f"Unsubscribe request accepted for {youtube_channel_id}")

                # Update subscription status
                subscription.subscription_status = "unsubscribed"
                subscription.updated_at = datetime.now(timezone.utc)
                db.commit()

                return {
                    "success": True,
                    "action": "unsubscribed",
                    "message": "Unsubscribe request sent"
                }
            else:
                logger.error(f"Unsubscribe failed for {youtube_channel_id}: {response.status_code}")
                return {
                    "success": False,
                    "error": f"Unsubscribe request failed: {response.status_code}",
                    "details": response.text
                }

        except Exception as e:
            logger.error(f"Error unsubscribing from {youtube_channel_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)

    def mark_verified(
        self,
        youtube_channel_id: str,
        lease_seconds: int,
        db: Optional[Session] = None
    ) -> bool:
        """
        Mark subscription as verified after hub callback.

        Args:
            youtube_channel_id: YouTube channel ID
            lease_seconds: Subscription lease duration in seconds
            db: Optional database session

        Returns:
            bool indicating success
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            subscription = db.query(YouTubeSubscription).filter(
                YouTubeSubscription.youtube_channel_id == youtube_channel_id
            ).first()

            if not subscription:
                logger.error(f"Cannot verify: subscription not found for {youtube_channel_id}")
                return False

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=lease_seconds)

            subscription.subscription_status = "active"
            subscription.last_subscribed_at = now
            subscription.expires_at = expires_at
            subscription.updated_at = now

            db.commit()

            logger.info(f"Subscription verified for {youtube_channel_id}, expires at {expires_at}")
            return True

        except Exception as e:
            logger.error(f"Error marking subscription verified: {str(e)}", exc_info=True)
            return False

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)

    def record_notification(
        self,
        youtube_channel_id: str,
        db: Optional[Session] = None
    ) -> bool:
        """
        Record that a notification was received for this subscription.

        Args:
            youtube_channel_id: YouTube channel ID
            db: Optional database session

        Returns:
            bool indicating success
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            subscription = db.query(YouTubeSubscription).filter(
                YouTubeSubscription.youtube_channel_id == youtube_channel_id
            ).first()

            if not subscription:
                logger.warning(f"Cannot record notification: subscription not found for {youtube_channel_id}")
                return False

            subscription.last_notification_at = datetime.now(timezone.utc)
            subscription.notification_count += 1
            subscription.updated_at = datetime.now(timezone.utc)

            db.commit()

            logger.info(f"Recorded notification for {youtube_channel_id} (total: {subscription.notification_count})")
            return True

        except Exception as e:
            logger.error(f"Error recording notification: {str(e)}", exc_info=True)
            return False

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)

    def renew_expiring_subscriptions(
        self,
        db: Optional[Session] = None
    ) -> Dict:
        """
        Renew subscriptions that are expiring soon.

        Args:
            db: Optional database session

        Returns:
            dict with renewal results
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            threshold_time = datetime.now(timezone.utc) + timedelta(hours=SUBSCRIPTION_RENEWAL_THRESHOLD_HOURS)

            # Find subscriptions expiring soon
            expiring = db.query(YouTubeSubscription).filter(
                and_(
                    YouTubeSubscription.subscription_status == "active",
                    YouTubeSubscription.expires_at <= threshold_time
                )
            ).all()

            logger.info(f"Found {len(expiring)} subscriptions expiring within {SUBSCRIPTION_RENEWAL_THRESHOLD_HOURS}h")

            results = {
                "total": len(expiring),
                "renewed": 0,
                "failed": 0,
                "errors": []
            }

            for subscription in expiring:
                logger.info(f"Renewing subscription for {subscription.youtube_channel_id}")

                result = self.subscribe_to_channel(
                    channel_id=subscription.channel_id,
                    youtube_channel_id=subscription.youtube_channel_id,
                    db=db
                )

                if result.get("success"):
                    results["renewed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "youtube_channel_id": subscription.youtube_channel_id,
                        "error": result.get("error")
                    })

            logger.info(f"Renewal complete: {results['renewed']} renewed, {results['failed']} failed")
            return results

        except Exception as e:
            logger.error(f"Error renewing subscriptions: {str(e)}", exc_info=True)
            return {
                "total": 0,
                "renewed": 0,
                "failed": 0,
                "error": str(e)
            }

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)

    def get_subscription_status(
        self,
        youtube_channel_id: str,
        db: Optional[Session] = None
    ) -> Optional[Dict]:
        """
        Get current subscription status for a channel.

        Args:
            youtube_channel_id: YouTube channel ID
            db: Optional database session

        Returns:
            dict with subscription details or None
        """
        use_context_manager = db is None
        if use_context_manager:
            db = get_db().__enter__()

        try:
            subscription = db.query(YouTubeSubscription).filter(
                YouTubeSubscription.youtube_channel_id == youtube_channel_id
            ).first()

            if not subscription:
                return None

            return {
                "id": subscription.id,
                "channel_id": subscription.channel_id,
                "youtube_channel_id": subscription.youtube_channel_id,
                "status": subscription.subscription_status,
                "last_subscribed_at": subscription.last_subscribed_at,
                "expires_at": subscription.expires_at,
                "last_notification_at": subscription.last_notification_at,
                "notification_count": subscription.notification_count,
                "created_at": subscription.created_at,
                "updated_at": subscription.updated_at
            }

        finally:
            if use_context_manager:
                db.__exit__(None, None, None)


# Singleton instance
_subscription_service = None


def get_subscription_service() -> YouTubeSubscriptionService:
    """Get or create singleton subscription service instance"""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = YouTubeSubscriptionService()
    return _subscription_service
