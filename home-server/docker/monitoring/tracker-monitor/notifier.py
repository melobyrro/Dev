"""
Notifier Module v2

Sends notifications via Home Assistant and ntfy.
Prometheus/Grafana metrics are optional and disabled by default.
"""

import os
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Notifier:
    """Handles notifications to Home Assistant, ntfy, and optional metrics."""

    def __init__(self, config: Dict):
        """Initialize notifier from config.

        Args:
            config: Full configuration dictionary
        """
        notification_config = config.get('notification', {})

        # Home Assistant config
        ha_config = notification_config.get('homeassistant', {})
        self.ha_enabled = ha_config.get('enabled', False)
        self.ha_url = ha_config.get('url', 'http://192.168.1.11:8123')
        self.ha_token = os.environ.get('HA_TOKEN', ha_config.get('token', ''))
        self.ha_service = ha_config.get('service', 'notify.persistent_notification')
        self.ha_persistent = ha_config.get('persistent_notification', True)

        # ntfy config (backup)
        ntfy_config = notification_config.get('ntfy', {})
        self.ntfy_enabled = ntfy_config.get('enabled', True)
        self.ntfy_server = ntfy_config.get('server', 'https://ntfy.sh')
        self.ntfy_topic = ntfy_config.get('topic', 'tracker-enrollments')
        self.ntfy_priority = ntfy_config.get('priority', 'high')

        # Metrics config
        metrics_config = config.get('metrics', {})
        self.pushgateway_enabled = metrics_config.get('pushgateway_enabled', False)
        self.pushgateway_url = config.get('pushgateway_url', 'http://pushgateway:9091')

        logger.info(f"Notifier initialized: HA={self.ha_enabled}, ntfy={self.ntfy_enabled}, "
                   f"pushgateway={self.pushgateway_enabled}")

    def send_signup_alert(self, tracker_name: str, post_data: Dict) -> bool:
        """Send open signup alert via configured channels.

        Args:
            tracker_name: Name of tracker (or "Unknown" for generic matches)
            post_data: Reddit post data dictionary

        Returns:
            True if at least one notification sent successfully
        """
        success = False

        # Try Home Assistant first
        if self.ha_enabled:
            if self._send_homeassistant_notification(tracker_name, post_data):
                success = True

        # Also send to ntfy as backup
        if self.ntfy_enabled:
            if self._send_ntfy_notification(tracker_name, post_data):
                success = True

        return success

    def _send_homeassistant_notification(self, tracker_name: str, post_data: Dict) -> bool:
        """Send notification via Home Assistant REST API.

        Args:
            tracker_name: Name of tracker
            post_data: Reddit post data

        Returns:
            True if successful
        """
        if not self.ha_token:
            logger.warning("Home Assistant token not configured, skipping HA notification")
            return False

        try:
            headers = {
                'Authorization': f'Bearer {self.ha_token}',
                'Content-Type': 'application/json'
            }

            # Format message
            title = f"Tracker Open Signup: {tracker_name}"
            message = (
                f"**{tracker_name}** has open signups!\n\n"
                f"Source: r/{post_data['subreddit']}\n"
                f"Title: {post_data['title']}\n"
                f"Posted: {self._format_time_ago(post_data['created_utc'])}\n\n"
                f"[Open Reddit Post]({post_data['url']})"
            )

            # Send mobile notification
            if 'mobile_app' in self.ha_service:
                payload = {
                    'title': title,
                    'message': message,
                    'data': {
                        'url': post_data['url'],
                        'clickAction': post_data['url'],
                        'tag': f'tracker-{tracker_name}',
                        'group': 'tracker-signups',
                        'push': {
                            'sound': 'default',
                            'badge': 1
                        },
                        'actions': [
                            {
                                'action': 'URI',
                                'title': 'Open Reddit',
                                'uri': post_data['url']
                            }
                        ]
                    }
                }

                response = requests.post(
                    f"{self.ha_url}/api/services/{self.ha_service.replace('.', '/')}",
                    json=payload,
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"Home Assistant mobile notification sent for {tracker_name}")
                else:
                    logger.error(f"HA mobile notification failed: {response.status_code} {response.text}")

            # Also create persistent notification
            if self.ha_persistent:
                persistent_payload = {
                    'title': title,
                    'message': message,
                    'notification_id': f'tracker_{tracker_name}_{post_data["id"]}'
                }

                response = requests.post(
                    f"{self.ha_url}/api/services/persistent_notification/create",
                    json=persistent_payload,
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"HA persistent notification created for {tracker_name}")
                else:
                    logger.warning(f"HA persistent notification failed: {response.status_code}")

            # Update HA input entities for dashboard visibility
            self._update_ha_entities(tracker_name, post_data, headers)

            return True

        except Exception as e:
            logger.error(f"Error sending Home Assistant notification: {e}", exc_info=True)
            return False

    def _update_ha_entities(self, tracker_name: str, post_data: Dict, headers: Dict) -> None:
        """Update HA input entities for dashboard visibility.

        Updates input_text, input_datetime, and input_number entities
        so signup history is visible in the HA dashboard even after
        persistent notifications are dismissed.

        Args:
            tracker_name: Name of tracker
            post_data: Reddit post data
            headers: HTTP headers with auth token
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Update last signup text
            signup_text = f"{tracker_name} - {post_data['url']}"
            requests.post(
                f"{self.ha_url}/api/services/input_text/set_value",
                json={
                    "entity_id": "input_text.last_tracker_signup",
                    "value": signup_text[:255]  # Respect max length
                },
                headers=headers,
                timeout=10
            )
            logger.debug(f"Updated input_text.last_tracker_signup: {signup_text[:50]}...")

            # Update timestamp
            requests.post(
                f"{self.ha_url}/api/services/input_datetime/set_datetime",
                json={
                    "entity_id": "input_datetime.last_tracker_signup_time",
                    "datetime": timestamp
                },
                headers=headers,
                timeout=10
            )
            logger.debug(f"Updated input_datetime.last_tracker_signup_time: {timestamp}")

            # Increment the 24h counter
            # First get current value, then increment
            try:
                current = requests.get(
                    f"{self.ha_url}/api/states/input_number.tracker_signup_count_24h",
                    headers=headers,
                    timeout=10
                )
                if current.status_code == 200:
                    current_count = float(current.json().get('state', 0))
                    new_count = min(current_count + 1, 100)  # Cap at 100
                    requests.post(
                        f"{self.ha_url}/api/services/input_number/set_value",
                        json={
                            "entity_id": "input_number.tracker_signup_count_24h",
                            "value": new_count
                        },
                        headers=headers,
                        timeout=10
                    )
                    logger.debug(f"Incremented tracker_signup_count_24h to {new_count}")
            except Exception as e:
                logger.warning(f"Could not increment signup counter: {e}")

            logger.info(f"Updated HA entities for tracker signup: {tracker_name}")

        except Exception as e:
            logger.warning(f"Error updating HA entities (non-critical): {e}")

    def _send_ntfy_notification(self, tracker_name: str, post_data: Dict) -> bool:
        """Send notification via ntfy.

        Args:
            tracker_name: Name of tracker
            post_data: Reddit post data

        Returns:
            True if successful
        """
        try:
            title = f"Tracker Open Signup: {tracker_name}"

            message = (
                f"{tracker_name} signup detected!\n\n"
                f"Source: r/{post_data['subreddit']}\n"
                f"Title: {post_data['title']}\n"
                f"Posted: {self._format_time_ago(post_data['created_utc'])}\n\n"
                f"Link: {post_data['url']}"
            )

            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data=message.encode('utf-8'),
                headers={
                    'Title': title,
                    'Priority': self.ntfy_priority,
                    'Tags': 'tracker,signup,open',
                    'Click': post_data['url']
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"ntfy notification sent for {tracker_name}")
                return True
            else:
                logger.error(f"ntfy notification failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending ntfy notification: {e}", exc_info=True)
            return False

    def push_metrics(self, tracker_statuses: List[Dict]) -> bool:
        """Push Prometheus metrics (if enabled).

        Args:
            tracker_statuses: List of tracker status dictionaries

        Returns:
            True if successful or metrics disabled
        """
        if not self.pushgateway_enabled:
            logger.debug("Pushgateway disabled, skipping metrics")
            return True

        try:
            metrics_lines = [
                '# HELP tracker_monitor_check_total Total checks performed',
                '# TYPE tracker_monitor_check_total counter',
                f'tracker_monitor_check_total{{job="tracker-monitor"}} 1',
            ]

            metrics_text = '\n'.join(metrics_lines) + '\n'

            response = requests.post(
                f"{self.pushgateway_url}/metrics/job/tracker-monitor",
                data=metrics_text,
                headers={'Content-Type': 'text/plain; charset=utf-8'},
                timeout=5
            )

            return response.status_code == 200

        except Exception as e:
            logger.warning(f"Failed to push metrics (non-critical): {e}")
            return False

    def _format_time_ago(self, created_utc: datetime) -> str:
        """Format datetime as human-readable 'time ago' string."""
        now = datetime.now()
        diff = now - created_utc
        seconds = diff.total_seconds()

        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"

    def test_homeassistant(self) -> bool:
        """Test Home Assistant connection."""
        if not self.ha_enabled or not self.ha_token:
            logger.info("Home Assistant not configured for testing")
            return False

        try:
            headers = {
                'Authorization': f'Bearer {self.ha_token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f"{self.ha_url}/api/",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("Home Assistant connection successful")
                return True
            else:
                logger.error(f"Home Assistant connection failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Home Assistant test error: {e}")
            return False

    def test_ntfy(self) -> bool:
        """Test ntfy connection."""
        if not self.ntfy_enabled:
            return False

        try:
            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data="Test from Tracker Monitor".encode('utf-8'),
                headers={
                    'Title': 'Tracker Monitor Test',
                    'Priority': 'low',
                    'Tags': 'test'
                },
                timeout=10
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"ntfy test error: {e}")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    test_config = {
        'notification': {
            'homeassistant': {
                'enabled': True,
                'url': 'http://192.168.1.11:8123',
                'service': 'notify.mobile_app_andre_iphone'
            },
            'ntfy': {
                'enabled': True,
                'server': 'https://ntfy.sh',
                'topic': 'test-tracker'
            }
        },
        'metrics': {
            'pushgateway_enabled': False
        }
    }

    notifier = Notifier(test_config)

    print("Testing notifier:")
    print(f"  HA test: {notifier.test_homeassistant()}")
    print(f"  ntfy test: {notifier.test_ntfy()}")
