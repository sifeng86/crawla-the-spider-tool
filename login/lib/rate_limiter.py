"""
Rate limiter for web crawling to prevent IP bans and respect server resources.
"""
import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlparse
from typing import Optional


class RateLimiter:
    """
    Per-domain rate limiting to prevent IP bans.
    Thread-safe implementation for concurrent crawling.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 20,
        min_delay_seconds: float = 0.5,
        max_delay_seconds: float = 3.0,
        burst_limit: int = 5
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per domain
            min_delay_seconds: Minimum delay between requests to same domain
            max_delay_seconds: Maximum delay (for randomization)
            burst_limit: Number of quick requests allowed before enforcing delays
        """
        self.rpm = requests_per_minute
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds
        self.burst_limit = burst_limit
        
        self._last_request: dict = defaultdict(float)
        self._request_count: dict = defaultdict(int)
        self._minute_start: dict = defaultdict(float)
        self._lock = Lock()
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL for rate limiting."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:
            return url
    
    def wait_if_needed(self, url: str) -> float:
        """
        Block until safe to make request to the URL's domain.
        
        Args:
            url: The URL to request
            
        Returns:
            The number of seconds waited
        """
        domain = self.extract_domain(url)
        waited = 0.0
        
        with self._lock:
            now = time.time()
            
            # Reset minute counter if needed
            if now - self._minute_start[domain] >= 60:
                self._minute_start[domain] = now
                self._request_count[domain] = 0
            
            # Check rate limit
            if self._request_count[domain] >= self.rpm:
                sleep_time = 60 - (now - self._minute_start[domain])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    waited += sleep_time
                self._minute_start[domain] = time.time()
                self._request_count[domain] = 0
            
            # Apply minimum delay between requests
            elapsed = now - self._last_request[domain]
            if elapsed < self.min_delay and self._request_count[domain] > self.burst_limit:
                sleep_time = self.min_delay - elapsed
                # Add some randomization
                import random
                sleep_time += random.uniform(0, self.max_delay - self.min_delay)
                time.sleep(sleep_time)
                waited += sleep_time
            
            # Update tracking
            self._last_request[domain] = time.time()
            self._request_count[domain] += 1
        
        return waited
    
    def get_stats(self, url: Optional[str] = None) -> dict:
        """
        Get rate limiting statistics.
        
        Args:
            url: Optional URL to get stats for specific domain
            
        Returns:
            Dictionary with stats
        """
        with self._lock:
            if url:
                domain = self.extract_domain(url)
                return {
                    'domain': domain,
                    'requests_this_minute': self._request_count[domain],
                    'last_request': self._last_request[domain],
                }
            return {
                'total_domains': len(self._request_count),
                'domains': dict(self._request_count),
            }
    
    def reset(self, url: Optional[str] = None):
        """
        Reset rate limiting counters.
        
        Args:
            url: Optional URL to reset specific domain, None resets all
        """
        with self._lock:
            if url:
                domain = self.extract_domain(url)
                self._last_request.pop(domain, None)
                self._request_count.pop(domain, None)
                self._minute_start.pop(domain, None)
            else:
                self._last_request.clear()
                self._request_count.clear()
                self._minute_start.clear()


# Global rate limiter instance with sensible defaults
rate_limiter = RateLimiter(
    requests_per_minute=20,
    min_delay_seconds=0.5,
    max_delay_seconds=2.0,
    burst_limit=3
)
