"""
Screener.in Unofficial API client.
Provides access to Indian stock fundamental data via Screener's data.
Includes retry logic, timeout handling, and comprehensive error reporting.
"""

import os
import time
import functools
from typing import Dict, Any, Optional, List, Callable
import requests


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry API calls on transient failures."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.ConnectionError, requests.Timeout) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
                except requests.HTTPError as e:
                    # Don't retry 4xx errors (client errors)
                    if 400 <= e.response.status_code < 500:
                        raise
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception  # type: ignore
        return wrapper
    return decorator


class ScreenerAPI:
    """Client for Screener Unofficial API with retry and timeout support."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize the Screener API client.

        Args:
            base_url: Base URL for the Screener API. Defaults to env var or http://127.0.0.1:8098.
            api_key: Optional API key for authentication.
            timeout: Request timeout in seconds. Defaults to 30.
        """
        self.base_url = (base_url or os.getenv("SCREENER_API_BASE_URL", "http://127.0.0.1:8000")).rstrip('/')
        self.api_key = api_key or os.getenv("SCREENER_API_KEY")
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'x-api-key': self.api_key})
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    @retry_on_failure(max_retries=3, delay=1.0)
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a GET request to the Screener API with retry logic.

        Args:
            endpoint: API endpoint path (e.g., '/v1/company/RELIANCE').
            params: Optional query parameters.

        Returns:
            JSON response as dictionary.

        Raises:
            requests.ConnectionError: If the API server is unreachable.
            requests.Timeout: If the request times out.
            requests.HTTPError: If the server returns an error status.
        """
        url = self.base_url + endpoint
        
        # Add cache-busting parameter if SCREENER_FRESH is set (--fresh flag)
        fresh_timestamp = os.getenv("SCREENER_FRESH")
        if fresh_timestamp:
            if params is None:
                params = {}
            params['_t'] = fresh_timestamp  # Underscore prefix = ignored by Screener API
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_company(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive company data including fundamentals, ratios, and financials."""
        return self._get(f"/v1/company/{symbol}")

    def get_company_tab(self, symbol: str, tab: str) -> Dict[str, Any]:
        """
        Get specific tab data for a company.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE').
            tab: One of 'analysis', 'peers', 'quarters', 'profit-loss',
                 'balance-sheet', 'cash-flow', 'ratios', 'shareholding', 'documents'.

        Returns:
            Tab-specific data as dictionary.
        """
        valid_tabs = {'analysis', 'peers', 'quarters', 'profit-loss',
                      'balance-sheet', 'cash-flow', 'ratios', 'shareholding', 'documents'}
        if tab not in valid_tabs:
            return {'error': f'Invalid tab "{tab}". Valid options: {sorted(valid_tabs)}'}
        return self._get(f"/v1/company/{symbol}/{tab}")

    def compare_companies(self, symbols: List[str]) -> Dict[str, Any]:
        """Compare fundamental metrics across multiple companies."""
        if not symbols:
            return {'error': 'At least one symbol is required'}
        params = {'symbols': ','.join(symbols)}
        return self._get('/v1/compare', params=params)

    def search_companies(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for companies by name or partial match."""
        if not query or not query.strip():
            return {'error': 'Search query cannot be empty'}
        params = {'q': query.strip(), 'limit': max(1, min(limit, 100))}
        return self._get('/v1/search/companies', params=params)

    def list_sectors(self) -> Dict[str, Any]:
        """List all market sectors available on Screener."""
        return self._get('/v1/sectors')

    def get_sector(self, sector_slug: str, page: int = 1, limit: int = 50,
                   include_all_pages: bool = False) -> Dict[str, Any]:
        """Get list of companies in a specific sector."""
        params = {'page': page, 'limit': limit, 'include_all_pages': include_all_pages}
        return self._get(f"/v1/sectors/{sector_slug}", params=params)

    def list_screens(self, page: int = 1, include_all_pages: bool = False,
                     max_pages: Optional[int] = None) -> Dict[str, Any]:
        """List available public stock screens."""
        params: Dict[str, Any] = {'page': page, 'include_all_pages': include_all_pages}
        if max_pages is not None:
            params['max_pages'] = max_pages
        return self._get('/v1/screens', params=params)

    def get_screen(self, screen_id: int, slug: str, page: int = 1,
                   limit: int = 50, include_all_pages: bool = False) -> Dict[str, Any]:
        """Get detailed results for a specific screen."""
        params = {'page': page, 'limit': limit, 'include_all_pages': include_all_pages}
        return self._get(f"/v1/screens/{screen_id}/{slug}", params=params)

    def prewarm(self, sector_slugs: Optional[List[str]] = None,
                screen_refs: Optional[List[Dict]] = None,
                pages_per_target: int = 2) -> Dict[str, Any]:
        """Pre-warm cache for faster subsequent access to sectors and screens."""
        payload = {
            "sector_slugs": sector_slugs or [],
            "screen_refs": screen_refs or [],
            "pages_per_target": pages_per_target
        }
        url = self.base_url + "/v1/prewarm"
        response = self.session.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """Check if the Screener API is reachable."""
        try:
            self._get('/v1/sectors')
            return True
        except Exception:
            return False


# Global instance
screener = ScreenerAPI()

# Convenience tool functions for AG2
def get_company_fundamentals(symbol: str) -> dict:
    """Fetch comprehensive fundamental data for an Indian stock from Screener.in, including company overview, key ratios, and financials."""
    return screener.get_company(symbol)

def get_company_ratios(symbol: str) -> dict:
    """Get detailed financial ratios for a company (e.g., P/E, P/B, ROE, debt-to-equity)."""
    return screener.get_company_tab(symbol, 'ratios')

def get_company_financials(symbol: str, statement: str = 'profit-loss') -> dict:
    """
    Get financial statements for a company.

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE').
        statement: One of 'profit-loss', 'balance-sheet', 'cash-flow', 'quarters'.

    Returns:
        Financial statement data as dictionary.
    """
    return screener.get_company_tab(symbol, statement)

def get_company_analysis(symbol: str) -> dict:
    """Get technical analysis and peer comparison for a company."""
    return screener.get_company_tab(symbol, 'analysis')

def get_company_peers(symbol: str) -> dict:
    """Get peer companies for comparison."""
    return screener.get_company_tab(symbol, 'peers')

def search_companies(query: str, limit: int = 10) -> dict:
    """Search for Indian companies by name or keyword. Use this to resolve partial names."""
    return screener.search_companies(query, limit)

def compare_companies(symbols: list) -> dict:
    """Compare fundamental metrics across multiple companies. Provide a list of stock symbols."""
    return screener.compare_companies(symbols)

def get_sector_companies(sector_slug: str, include_all: bool = False) -> dict:
    """Get list of companies in a given sector (e.g., 'it-software', 'pharmaceuticals-biotechnology')."""
    return screener.get_sector(sector_slug, include_all_pages=include_all)

def list_sectors() -> dict:
    """List all market sectors available on Screener.in."""
    return screener.list_sectors()

def list_available_screens() -> dict:
    """List publicly available stock screens (e.g., 'High PE', 'Low Debt', 'Multibagger', etc.)."""
    return screener.list_screens(page=1)

def get_screen_results(screen_id: int, slug: str, limit: int = 50) -> dict:
    """Get results of a specific screen. Requires screen_id and slug from list_available_screens()."""
    return screener.get_screen(screen_id, slug, limit=limit)
