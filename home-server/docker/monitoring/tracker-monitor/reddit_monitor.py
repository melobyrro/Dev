"""
Reddit Monitor Module

Handles Reddit RSS feed parsing to fetch recent posts from configured subreddits.
No authentication required - uses public RSS feeds.
"""

import json
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
import time
import urllib.parse
import urllib.request

import feedparser

logger = logging.getLogger(__name__)


class RedditMonitor:
    """Reddit RSS feed parser for monitoring subreddits for tracker enrollment posts."""
    
    def __init__(self, subreddits: List[str], max_posts: int = 25):
        """Initialize Reddit monitor.
        
        Args:
            subreddits: List of subreddit names to monitor (e.g., ['trackers', 'OpenSignups'])
            max_posts: Maximum number of posts to fetch per subreddit per check
        """
        self.subreddits = subreddits
        self.max_posts = max_posts
        self.user_agent = 'TrackerMonitor/1.0 (RSS; +https://ntfy.byrroserver.com)'
        
        logger.info(f"Reddit RSS monitor initialized for {len(subreddits)} subreddits")
    
    def fetch_recent_posts(self) -> List[Dict]:
        """Fetch recent posts from all configured subreddits.
        
        Returns:
            List of post dictionaries with keys: id, title, body, url, subreddit, 
            created_utc, score, author
        """
        all_posts = []
        seen_ids = set()

        for subreddit_name in self.subreddits:
            try:
                posts = self._fetch_subreddit_posts(subreddit_name)
                for post in posts:
                    if post['id'] in seen_ids:
                        continue
                    seen_ids.add(post['id'])
                    all_posts.append(post)
                logger.info(f"Fetched {len(posts)} posts from r/{subreddit_name}")

                if subreddit_name.lower() == 'opensignups':
                    closed_posts = self._fetch_closed_flair_posts(subreddit_name)
                    for post in closed_posts:
                        if post['id'] in seen_ids:
                            continue
                        seen_ids.add(post['id'])
                        all_posts.append(post)
                    logger.info(
                        f"Fetched {len(closed_posts)} CLOSED flair posts from r/{subreddit_name}"
                    )

                # Be polite - small delay between subreddit requests
                if subreddit_name != self.subreddits[-1]:
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error fetching posts from r/{subreddit_name}: {e}", exc_info=True)
                # Continue with other subreddits
        
        return all_posts
    
    def _fetch_subreddit_posts(self, subreddit_name: str) -> List[Dict]:
        """Fetch recent posts from a single subreddit via RSS feed.
        
        Args:
            subreddit_name: Name of subreddit (without 'r/' prefix)
            
        Returns:
            List of post dictionaries
        """
        posts = []
        
        try:
            # Construct RSS feed URL
            rss_url = f"https://www.reddit.com/r/{subreddit_name}/.rss"
            
            # Parse RSS feed with custom User-Agent
            feed = feedparser.parse(rss_url, agent=self.user_agent)
            
            # Check for feed parsing errors
            if feed.bozo and not feed.entries:
                logger.error(f"Failed to parse RSS feed for r/{subreddit_name}: {feed.bozo_exception}")
                return posts
            
            # Check HTTP status
            if hasattr(feed, 'status'):
                if feed.status == 404:
                    logger.error(f"Subreddit r/{subreddit_name} not found (404)")
                    return posts
                elif feed.status >= 500:
                    logger.error(f"Reddit server error for r/{subreddit_name} (HTTP {feed.status})")
                    return posts
                elif feed.status >= 400:
                    logger.warning(f"HTTP {feed.status} for r/{subreddit_name}")
                    return posts
            
            # Process feed entries
            for entry in feed.entries[:self.max_posts]:
                try:
                    post_data = self._parse_feed_entry(entry, subreddit_name)
                    posts.append(post_data)
                except Exception as e:
                    logger.warning(f"Error parsing feed entry: {e}")
                    continue
            
            if not posts:
                logger.info(f"No posts found in r/{subreddit_name} RSS feed")
                
        except Exception as e:
            logger.error(f"Unexpected error fetching RSS from r/{subreddit_name}: {e}")
            raise
        
        return posts

    def _fetch_closed_flair_posts(self, subreddit_name: str) -> List[Dict]:
        """Fetch recent CLOSED flair posts from a subreddit via JSON search."""
        posts = []
        try:
            query = 'flair:"Closed"'
            params = urllib.parse.urlencode({
                'q': query,
                'restrict_sr': 1,
                'sort': 'new',
                'limit': self.max_posts,
                'raw_json': 1
            })
            url = f"https://www.reddit.com/r/{subreddit_name}/search.json?{params}"
            req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            children = data.get('data', {}).get('children', [])
            for child in children:
                post_data = self._parse_json_post(child.get('data', {}), subreddit_name)
                posts.append(post_data)

        except Exception as e:
            logger.error(f"Error fetching CLOSED flair posts from r/{subreddit_name}: {e}", exc_info=True)

        return posts

    def _parse_json_post(self, post: Dict, subreddit_name: str) -> Dict:
        """Parse a JSON post entry into post dictionary."""
        post_id = post.get('id') or 'unknown'
        title = post.get('title') or '[No Title]'
        created_utc = datetime.utcfromtimestamp(post.get('created_utc', time.time()))
        author = post.get('author') or '[unknown]'
        url = post.get('url') or f"https://reddit.com/r/{subreddit_name}"
        body = post.get('selftext') or ''

        return {
            'id': post_id,
            'title': title,
            'body': body,
            'url': url,
            'subreddit': subreddit_name,
            'created_utc': created_utc,
            'score': post.get('score', 0),
            'author': author,
            'flair': post.get('link_flair_text'),
            'source': 'reddit_json'
        }
    
    def _parse_feed_entry(self, entry, subreddit_name: str) -> Dict:
        """Parse a single RSS feed entry into post dictionary.
        
        Args:
            entry: feedparser entry object
            subreddit_name: Name of subreddit
            
        Returns:
            Post dictionary
        """
        # Extract post ID from entry
        # RSS entry.id format: https://www.reddit.com/r/OpenSignups/t3_1pyk3bv
        # RSS entry.link format: https://www.reddit.com/r/OpenSignups/comments/1pyk3bv/title/
        post_id = 'unknown'

        # First try to extract from entry.id (t3_xxxxx format)
        if hasattr(entry, 'id') and entry.id:
            # Get the last part after splitting by '/'
            last_part = entry.id.rstrip('/').split('/')[-1]
            # Remove 't3_' prefix if present
            if last_part.startswith('t3_'):
                post_id = last_part[3:]  # Remove 't3_' prefix
            else:
                post_id = last_part

        # Fallback: try to extract from link (comments/xxxxx format)
        if post_id == 'unknown' and hasattr(entry, 'link') and entry.link:
            parts = entry.link.rstrip('/').split('/')
            if 'comments' in parts:
                comment_idx = parts.index('comments')
                if comment_idx + 1 < len(parts):
                    post_id = parts[comment_idx + 1]
        
        # Parse published date
        created_utc = datetime.now()
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            created_utc = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            created_utc = datetime(*entry.updated_parsed[:6])
        
        # Extract author
        author = '[unknown]'
        if hasattr(entry, 'author'):
            # RSS author format: /u/username
            author = entry.author.replace('/u/', '')
        
        # Get title
        title = entry.title if hasattr(entry, 'title') else '[No Title]'
        
        # Get body/summary (RSS provides HTML-formatted summary)
        body = ''
        if hasattr(entry, 'summary'):
            # Strip HTML tags for plain text (basic approach)
            import re
            body = re.sub(r'<[^>]+>', '', entry.summary)
            # Decode HTML entities
            import html
            body = html.unescape(body)
        
        # Get link
        url = entry.link if hasattr(entry, 'link') else f"https://reddit.com/r/{subreddit_name}"
        
        post_data = {
            'id': post_id,
            'title': title,
            'body': body,
            'url': url,
            'subreddit': subreddit_name,
            'created_utc': created_utc,
            'score': 0,  # RSS feeds don't include scores
            'author': author,
            'source': 'rss'
        }
        
        return post_data
    
    def enrich_post(self, post: Dict) -> Dict:
        # Fetch full post details for RSS entries to improve metadata.
        if not isinstance(post, dict):
            return post
        if post.get('source') != 'rss':
            return post

        post_id = post.get('id')
        if not post_id or post_id == 'unknown':
            return post

        try:
            details = self._fetch_post_details(post_id, post.get('subreddit'))
        except Exception as e:
            logger.warning(f"Error fetching Reddit JSON for {post_id}: {e}")
            return post

        if not details:
            return post

        if details.get('body'):
            post['body'] = details['body']
        if details.get('flair') and not post.get('flair'):
            post['flair'] = details['flair']
        if details.get('title'):
            post['title'] = details['title']
        if details.get('url'):
            post['url'] = details['url']
        if details.get('removed_by_category'):
            post['removed_by_category'] = details['removed_by_category']

        return post

    def _fetch_post_details(self, post_id: str, subreddit: Optional[str]) -> Optional[Dict]:
        # Fetch full post details from Reddit JSON.
        if not post_id:
            return None

        base = f"https://www.reddit.com/comments/{post_id}.json"
        if subreddit:
            base = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = urllib.parse.urlencode({'raw_json': 1})
        url = f"{base}?{params}"

        req = urllib.request.Request(url, headers={'User-Agent': self.user_agent})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        if not isinstance(data, list) or not data:
            return None

        post_listing = data[0].get('data', {}).get('children', [])
        if not post_listing:
            return None

        post_data = post_listing[0].get('data', {})
        return {
            'title': post_data.get('title'),
            'body': post_data.get('selftext') or '',
            'url': post_data.get('url'),
            'flair': post_data.get('link_flair_text'),
            'removed_by_category': post_data.get('removed_by_category')
        }

    def get_post_status(self, url: str) -> Optional[Dict]:
        post_id = self._extract_post_id_from_url(url)
        if not post_id:
            return None
        subreddit = self._extract_subreddit_from_url(url)
        details = self._fetch_post_details(post_id, subreddit)
        if details:
            details['post_id'] = post_id
            details['subreddit'] = subreddit
        return details

    def _extract_post_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        base = url.split('?', 1)[0]
        match = re.search(r'/comments/([a-z0-9]+)/', base, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'/comments/([a-z0-9]+)$', base, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r't3_([a-z0-9]+)', base, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_subreddit_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        match = re.search(r'/r/([^/]+)/comments/', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def test_connection(self) -> bool:
        """Test Reddit RSS feed access.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to fetch RSS feed from r/test
            rss_url = "https://www.reddit.com/r/test/.rss"
            feed = feedparser.parse(rss_url, agent=self.user_agent)
            
            if feed.bozo and not feed.entries:
                logger.error(f"RSS test failed: {feed.bozo_exception}")
                return False
            
            if hasattr(feed, 'status') and feed.status >= 400:
                logger.error(f"RSS test failed with HTTP {feed.status}")
                return False
            
            logger.info(f"Test successful: fetched {len(feed.entries)} posts from r/test")
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def close(self) -> None:
        """Cleanup resources (no-op for RSS implementation)."""
        logger.debug("Reddit monitor closed")


# Example usage for testing
if __name__ == '__main__':
    import sys
    
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test Reddit RSS connection
    monitor = RedditMonitor(subreddits=['trackers'], max_posts=5)
    
    if monitor.test_connection():
        print("✅ Reddit RSS connection successful")
        
        # Fetch some posts
        posts = monitor.fetch_recent_posts()
        print(f"\n📬 Fetched {len(posts)} posts:")
        for post in posts[:3]:  # Show first 3
            print(f"  - {post['title'][:60]}... (r/{post['subreddit']})")
            print(f"    By: {post['author']} | Posted: {post['created_utc']}")
    else:
        print("❌ Reddit RSS connection failed")
        sys.exit(1)
