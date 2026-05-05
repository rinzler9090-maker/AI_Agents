"""
Tools for fetching Indian stock market data.
Supports NSE and BSE data via yfinance with real news, sector performance, and technical indicators.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class IndianMarketDataFetcher:
    """Fetches real-time and historical data for Indian stocks."""

    EXCHANGE_SUFFIXES = {
        'NSE': '.NS',
        'BSE': '.BO'
    }

    INDICES = {
        'NIFTY 50': '^NSEI',
        'BANK NIFTY': '^NSEBANK',
        'NIFTY IT': '^CNXIT',
        'NIFTY PHARMA': '^CNXPHARMA',
        'NIFTY AUTO': '^CNXAUTO',
        'NIFTY METAL': '^CNXMETAL',
        'NIFTY REALTY': '^CNXREALTY',
        'NIFTY FMCG': '^CNXFMCG',
        'SENSEX': '^BSESN'
    }

    def __init__(self):
        # NOTE: Do NOT set a custom session. yfinance now requires curl_cffi internally.
        pass

    def get_stock_data(self, symbol: str, exchange: str = 'NSE',
                       period: str = '6mo') -> Dict[str, Any]:
        """
        Fetch historical stock data for an Indian stock.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE').
            exchange: 'NSE' or 'BSE'.
            period: Data period (e.g., '1mo', '3mo', '6mo', '1y', 'max').

            
        Returns:
            Dictionary with stock data including price, volume, fundamentals.
        """
        try:
            exchange_key = exchange.upper()
            if exchange_key not in self.EXCHANGE_SUFFIXES:
                return {'error': f'Unsupported exchange "{exchange}". Use NSE or BSE.'}

            ticker_symbol = symbol.upper() + self.EXCHANGE_SUFFIXES[exchange_key]
            stock = yf.Ticker(ticker_symbol)
            hist = stock.history(period=period)
            info = stock.info

            if hist.empty:
                return {
                    'error': f'No historical data found for {symbol} on {exchange}',
                    'symbol': symbol,
                    'exchange': exchange
                }

            latest = hist.iloc[-1]

            result = {
                'symbol': symbol,
                'exchange': exchange,
                'currency': info.get('currency', 'INR'),
                'current_price': info.get('currentPrice', round(float(latest['Close']), 2)),
                'day_high': info.get('dayHigh', round(float(latest['High']), 2)),
                'day_low': info.get('dayLow', round(float(latest['Low']), 2)),
                'volume': info.get('volume', int(latest['Volume'])),
                'market_cap': info.get('marketCap'),
                '52w_high': info.get('fiftyTwoWeekHigh'),
                '52w_low': info.get('fiftyTwoWeekLow'),
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'beta': info.get('beta'),
                'company_name': info.get('longName', symbol),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'historical_data': hist.tail(30).to_dict('records') if not hist.empty else [],
            }
            return result
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
            return {'error': str(e), 'symbol': symbol, 'exchange': exchange}

    def get_index_data(self, index_name: str, period: str = '6mo') -> Dict[str, Any]:
        """
        Fetch data for Indian market indices.

        Args:
            index_name: Index name (e.g., 'NIFTY 50', 'SENSEX', 'BANK NIFTY').
            period: Data period.

        Returns:
            Dictionary with index data.
        """
        try:
            if index_name not in self.INDICES:
                return {
                    'error': f'Index "{index_name}" not supported.',
                    'supported_indices': list(self.INDICES.keys())
                }

            ticker = yf.Ticker(self.INDICES[index_name])
            hist = ticker.history(period=period)

            if hist.empty:
                return {'error': f'No data available for index {index_name}', 'index_name': index_name}

            latest = hist.iloc[-1]
            prev_close = hist.iloc[-2]['Close'] if len(hist) > 1 else latest['Open']
            change = float(latest['Close'] - prev_close)
            change_pct = float((change / prev_close) * 100)

            return {
                'index_name': index_name,
                'ticker': self.INDICES[index_name],
                'current_value': round(float(latest['Close']), 2),
                'change': round(change, 2),
                'change_pct': round(change_pct, 2),
                'day_high': round(float(latest['High']), 2),
                'day_low': round(float(latest['Low']), 2),
                'volume': int(latest['Volume']),
                'historical_data': hist.tail(30).to_dict('records') if not hist.empty else [],
            }
        except Exception as e:
            logger.error(f"Error fetching index data for {index_name}: {e}")
            return {'error': str(e), 'index_name': index_name}

    def get_multiple_stocks(self, symbols: List[str], exchange: str = 'NSE') -> Dict[str, Any]:
        """Fetch data for multiple stocks at once."""
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_stock_data(symbol, exchange)
        return results

    def calculate_technical_indicators(self, symbol: str, exchange: str = 'NSE') -> Dict[str, Any]:
        """
        Calculate comprehensive technical indicators for a stock.

        Includes: RSI, MACD, Moving Averages (20, 50, 200), Volume Analysis, Pivot Points, Bollinger Bands.

        Args:
            symbol: Stock symbol.
            exchange: 'NSE' or 'BSE'.

        Returns:
            Dictionary with all technical indicators.
        """
        try:
            exchange_key = exchange.upper()
            if exchange_key not in self.EXCHANGE_SUFFIXES:
                return {'error': f'Unsupported exchange "{exchange}". Use NSE or BSE.'}

            ticker_symbol = symbol.upper() + self.EXCHANGE_SUFFIXES[exchange_key]
            stock = yf.Ticker(ticker_symbol)
            hist = stock.history(period='1y')


            if hist.empty or len(hist) < 20:
                return {'error': f'Insufficient data for {symbol} to calculate technical indicators. Need at least 20 trading days.'}

            close = hist['Close']
            high = hist['High']
            low = hist['Low']
            volume = hist['Volume']
            current_price = float(close.iloc[-1])

            # RSI (14-day)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs.iloc[-1]))) if not pd.isna(rs.iloc[-1]) else 50.0

            # MACD
            exp1 = close.ewm(span=12, adjust=False).mean()
            exp2 = close.ewm(span=26, adjust=False).mean()
            macd_line = float(exp1.iloc[-1] - exp2.iloc[-1])
            signal_line = float((exp1 - exp2).ewm(span=9, adjust=False).mean().iloc[-1])
            histogram = macd_line - signal_line

            # Moving Averages
            ma_20 = float(close.rolling(window=20).mean().iloc[-1])
            ma_50 = float(close.rolling(window=50).mean().iloc[-1]) if len(hist) >= 50 else None
            ma_200 = float(close.rolling(window=200).mean().iloc[-1]) if len(hist) >= 200 else None

            # Bollinger Bands (20-day)
            bb_middle = close.rolling(window=20).mean().iloc[-1]
            bb_std = close.rolling(window=20).std().iloc[-1]
            bb_upper = float(bb_middle + 2 * bb_std)
            bb_lower = float(bb_middle - 2 * bb_std)
            bb_width = float((bb_upper - bb_lower) / bb_middle * 100) if bb_middle != 0 else 0

            # Volume analysis
            avg_volume = float(volume.mean())
            recent_volume = float(volume.iloc[-5:].mean())
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            # Pivot points (using last 30 days)
            period_high = float(high.tail(30).max())
            period_low = float(low.tail(30).min())
            pivot = (period_high + period_low + current_price) / 3
            r1 = 2 * pivot - period_low
            s1 = 2 * pivot - period_high
            r2 = pivot + (period_high - period_low)
            s2 = pivot - (period_high - period_low)

            # Support & Resistance (recent highs/lows)
            recent_high = float(high.tail(20).max())
            recent_low = float(low.tail(20).min())

            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'rsi': {
                    'value': round(rsi, 2),
                    'signal': 'Overbought' if rsi > 70 else ('Oversold' if rsi < 30 else 'Neutral')
                },
                'macd': {
                    'macd_line': round(macd_line, 2),
                    'signal_line': round(signal_line, 2),
                    'histogram': round(histogram, 2),
                    'signal': 'Bullish' if macd_line > signal_line else 'Bearish'
                },
                'moving_averages': {
                    'ma_20': round(ma_20, 2),
                    'ma_50': round(ma_50, 2) if ma_50 else None,
                    'ma_200': round(ma_200, 2) if ma_200 else None
                },
                'bollinger_bands': {
                    'upper': round(bb_upper, 2),
                    'middle': round(float(bb_middle), 2),
                    'lower': round(bb_lower, 2),
                    'width_pct': round(bb_width, 2)
                },
                'volume_analysis': {
                    'avg_volume': int(avg_volume),
                    'recent_volume': int(recent_volume),
                    'volume_ratio': round(volume_ratio, 2),
                    'trend': 'High' if volume_ratio > 1.2 else ('Low' if volume_ratio < 0.8 else 'Normal')
                },
                'pivot_points': {
                    'pivot': round(pivot, 2),
                    'resistance_1': round(r1, 2),
                    'resistance_2': round(r2, 2),
                    'support_1': round(s1, 2),
                    'support_2': round(s2, 2)
                },
                'support_resistance': {
                    'recent_high': round(recent_high, 2),
                    'recent_low': round(recent_low, 2)
                },
                'trend': self._determine_trend(current_price, ma_20, ma_50, ma_200)
            }
        except Exception as e:
            logger.error(f"Error calculating technical indicators for {symbol}: {e}")
            return {'error': str(e), 'symbol': symbol}

    def _determine_trend(self, price: float, ma20: float, ma50: float,
                         ma200: Optional[float]) -> str:
        """Determine the trend based on moving averages alignment."""
        if price > ma20 > ma50:
            if ma200 and price > ma200:
                return 'Strong Uptrend'
            return 'Uptrend'
        elif price < ma20 < ma50:
            if ma200 and price < ma200:
                return 'Strong Downtrend'
            return 'Downtrend'
        else:
            return 'Sideways/Consolidation'

    def get_market_news(self, symbol: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch recent market news for a stock or general market.

        Uses yfinance's news attribute for real news when available.

        Args:
            symbol: Optional stock symbol to get news for. If None, returns general market news.
            limit: Maximum number of news items to return.

        Returns:
            List of news articles with title, source, timestamp, and summary.
        """
        try:
            if symbol:
                ticker = yf.Ticker(symbol.upper() + '.NS')
                news_data = ticker.news
                if news_data:
                    articles = []
                    for item in news_data[:limit]:
                        articles.append({
                            'title': item.get('title', ''),
                            'source': item.get('publisher', 'Yahoo Finance'),
                            'timestamp': datetime.fromtimestamp(
                                item.get('providerPublishTime', datetime.now().timestamp())
                            ).isoformat(),
                            'summary': item.get('summary', ''),
                            'link': item.get('link', ''),
                            'type': 'stock_specific'
                        })
                    return articles

            # Fallback: Get general market news via Nifty 50 ticker
            ticker = yf.Ticker('^NSEI')
            news_data = ticker.news
            if news_data:
                articles = []
                for item in news_data[:limit]:
                    articles.append({
                        'title': item.get('title', ''),
                        'source': item.get('publisher', 'Yahoo Finance'),
                        'timestamp': datetime.fromtimestamp(
                            item.get('providerPublishTime', datetime.now().timestamp())
                        ).isoformat(),
                        'summary': item.get('summary', ''),
                        'link': item.get('link', ''),
                        'type': 'market'
                    })
                return articles

            # Ultimate fallback
            return [{
                'title': 'No recent news available',
                'source': 'System',
                'timestamp': datetime.now().isoformat(),
                'summary': 'Unable to fetch news at this time.',
                'type': 'fallback'
            }]
        except Exception as e:
            logger.warning(f"Could not fetch news: {e}")
            return [{
                'title': 'News fetch failed',
                'source': 'System',
                'timestamp': datetime.now().isoformat(),
                'summary': f'Error fetching news: {str(e)}',
                'type': 'error'
            }]

    def get_sector_performance(self) -> Dict[str, Any]:
        """
        Get performance of major Indian market sectors.

        Returns:
            Dictionary mapping sector names to their percentage change over the last 5 days.
        """
        sectors = {
            'NIFTY BANK': '^NSEBANK',
            'NIFTY IT': '^CNXIT',
            'NIFTY PHARMA': '^CNXPHARMA',
            'NIFTY AUTO': '^CNXAUTO',
            'NIFTY METAL': '^CNXMETAL',
            'NIFTY FMCG': '^CNXFMCG',
            'NIFTY REALTY': '^CNXREALTY'
        }
        performance = {}
        errors = []
        for sector, ticker_symbol in sectors.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period='5d')
                if not hist.empty and len(hist) >= 2:
                    change_pct = float(
                        ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                    )
                    performance[sector] = round(change_pct, 2)
                else:
                    performance[sector] = 0.0
            except Exception as e:
                errors.append(f"{sector}: {e}")
                performance[sector] = 0.0

        result: Dict[str, Any] = {'sectors': performance}
        if errors:
            result['errors'] = errors
        return result

    def get_market_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive market summary including indices, sector performance, and top movers.

        Returns:
            Dictionary with market overview data.
        """
        summary = {
            'indices': {},
            'sectors': {},
            'market_breadth': {},
            'timestamp': datetime.now().isoformat()
        }

        # Get index data
        for name in ['NIFTY 50', 'SENSEX', 'BANK NIFTY']:
            summary['indices'][name] = self.get_index_data(name, period='5d')

        # Get sector performance
        sector_data = self.get_sector_performance()
        summary['sectors'] = sector_data.get('sectors', {})

        return summary


# Global instance
fetcher = IndianMarketDataFetcher()
