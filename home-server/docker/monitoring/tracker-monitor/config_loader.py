"""
Configuration Loader Module v2

Loads and validates YAML configuration for the tracker monitor.
Supports both new "all trackers" mode and legacy "specific trackers" mode.
"""

import os
import logging
from typing import Dict, Any
import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required sections
        _validate_config(config)

        # Merge with environment variables
        _merge_env_vars(config)

        # Ensure backwards compatibility
        _ensure_compatibility(config)

        logger.info(f"Configuration loaded successfully from {config_path}")
        return config

    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration structure.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    # Required: reddit section
    if 'reddit' not in config:
        raise ValueError("Missing required configuration section: reddit")

    if 'subreddits' not in config['reddit']:
        raise ValueError("Missing 'subreddits' in reddit configuration")

    if not isinstance(config['reddit']['subreddits'], list) or not config['reddit']['subreddits']:
        raise ValueError("'subreddits' must be a non-empty list")

    # Detection mode determines other requirements
    detection_mode = config.get('detection_mode', 'all')

    if detection_mode == 'all':
        # Need signup_keywords
        if 'signup_keywords' not in config or not config['signup_keywords']:
            raise ValueError("'signup_keywords' required for detection_mode='all'")
    else:
        # Need specific trackers (legacy mode)
        if 'trackers' not in config or not config['trackers']:
            raise ValueError("'trackers' required for detection_mode='specific'")

        for tracker in config['trackers']:
            if 'name' not in tracker:
                raise ValueError("Each tracker must have a 'name' field")
            if 'keywords' not in tracker:
                raise ValueError(f"Tracker '{tracker['name']}' missing 'keywords' field")

    # Notification section (at least one method should be configured)
    if 'notification' not in config:
        config['notification'] = {}

    logger.debug("Configuration validation passed")


def _merge_env_vars(config: Dict[str, Any]) -> None:
    """Merge environment variable overrides into configuration.

    Args:
        config: Configuration dictionary (modified in-place)
    """
    # Home Assistant token (sensitive - should come from env)
    if 'HA_TOKEN' in os.environ:
        if 'notification' not in config:
            config['notification'] = {}
        if 'homeassistant' not in config['notification']:
            config['notification']['homeassistant'] = {}
        config['notification']['homeassistant']['token'] = os.environ['HA_TOKEN']

    # Pushgateway URL (optional)
    if 'PUSHGATEWAY_URL' in os.environ:
        config['pushgateway_url'] = os.environ['PUSHGATEWAY_URL']

    # ntfy overrides
    if 'NTFY_SERVER' in os.environ:
        if 'ntfy' not in config.get('notification', {}):
            config['notification']['ntfy'] = {}
        config['notification']['ntfy']['server'] = os.environ['NTFY_SERVER']

    if 'NTFY_TOPIC' in os.environ:
        if 'ntfy' not in config.get('notification', {}):
            config['notification']['ntfy'] = {}
        config['notification']['ntfy']['topic'] = os.environ['NTFY_TOPIC']

    logger.debug("Environment variable overrides applied")


def _ensure_compatibility(config: Dict[str, Any]) -> None:
    """Ensure backwards compatibility with older configs.

    Args:
        config: Configuration dictionary (modified in-place)
    """
    # Default detection mode
    if 'detection_mode' not in config:
        # If trackers are defined but not signup_keywords, use specific mode
        if 'trackers' in config and 'signup_keywords' not in config:
            config['detection_mode'] = 'specific'
        else:
            config['detection_mode'] = 'all'

    # Default filters
    if 'filters' not in config:
        config['filters'] = {}

    if 'ignore_words' not in config['filters']:
        config['filters']['ignore_words'] = ['closed', 'ended']

    if 'minimum_post_score' not in config['filters']:
        config['filters']['minimum_post_score'] = 0

    # Default language settings
    if 'language' not in config:
        config['language'] = {
            'enabled': False,
            'allowed': ['english', 'portuguese']
        }

    # Default reddit settings
    if 'check_interval_minutes' not in config['reddit']:
        config['reddit']['check_interval_minutes'] = 30

    if 'max_posts_per_check' not in config['reddit']:
        config['reddit']['max_posts_per_check'] = 25

    # Default metrics (disabled)
    if 'metrics' not in config:
        config['metrics'] = {'pushgateway_enabled': False}


def get_default_config() -> Dict[str, Any]:
    """Get default configuration structure.

    Returns:
        Default configuration dictionary
    """
    return {
        'reddit': {
            'subreddits': ['trackers', 'OpenSignups', 'OpenInvites'],
            'check_interval_minutes': 15,
            'max_posts_per_check': 50
        },
        'detection_mode': 'all',
        'signup_keywords': [
            'open signup', 'open signups', 'open registration',
            'applications open', 'signups open', 'registration open',
            'now open', 'is open', 'are open'
        ],
        'ignored_trackers': [],
        'language': {
            'enabled': True,
            'allowed': ['english', 'portuguese'],
            'portuguese_trackers': ['BrasilTracker', 'BRT']
        },
        'notification': {
            'homeassistant': {
                'enabled': True,
                'url': 'http://192.168.1.11:8123',
                'service': 'notify.mobile_app_andre_iphone',
                'persistent_notification': True
            },
            'ntfy': {
                'enabled': True,
                'server': 'https://ntfy.sh',
                'topic': 'tracker-enrollments',
                'priority': 'high'
            }
        },
        'filters': {
            'ignore_words': ['closed', 'ended', 'deadline passed'],
            'minimum_post_score': 0
        },
        'metrics': {
            'pushgateway_enabled': False
        }
    }


if __name__ == '__main__':
    import tempfile

    logging.basicConfig(level=logging.DEBUG)

    # Create temp config file
    temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)

    try:
        test_config = get_default_config()
        yaml.dump(test_config, temp_config)
        temp_config.close()

        print("Testing config loader:\n")

        config = load_config(temp_config.name)
        print(f"  Detection mode: {config['detection_mode']}")
        print(f"  Subreddits: {config['reddit']['subreddits']}")
        print(f"  Signup keywords: {len(config['signup_keywords'])}")
        print(f"  Language filter: {config['language']['enabled']}")
        print(f"  HA enabled: {config['notification']['homeassistant']['enabled']}")

        print("\nConfig loaded successfully!")

    finally:
        import os
        if os.path.exists(temp_config.name):
            os.remove(temp_config.name)
