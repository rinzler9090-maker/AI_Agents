"""
Data Prefetcher: Fetches ALL real market data BEFORE agent conversations start.
This is the foundation of the anti-hallucination strategy.
All numerical values in reports come from here, NOT from LLM generation.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.tools.indian_market_data import fetcher
from src.tools.screener_api import get_company_fundamentals, get_company_ratios, get_company_financials
from src.tools.alpha_vantage import is_available as av_is_available
from src.tools.alpha_vantage import get_news_for_sentiment_analyst as av_get_news



logger = logging.getLogger(__name__)


def _parse_screener_value(value_str: str) -> Any:
    """
    Parse a Screener API string value into a numeric value.
    
    Examples:
        "10.8%" -> 10.8
        "₹1,39,940Cr." -> 1399400000000 (Cr = crore = 10^7)
        "₹438" -> 438
        "36.9" -> 36.9
        "0.51%" -> 0.51
        "₹465/342" -> "465/342" (keep as string for High/Low)
        "-0.96" -> -0.96
    """
    if value_str is None:
        return None
    s = str(value_str).strip()
    if not s:
        return None
    
    # Check if it's a range like "465/342"
    if '/' in s and not s.startswith('0'):
        return s  # Keep ranges as strings
    
    # Remove ₹ symbol
    s = s.replace('₹', '').replace(',', '')
    
    # Check for Cr (crore = 10^7)
    multiplier = 1
    if s.endswith('Cr.'):
        s = s[:-3].strip()
        multiplier = 10000000  # 1 crore = 10^7
    elif s.endswith('L'):
        s = s[:-1].strip()
        multiplier = 100000  # 1 lakh = 10^5
    
    # Remove % sign
    is_percent = False
    if s.endswith('%'):
        s = s[:-1].strip()
        is_percent = True
    
    try:
        val = float(s) * multiplier
        return val
    except (ValueError, TypeError):
        return value_str  # Return original string if can't parse


def _extract_table_value(rows: List[List], row_label: str, column_index: int = -1) -> Any:
    """
    Extract the latest value from a table row by label.
    
    Args:
        rows: List of rows, each row is [label, value1, value2, ...]
        row_label: Label to search for (case-insensitive, partial match)
        column_index: Which column to get (-1 = last column = most recent)
    
    Returns:
        Parsed value or None
    """
    if not rows:
        return None
    
    for row in rows:
        if not row or not row[0]:
            continue
        label = str(row[0]).strip().lower()
        search = row_label.lower()
        # Match if label starts with or contains the search term
        if label.startswith(search) or search in label:
            if column_index == -1:
                val = row[-1]  # Most recent (last column)
            elif column_index < len(row):
                val = row[column_index]
            else:
                val = row[-1]
            return _parse_screener_value(val)
    
    return None


def parse_screener_company_data(raw_data: Dict) -> Dict[str, Any]:
    """
    Parse the raw Screener API company response into structured key-value pairs.
    
    The Screener API returns data in two formats:
    1. overview.top_ratios: dict with keys like "ROCE", "ROE", "Stock P/E", etc.
    2. profit_loss, balance_sheet, cash_flow, ratios: table format with columns/rows
    
    Args:
        raw_data: Raw response from get_company_fundamentals()
    
    Returns:
        Dict with parsed numeric values
    """
    result = {}
    
    if not raw_data or 'error' in raw_data:
        return result
    
    data = raw_data.get('data', raw_data)
    
    # 1. Parse overview.top_ratios
    overview = data.get('overview', {})
    if overview:
        result['company_name'] = overview.get('company_name', '')
        top_ratios = overview.get('top_ratios', {})
        if top_ratios:
            # Map Screener keys to formatter keys
            ratio_mapping = {
                'Market Cap': 'market_cap',
                'Current Price': 'current_price',
                'Stock P/E': 'pe_ratio',
                'Book Value': 'book_value',
                'Dividend Yield': 'dividend_yield',
                'ROCE': 'roce',
                'ROE': 'roe',
                'Face Value': 'face_value',
                'High / Low': 'high_low',
            }
            for screener_key, formatter_key in ratio_mapping.items():
                val = top_ratios.get(screener_key)
                if val:
                    result[formatter_key] = _parse_screener_value(val)
    
    # 2. Parse profit_loss table
    pl = data.get('profit_loss', {})
    if pl and 'rows' in pl:
        rows = pl['rows']
        result['revenue'] = _extract_table_value(rows, 'Sales')
        result['operating_profit'] = _extract_table_value(rows, 'Operating Profit')
        result['opm'] = _extract_table_value(rows, 'OPM')
        result['net_income'] = _extract_table_value(rows, 'Net Profit')
        result['eps'] = _extract_table_value(rows, 'EPS')
        result['interest'] = _extract_table_value(rows, 'Interest')
        result['depreciation'] = _extract_table_value(rows, 'Depreciation')
        result['profit_before_tax'] = _extract_table_value(rows, 'Profit before tax')
    
    # 3. Parse balance_sheet table
    bs = data.get('balance_sheet', {})
    if bs and 'rows' in bs:
        rows = bs['rows']
        equity = _extract_table_value(rows, 'Equity Capital')
        reserves = _extract_table_value(rows, 'Reserves')
        borrowings = _extract_table_value(rows, 'Borrowings')
        total_liabilities = _extract_table_value(rows, 'Total Liabilities')
        fixed_assets = _extract_table_value(rows, 'Fixed Assets')
        
        if equity is not None and reserves is not None:
            result['net_worth'] = (equity if isinstance(equity, (int, float)) else 0) + \
                                  (reserves if isinstance(reserves, (int, float)) else 0)
        if borrowings is not None and result.get('net_worth'):
            b_val = borrowings if isinstance(borrowings, (int, float)) else 0
            nw_val = result['net_worth'] if isinstance(result['net_worth'], (int, float)) else 1
            if nw_val != 0:
                result['debt_to_equity'] = round(b_val / nw_val, 2)
    
    # 4. Parse cash_flow table
    cf = data.get('cash_flow', {})
    if cf and 'rows' in cf:
        rows = cf['rows']
        result['free_cash_flow'] = _extract_table_value(rows, 'Free Cash Flow')
        result['cash_from_ops'] = _extract_table_value(rows, 'Cash from Operating')
    
    # 5. Parse ratios table for additional ratios
    rat = data.get('ratios', {})
    if rat and 'rows' in rat:
        rows = rat['rows']
        result['roce'] = result.get('roce') or _extract_table_value(rows, 'ROCE')
        # Current ratio might be in ratios table
        result['current_ratio'] = _extract_table_value(rows, 'Current Ratio')
    
    return result


def prefetch_all_data(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
    """
    Fetch ALL real market data upfront before any agent conversation.
    This data is used to:
    1. Inject into agent system messages for grounding
    2. Override any hallucinated values in the final report
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE')
        exchange: 'NSE' or 'BSE'
    
    Returns:
        Dictionary with all fetched data, structured for report generation
    """
    print(f"\n📡 Pre-fetching real market data for {symbol}...")
    
    data = {
        'symbol': symbol,
        'exchange': exchange,
        'fetched_at': datetime.now().isoformat(),
        'fundamental': {},
        'technical': {},
        'sentiment': {},
        'risk': {},
        'errors': []
    }
    
    # 1. Fetch technical indicators (yfinance) - this gives us current_price, RSI, MACD, etc.
    try:
        print(f"  Fetching technical indicators from yfinance...")
        tech_data = fetcher.calculate_technical_indicators(symbol, exchange)
        if 'error' not in tech_data:
            data['technical'] = tech_data
            print(f"    ✓ Current price: ₹{tech_data.get('current_price', 'N/A')}")
            print(f"    ✓ RSI: {tech_data.get('rsi', {}).get('value', 'N/A')}")
            print(f"    ✓ Trend: {tech_data.get('trend', 'N/A')}")
        else:
            data['errors'].append(f"Technical data: {tech_data['error']}")
            print(f"    ⚠ Technical data error: {tech_data['error']}")
    except Exception as e:
        data['errors'].append(f"Technical data exception: {e}")
        logger.warning(f"Failed to fetch technical data: {e}")
    
    # 2. Fetch stock data (yfinance) - gives us beta, 52w high/low, market cap, etc.
    try:
        print(f"  Fetching stock fundamentals from yfinance...")
        stock_data = fetcher.get_stock_data(symbol, exchange, period='1y')
        if 'error' not in stock_data:
            data['risk'] = {
                'beta': stock_data.get('beta'),
                '52w_high': stock_data.get('52w_high'),
                '52w_low': stock_data.get('52w_low'),
                'market_cap': stock_data.get('market_cap'),
                'pe_ratio': stock_data.get('pe_ratio'),
                'pb_ratio': stock_data.get('pb_ratio'),
                'dividend_yield': stock_data.get('dividend_yield'),
                'company_name': stock_data.get('company_name', symbol),
                'sector': stock_data.get('sector', 'N/A'),
                'industry': stock_data.get('industry', 'N/A'),
            }
            print(f"    ✓ Company: {stock_data.get('company_name', symbol)}")
            print(f"    ✓ Beta: {stock_data.get('beta', 'N/A')}")
            print(f"    ✓ 52W Range: {stock_data.get('52w_low', 'N/A')} - {stock_data.get('52w_high', 'N/A')}")
        else:
            data['errors'].append(f"Stock data: {stock_data['error']}")
            print(f"    ⚠ Stock data error: {stock_data['error']}")
    except Exception as e:
        data['errors'].append(f"Stock data exception: {e}")
        logger.warning(f"Failed to fetch stock data: {e}")
    
    # 3. Fetch Screener.in fundamental data
    try:
        print(f"  Fetching Screener.in fundamental data...")
        screener_data = get_company_fundamentals(symbol)
        if screener_data and 'error' not in screener_data:
            data['fundamental']['screener'] = screener_data
            print(f"    ✓ Screener data received")
        else:
            data['errors'].append(f"Screener data: {screener_data.get('error', 'Unknown error')}")
            print(f"    ⚠ Screener data error")
    except Exception as e:
        data['errors'].append(f"Screener data exception: {e}")
        logger.warning(f"Failed to fetch Screener data: {e}")
    
    # 4. Fetch Screener.in ratios
    try:
        print(f"  Fetching Screener.in ratios...")
        ratios_data = get_company_ratios(symbol)
        if ratios_data and 'error' not in ratios_data:
            data['fundamental']['ratios'] = ratios_data
            print(f"    ✓ Ratios received")
    except Exception as e:
        data['errors'].append(f"Ratios exception: {e}")
        logger.warning(f"Failed to fetch ratios: {e}")
    
    # 5. Fetch Screener.in financials (profit-loss, balance-sheet)
    try:
        print(f"  Fetching Screener.in financials...")
        pl_data = get_company_financials(symbol, 'profit-loss')
        if pl_data and 'error' not in pl_data:
            data['fundamental']['profit-loss'] = pl_data
            print(f"    ✓ P&L data received")
        bs_data = get_company_financials(symbol, 'balance-sheet')
        if bs_data and 'error' not in bs_data:
            data['fundamental']['balance-sheet'] = bs_data
            print(f"    ✓ Balance sheet received")
        cf_data = get_company_financials(symbol, 'cash-flow')
        if cf_data and 'error' not in cf_data:
            data['fundamental']['cash-flow'] = cf_data
            print(f"    ✓ Cash flow received")
    except Exception as e:
        data['errors'].append(f"Financials exception: {e}")
        logger.warning(f"Failed to fetch financials: {e}")
    
    # 6. Fetch market news (Alpha Vantage preferred, yfinance fallback)
    if av_is_available():
        try:
            print(f"  Fetching market news from Alpha Vantage...")
            av_news = av_get_news(symbol, limit=10)
            if av_news and 'error' not in av_news and av_news.get('articles'):
                data['sentiment']['news'] = av_news['articles']
                print(f"    ✓ {len(av_news['articles'])} news articles with sentiment scores")
            else:
                logger.debug(f"Alpha Vantage news not available: {av_news.get('error', 'unknown')}")
                print(f"    ⚠ No Alpha Vantage news available, trying yfinance...")
                # Fallback to yfinance
                news = fetcher.get_market_news(symbol, limit=5)
                if news:
                    data['sentiment']['news'] = news
                    print(f"    ✓ {len(news)} news articles from yfinance")
        except Exception as e:
            data['errors'].append(f"Alpha Vantage news exception: {e}")
            logger.warning(f"Failed to fetch Alpha Vantage news: {e}")
            # Fallback to yfinance
            try:
                news = fetcher.get_market_news(symbol, limit=5)
                if news:
                    data['sentiment']['news'] = news
                    print(f"    ✓ {len(news)} news articles from yfinance (fallback)")
            except Exception as e2:
                data['errors'].append(f"yfinance news fallback exception: {e2}")
    else:
        # Alpha Vantage not configured, use yfinance
        try:
            print(f"  Fetching market news from yfinance...")
            news = fetcher.get_market_news(symbol, limit=5)
            if news:
                data['sentiment']['news'] = news
                print(f"    ✓ {len(news)} news articles fetched")
        except Exception as e:
            data['errors'].append(f"News exception: {e}")
            logger.warning(f"Failed to fetch news: {e}")
    
    # 7. Fetch sector performance
    try:
        print(f"  Fetching sector performance...")
        sector_data = fetcher.get_sector_performance()
        if sector_data and 'sectors' in sector_data:
            data['sentiment']['sectors'] = sector_data['sectors']
            print(f"    ✓ Sector data received")
    except Exception as e:
        data['errors'].append(f"Sector data exception: {e}")
        logger.warning(f"Failed to fetch sector data: {e}")
    
    # 8. Fetch market summary
    try:
        print(f"  Fetching market summary...")
        market_summary = fetcher.get_market_summary()
        if market_summary:
            data['sentiment']['market_summary'] = market_summary
            print(f"    ✓ Market summary received")
    except Exception as e:
        data['errors'].append(f"Market summary exception: {e}")
        logger.warning(f"Failed to fetch market summary: {e}")
    
    print(f"  ✅ Data pre-fetch complete ({len(data['errors'])} errors)")
    return data



def build_grounding_context(data: Dict[str, Any]) -> str:
    """
    Build a grounding context string from pre-fetched data.
    This is injected into agent system messages so they have the real numbers.
    
    Args:
        data: Pre-fetched data dictionary
    
    Returns:
        Formatted string with all real data values
    """
    lines = []
    lines.append("=" * 70)
    lines.append("📊 REAL MARKET DATA (ground truth - use these exact values)")
    lines.append("=" * 70)
    
    tech = data.get('technical', {})
    risk = data.get('risk', {})
    
    # Current Price (MOST IMPORTANT - this is what gets hallucinated most)
    current_price = tech.get('current_price', 'N/A')
    lines.append(f"\n📍 CURRENT PRICE: ₹{current_price}")
    
    # Company Info
    company_name = risk.get('company_name', data.get('symbol', 'N/A'))
    sector = risk.get('sector', 'N/A')
    industry = risk.get('industry', 'N/A')
    lines.append(f"   Company: {company_name}")
    lines.append(f"   Sector: {sector}")
    lines.append(f"   Industry: {industry}")
    
    # Technical Indicators
    lines.append(f"\n📉 TECHNICAL INDICATORS (from yfinance):")
    
    rsi = tech.get('rsi', {})
    if rsi:
        lines.append(f"   RSI (14): {rsi.get('value', 'N/A')} - {rsi.get('signal', '')}")
    
    macd = tech.get('macd', {})
    if macd:
        lines.append(f"   MACD: Line={macd.get('macd_line', 'N/A')}, Signal={macd.get('signal_line', 'N/A')}, Histogram={macd.get('histogram', 'N/A')}")
        lines.append(f"   MACD Signal: {macd.get('signal', '')}")
    
    ma = tech.get('moving_averages', {})
    if ma:
        lines.append(f"   MA(20): ₹{ma.get('ma_20', 'N/A')}")
        lines.append(f"   MA(50): ₹{ma.get('ma_50', 'N/A')}")
        lines.append(f"   MA(200): ₹{ma.get('ma_200', 'N/A')}")
    
    bb = tech.get('bollinger_bands', {})
    if bb:
        lines.append(f"   Bollinger Bands: Upper=₹{bb.get('upper', 'N/A')}, Middle=₹{bb.get('middle', 'N/A')}, Lower=₹{bb.get('lower', 'N/A')}")
        lines.append(f"   Band Width: {bb.get('width_pct', 'N/A')}%")
    
    vol = tech.get('volume_analysis', {})
    if vol:
        lines.append(f"   Volume: Avg={vol.get('avg_volume', 'N/A')}, Recent={vol.get('recent_volume', 'N/A')}, Ratio={vol.get('volume_ratio', 'N/A')}")
        lines.append(f"   Volume Trend: {vol.get('trend', '')}")
    
    sr = tech.get('support_resistance', {})
    if sr:
        lines.append(f"   Support/Resistance: Recent High=₹{sr.get('recent_high', 'N/A')}, Recent Low=₹{sr.get('recent_low', 'N/A')}")
    
    trend = tech.get('trend', '')
    if trend:
        lines.append(f"   Overall Trend: {trend}")
    
    # Risk Data
    lines.append(f"\n⚠️ RISK DATA (from yfinance):")
    lines.append(f"   Beta: {risk.get('beta', 'N/A')}")
    lines.append(f"   52-Week High: ₹{risk.get('52w_high', 'N/A')}")
    lines.append(f"   52-Week Low: ₹{risk.get('52w_low', 'N/A')}")
    lines.append(f"   Market Cap: {risk.get('market_cap', 'N/A')}")
    lines.append(f"   P/E Ratio: {risk.get('pe_ratio', 'N/A')}")
    lines.append(f"   P/B Ratio: {risk.get('pb_ratio', 'N/A')}")
    
    # News
    news_list = data.get('sentiment', {}).get('news', [])
    if news_list:
        lines.append(f"\n📰 RECENT NEWS:")
        for i, item in enumerate(news_list[:5], 1):
            lines.append(f"   {i}. {item.get('title', 'Untitled')}")
            lines.append(f"      Source: {item.get('source', 'Unknown')} | {item.get('timestamp', 'N/A')}")
    
    # Sector Performance
    sectors = data.get('sentiment', {}).get('sectors', {})
    if sectors:
        lines.append(f"\n🏭 SECTOR PERFORMANCE:")
        for sector_name, perf in sectors.items():
            arrow = "🟢" if perf > 0 else "🔴"
            lines.append(f"   {arrow} {sector_name}: {perf:+.2f}%")
    
    lines.append("\n" + "=" * 70)
    lines.append("⚠️ CRITICAL RULE: Use ONLY the values above for prices and metrics.")
    lines.append("   Do NOT generate prices from your training data.")
    lines.append("=" * 70)
    
    return "\n".join(lines)
