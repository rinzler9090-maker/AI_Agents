"""
Alpha Vantage API integration for fetching market news and sentiment.
Uses the Alpha Vantage NEWS_SENTIMENT endpoint to get real-time news
for Indian stocks as a supplementary news source alongside yfinance.

Requires:
    ALPHA_VANTAGE_API_KEY in .env file (get free key at https://www.alphavantage.co/support/#api-key)

Usage in .env:
    ALPHA_VANTAGE_API_KEY=your_api_key_here
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

# Try to import requests - it's a common dependency
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Alpha Vantage free tier: 5 calls per minute, 500 calls per day
# We use a simple rate limiter to stay within limits
_LAST_CALL_TIME = 0.0
_MIN_INTERVAL = 12.5  # 60s / 5 calls = 12 seconds between calls (with buffer)


def _rate_limit():
    """
    Ensure we don't exceed Alpha Vantage's free tier rate limit (5 calls/minute).
    Waits if we're calling too fast.
    """
    global _LAST_CALL_TIME
    now = time.time()
    elapsed = now - _LAST_CALL_TIME
    if elapsed < _MIN_INTERVAL:
        sleep_time = _MIN_INTERVAL - elapsed
        logger.debug(f"Alpha Vantage rate limit: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    _LAST_CALL_TIME = time.time()


def get_api_key() -> Optional[str]:
    """
    Get the Alpha Vantage API key from environment variables.

    Returns:
        API key string or None if not configured.
    """
    return os.getenv("ALPHA_VANTAGE_API_KEY")


def is_available() -> bool:
    """
    Check if Alpha Vantage is configured and usable.

    Returns:
        True if API key is set and requests is available.
    """
    return bool(get_api_key()) and REQUESTS_AVAILABLE


def _call_api(function: str, **params) -> Optional[Dict[str, Any]]:
    """
    Make a rate-limited call to the Alpha Vantage API.

    Args:
        function: Alpha Vantage function name (e.g., 'NEWS_SENTIMENT').
        **params: Additional query parameters.

    Returns:
        Parsed JSON response or None on failure.
    """
    api_key = get_api_key()
    if not api_key:
        logger.warning("Alpha Vantage API key not configured. Set ALPHA_VANTAGE_API_KEY in .env")
        return None

    if not REQUESTS_AVAILABLE:
        logger.warning("'requests' library not installed. Install with: pip install requests")
        return None

    _rate_limit()

    url = "https://www.alphavantage.co/query"
    params['function'] = function
    params['apikey'] = api_key

    try:
        logger.debug(f"Calling Alpha Vantage: {function}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for API error messages
        if "Error Message" in data:
            logger.error(f"Alpha Vantage API error: {data['Error Message']}")
            return None
        if "Note" in data:
            logger.warning(f"Alpha Vantage API note: {data['Note']}")
            return None

        return data
    except requests.exceptions.Timeout:
        logger.warning(f"Alpha Vantage API timeout for function={function}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Alpha Vantage API request failed for function={function}: {e}")
        return None
    except ValueError as e:
        logger.warning(f"Alpha Vantage API response parse error: {e}")
        return None


def _sanitize_ticker(symbol: str) -> str:
    """
    Sanitize a ticker symbol for Alpha Vantage's NEWS_SENTIMENT endpoint.
    
    Alpha Vantage only allows alphanumeric characters, colons, underscores, 
    and hyphens in ticker symbols. Strips out exchange suffixes like .BSE, .NS.
    
    Args:
        symbol: Raw ticker symbol (e.g., 'ADANIPOWER.BSE', 'RELIANCE.NS').
    
    Returns:
        Sanitized ticker (e.g., 'ADANIPOWER', 'RELIANCE').
    """
    import re
    # Remove exchange suffixes (.BSE, .NS, .BO, etc.)
    symbol = re.sub(r'\.[A-Za-z]+$', '', symbol)
    # Keep only allowed characters
    symbol = re.sub(r'[^A-Za-z0-9_:.-]', '', symbol)
    return symbol.strip().upper()


def get_market_news(
    symbol: Optional[str] = None,
    topics: Optional[str] = None,
    limit: int = 10,
    time_from: Optional[str] = None,
    sort: str = "LATEST"
) -> List[Dict[str, Any]]:
    """
    Fetch market news and sentiment from Alpha Vantage NEWS_SENTIMENT endpoint.

    This is the PRIMARY use case for Alpha Vantage in this project.
    Provides richer news data than yfinance, including:
      - Overall sentiment score per article
      - Relevance score to the queried ticker
      - Source diversity (multiple publishers)
      - Topic categorization

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'ADANIPOWER').
                If None, fetches general market news.
                Exchange suffixes like .BSE, .NS are automatically stripped.
        topics: Comma-separated topic filters (e.g., 'technology,earnings,ipo').
                See Alpha Vantage docs for full list.
        limit: Maximum number of news items to return (default: 10, max: 50).
        time_from: Optional start time in YYYYMMDDTHHMM format (e.g., '20240101T0000').
        sort: Sort order - 'LATEST' or 'EARLIEST' or 'RELEVANCE' (default: 'LATEST').

    Returns:
        List of news articles with title, summary, source, sentiment, etc.
        Returns empty list on failure.
    """
    params = {
        "sort": sort,
    }

    if symbol:
        # Sanitize ticker: strip exchange suffixes (.BSE, .NS) and invalid chars
        clean_symbol = _sanitize_ticker(symbol)
        params["tickers"] = clean_symbol
        logger.debug(f"Alpha Vantage news ticker: '{symbol}' -> '{clean_symbol}'")


    if topics:
        params["topics"] = topics

    if time_from:
        params["time_from"] = time_from

    data = _call_api("NEWS_SENTIMENT", **params)
    if not data:
        return []

    try:
        feed = data.get("feed", [])
        if not feed:
            logger.debug(f"No news articles found for symbol={symbol}")
            return []

        articles = []
        for item in feed[:limit]:
            # Extract ticker-specific sentiment if available
            ticker_sentiment = None
            for ts in item.get("ticker_sentiment", []):
                if symbol and (ts.get("ticker", "").upper() == symbol.upper() or
                               symbol.upper() in ts.get("ticker", "").upper()):
                    ticker_sentiment = {
                        'score': _safe_float(ts.get("ticker_sentiment_score")),
                        'label': ts.get("ticker_sentiment_label", ""),
                    }
                    break

            # Parse timestamp
            published = item.get("time_published", "")
            try:
                # Alpha Vantage format: YYYYMMDDTHHMMSS
                if published and len(published) >= 14:
                    dt = datetime.strptime(published[:14], "%Y%m%dT%H%M%S")
                    timestamp = dt.isoformat()
                else:
                    timestamp = datetime.now().isoformat()
            except (ValueError, IndexError):
                timestamp = datetime.now().isoformat()

            article = {
                'title': item.get("title", ""),
                'summary': item.get("summary", ""),
                'source': item.get("source", "Alpha Vantage"),
                'authors': item.get("authors", []),
                'timestamp': timestamp,
                'url': item.get("url", ""),
                'overall_sentiment_score': _safe_float(item.get("overall_sentiment_score")),
                'overall_sentiment_label': item.get("overall_sentiment_label", ""),
                'ticker_sentiment': ticker_sentiment,
                'topics': [t.get("topic", "") for t in item.get("topics", [])],
                'type': 'stock_specific' if symbol else 'market',
                'source_api': 'Alpha Vantage',
            }
            articles.append(article)

        logger.info(f"Fetched {len(articles)} news articles from Alpha Vantage for {symbol or 'general market'}")
        return articles

    except (ValueError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse Alpha Vantage news response: {e}")
        return []


def get_news_for_sentiment_analyst(symbol: str, limit: int = 10) -> Dict[str, Any]:
    """
    Fetch news specifically formatted for the Sentiment Analyst agent.
    Includes sentiment scores and topic categorization.

    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'ADANIPOWER').
                Exchange suffixes (.BSE, .NS) are automatically stripped.
        limit: Maximum number of articles.

    Returns:
        Dict with 'news' list and metadata, or {'error': ...} on failure.
    """
    # Try stock-specific news first (sanitizer strips .BSE/.NS suffixes)
    articles = get_market_news(symbol=symbol, limit=limit)

    # If no results, try general market news
    if not articles:
        articles = get_market_news(limit=limit)

    if not articles:
        return {
            'error': 'No news available from Alpha Vantage',
            'source': 'Alpha Vantage',
            'articles': []
        }

    return {
        'source': 'Alpha Vantage',
        'fetched_at': datetime.now().isoformat(),
        'articles': articles,
        'total': len(articles),
    }



def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float, returning None if not possible."""
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (ValueError, TypeError):
        return None
