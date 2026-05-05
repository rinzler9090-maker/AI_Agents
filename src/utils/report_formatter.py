"""
Report Formatter for Indian Stock Market Multi-Agent System.
Transforms raw analysis output into beautifully formatted, readable reports.
Supports console output, file output (TXT, Markdown), and HTML.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, List


class ReportFormatter:
    """Formats stock analysis results into clean, readable reports."""

    @staticmethod
    def format_header(title: str, width: int = 80) -> str:
        """Create a centered header with decorative borders."""
        line = "=" * width
        padding = (width - len(title) - 2) // 2
        return f"\n{line}\n{' ' * padding}{title}\n{line}\n"

    @staticmethod
    def format_section(title: str, width: int = 80) -> str:
        """Create a section heading."""
        return f"\n{'─' * width}\n  {title}\n{'─' * width}\n"

    @staticmethod
    def format_subsection(title: str) -> str:
        """Create a subsection heading."""
        return f"\n  ▸ {title}"

    @staticmethod
    def format_key_value(key: str, value: Any, indent: int = 4, width: int = 25) -> str:
        """Format a key-value pair with aligned columns."""
        key_str = f"{key}:".ljust(width)
        return f"{' ' * indent}{key_str} {value}"

    @staticmethod
    def format_metric(label: str, value: Any, unit: str = "", 
                      good_range: Optional[tuple] = None,
                      current_value: Optional[float] = None) -> str:
        """
        Format a metric with optional color indicator.
        
        Args:
            label: Metric name
            value: Metric value
            unit: Unit string (e.g., '%', '₹')
            good_range: Optional tuple of (min, max) for "good" range
            current_value: Optional numeric value for comparison
        """
        indicator = ""
        if current_value is not None and good_range:
            if good_range[0] <= current_value <= good_range[1]:
                indicator = " ✅"
            elif current_value < good_range[0]:
                indicator = " ⚠️"
            else:
                indicator = " 🔴"
        
        return f"    {label:<30} {value}{' ' + unit if unit else ''}{indicator}"

    @staticmethod
    def format_table(headers: List[str], rows: List[List[Any]], 
                     title: Optional[str] = None) -> str:
        """
        Format data as a clean ASCII table.
        
        Args:
            headers: Column headers
            rows: List of row data
            title: Optional table title
        """
        if not rows:
            return "    (No data available)\n"
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Build table
        result = ""
        if title:
            result += f"\n    {title}:\n"
        
        # Header separator
        separator = "    " + "+".join("-" * (w + 2) for w in col_widths) + "\n"
        
        # Header row
        header_row = "    |"
        for i, h in enumerate(headers):
            header_row += f" {h:<{col_widths[i]}} |"
        result += separator + header_row + "\n" + separator
        
        # Data rows
        for row in rows:
            data_row = "    |"
            for i, cell in enumerate(row):
                data_row += f" {str(cell):<{col_widths[i]}} |"
            result += data_row + "\n"
        
        result += separator
        return result

    @staticmethod
    def format_recommendation(action: str, confidence: str, 
                              score: float, width: int = 80) -> str:
        """Format the final recommendation prominently."""
        line = "=" * width
        
        # Color/emoji indicators
        action_icons = {
            "BUY": "🟢 BUY",
            "SELL": "🔴 SELL",
            "HOLD": "🟡 HOLD"
        }
        confidence_icons = {
            "High": "★★★",
            "Medium": "★★☆",
            "Low": "★☆☆"
        }
        
        action_display = action_icons.get(action.upper(), action)
        conf_display = confidence_icons.get(confidence, confidence)
        
        return f"""
{line}
  📊 FINAL RECOMMENDATION
{line}
  Action:     {action_display}
  Confidence: {confidence} {conf_display}
  Score:      {score:.1f}/10
{line}
"""

    @staticmethod
    def format_divider(width: int = 80) -> str:
        """Create a divider line."""
        return f"\n{'·' * width}\n"

    @staticmethod
    def format_bullet_list(items: List[str], indent: int = 4) -> str:
        """Format a bulleted list."""
        return "\n".join(f"{' ' * indent}• {item}" for item in items)

    @staticmethod
    def format_numbered_list(items: List[str], indent: int = 4) -> str:
        """Format a numbered list."""
        return "\n".join(f"{' ' * indent}{i+1}. {item}" for i, item in enumerate(items))

    @staticmethod
    def _get_fundamental_val(data: Dict, *keys, default='N/A'):
        """
        Extract a value from fundamental_data, checking multiple possible locations.
        Searches: data itself, data['company'], data['ratios'], data['financials'],
        data['screener'], and data['profit-loss'] for the given keys.
        """
        if not data:
            return default
        # Check each key in order across all possible dict locations
        locations = [
            data,
            data.get('company', {}),
            data.get('ratios', {}),
            data.get('financials', {}),
            data.get('screener', {}),
            data.get('profit-loss', {}),
            data.get('balance-sheet', {}),
            data.get('cash-flow', {}),
        ]
        for key in keys:
            for loc in locations:
                if isinstance(loc, dict):
                    val = loc.get(key)
                    if val is not None:
                        return val
        return default

    @staticmethod
    def format_analysis_summary(
        symbol: str,
        exchange: str,
        analysis_type: str,
        timestamp: str,
        fundamental_data: Optional[Dict] = None,
        technical_data: Optional[Dict] = None,
        sentiment_data: Optional[Dict] = None,
        risk_data: Optional[Dict] = None,
        portfolio_data: Optional[Dict] = None,
        recommendation: Optional[Dict] = None,
        critique: Optional[str] = None,
        raw_conversation: Optional[str] = None,
        agent_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build a complete, beautifully formatted analysis report.
        
        Args:
            symbol: Stock symbol
            exchange: NSE or BSE
            analysis_type: Type of analysis performed
            timestamp: Analysis timestamp
            fundamental_data: Fundamental analysis data
            technical_data: Technical analysis data
            sentiment_data: Sentiment analysis data
            risk_data: Risk assessment data
            portfolio_data: Portfolio context data
            recommendation: Final recommendation dict
            critique: Critic's analysis
            raw_conversation: Raw agent conversation text
            agent_summaries: Dict of agent_name -> analysis_text for individual agent sections
        
        Returns:
            Formatted report string
        """
        width = 80
        report = []
        
        # ===== HEADER =====
        report.append(ReportFormatter.format_header(
            f"INDIAN STOCK MARKET ANALYSIS", width
        ))
        report.append(f"  Stock:      {symbol}")
        report.append(f"  Exchange:   {exchange}")
        report.append(f"  Analysis:   {analysis_type.upper()}")
        report.append(f"  Timestamp:  {timestamp}")
        report.append(f"  Generated:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # ===== FUNDAMENTAL ANALYSIS =====
        if fundamental_data:
            report.append(ReportFormatter.format_section("FUNDAMENTAL ANALYSIS", width))
            
            # Helper to get values from merged data structure
            _fval = lambda *keys: ReportFormatter._get_fundamental_val(fundamental_data, *keys)
            
            # Company Overview
            report.append(ReportFormatter.format_subsection("Company Overview"))
            report.append(ReportFormatter.format_key_value("Company Name", 
                _fval('company_name', 'name', 'longName')))
            report.append(ReportFormatter.format_key_value("Sector", 
                _fval('sector')))
            report.append(ReportFormatter.format_key_value("Industry", 
                _fval('industry')))
            report.append(ReportFormatter.format_key_value("Market Cap", 
                ReportFormatter._format_currency(_fval('market_cap', 'marketCap'))))
            
            # Key Ratios
            report.append(ReportFormatter.format_subsection("Key Ratios"))
            report.append(ReportFormatter.format_metric("P/E Ratio", 
                _fval('pe_ratio', 'trailingPE')))
            report.append(ReportFormatter.format_metric("P/B Ratio", 
                _fval('pb_ratio', 'priceToBook')))
            report.append(ReportFormatter.format_metric("ROE", 
                _fval('roe'), '%'))
            report.append(ReportFormatter.format_metric("ROCE", 
                _fval('roce'), '%'))
            report.append(ReportFormatter.format_metric("Debt/Equity", 
                _fval('debt_to_equity', 'debtToEquity')))
            report.append(ReportFormatter.format_metric("Current Ratio", 
                _fval('current_ratio', 'currentRatio')))
            report.append(ReportFormatter.format_metric("Dividend Yield", 
                _fval('dividend_yield', 'dividendYield'), '%'))
            
            # Financial Health
            report.append(ReportFormatter.format_subsection("Financial Health"))
            report.append(ReportFormatter.format_key_value("Revenue (TTM)", 
                ReportFormatter._format_currency(_fval('revenue', 'totalRevenue'))))
            report.append(ReportFormatter.format_key_value("Net Income", 
                ReportFormatter._format_currency(_fval('net_income', 'netIncomeToCommon'))))
            op_margin_val = _fval('operating_margin', 'operatingMargins', 'opm')
            report.append(ReportFormatter.format_key_value("Operating Margin", 
                f"{op_margin_val}%" if op_margin_val != 'N/A' else 'N/A'))
            profit_margin_val = _fval('profit_margin', 'profitMargins')
            report.append(ReportFormatter.format_key_value("Profit Margin", 
                f"{profit_margin_val}%" if profit_margin_val != 'N/A' else 'N/A'))
            report.append(ReportFormatter.format_key_value("Free Cash Flow", 
                ReportFormatter._format_currency(_fval('free_cash_flow', 'freeCashflow'))))
        
        # ===== TECHNICAL ANALYSIS =====
        if technical_data:
            report.append(ReportFormatter.format_section("TECHNICAL ANALYSIS", width))
            
            # Current Price
            current_price = technical_data.get('current_price', 'N/A')
            report.append(ReportFormatter.format_key_value("Current Price", 
                f"₹{current_price}" if current_price != 'N/A' else 'N/A'))
            
            # RSI
            rsi_data = technical_data.get('rsi', {})
            if rsi_data:
                report.append(ReportFormatter.format_subsection("RSI (14-day)"))
                rsi_val = rsi_data.get('value', 'N/A')
                rsi_signal = rsi_data.get('signal', '')
                report.append(ReportFormatter.format_key_value("Value", rsi_val))
                report.append(ReportFormatter.format_key_value("Signal", rsi_signal))
            
            # MACD
            macd_data = technical_data.get('macd', {})
            if macd_data:
                report.append(ReportFormatter.format_subsection("MACD"))
                report.append(ReportFormatter.format_key_value("MACD Line", macd_data.get('macd_line', 'N/A')))
                report.append(ReportFormatter.format_key_value("Signal Line", macd_data.get('signal_line', 'N/A')))
                report.append(ReportFormatter.format_key_value("Histogram", macd_data.get('histogram', 'N/A')))
                report.append(ReportFormatter.format_key_value("Signal", macd_data.get('signal', '')))
            
            # Moving Averages
            ma_data = technical_data.get('moving_averages', {})
            if ma_data:
                report.append(ReportFormatter.format_subsection("Moving Averages"))
                report.append(ReportFormatter.format_key_value("MA (20-day)", ma_data.get('ma_20', 'N/A')))
                report.append(ReportFormatter.format_key_value("MA (50-day)", ma_data.get('ma_50', 'N/A')))
                report.append(ReportFormatter.format_key_value("MA (200-day)", ma_data.get('ma_200', 'N/A')))
            
            # Bollinger Bands
            bb_data = technical_data.get('bollinger_bands', {})
            if bb_data:
                report.append(ReportFormatter.format_subsection("Bollinger Bands"))
                report.append(ReportFormatter.format_key_value("Upper Band", bb_data.get('upper', 'N/A')))
                report.append(ReportFormatter.format_key_value("Middle Band", bb_data.get('middle', 'N/A')))
                report.append(ReportFormatter.format_key_value("Lower Band", bb_data.get('lower', 'N/A')))
                report.append(ReportFormatter.format_key_value("Width", f"{bb_data.get('width_pct', 'N/A')}%"))
            
            # Volume Analysis
            vol_data = technical_data.get('volume_analysis', {})
            if vol_data:
                report.append(ReportFormatter.format_subsection("Volume Analysis"))
                report.append(ReportFormatter.format_key_value("Avg Volume", vol_data.get('avg_volume', 'N/A')))
                report.append(ReportFormatter.format_key_value("Recent Volume", vol_data.get('recent_volume', 'N/A')))
                report.append(ReportFormatter.format_key_value("Volume Ratio", vol_data.get('volume_ratio', 'N/A')))
                report.append(ReportFormatter.format_key_value("Trend", vol_data.get('trend', '')))
            
            # Support & Resistance
            sr_data = technical_data.get('support_resistance', {})
            if sr_data:
                report.append(ReportFormatter.format_subsection("Support & Resistance"))
                report.append(ReportFormatter.format_key_value("Recent High", sr_data.get('recent_high', 'N/A')))
                report.append(ReportFormatter.format_key_value("Recent Low", sr_data.get('recent_low', 'N/A')))
            
            # Trend
            trend = technical_data.get('trend', '')
            if trend:
                report.append(ReportFormatter.format_subsection("Overall Trend"))
                report.append(f"    {trend}")
        
        # ===== SENTIMENT ANALYSIS =====
        if sentiment_data:
            report.append(ReportFormatter.format_section("SENTIMENT ANALYSIS", width))
            
            # News
            news_items = sentiment_data.get('news', [])
            if news_items:
                report.append(ReportFormatter.format_subsection("Recent News"))
                for i, news in enumerate(news_items[:5], 1):
                    report.append(f"\n    [{i}] {news.get('title', 'Untitled')}")
                    report.append(f"        Source: {news.get('source', 'Unknown')}")
                    report.append(f"        Time:   {news.get('timestamp', 'N/A')}")
                    if news.get('summary'):
                        report.append(f"        {news.get('summary', '')[:150]}...")
            
            # Sentiment Score
            sentiment_score = sentiment_data.get('sentiment_score')
            if sentiment_score is not None:
                report.append(ReportFormatter.format_subsection("Sentiment Score"))
                score_display = f"{sentiment_score:+.1f} / +10"
                if sentiment_score > 5:
                    score_display += " 🟢 Bullish"
                elif sentiment_score < -5:
                    score_display += " 🔴 Bearish"
                else:
                    score_display += " 🟡 Neutral"
                report.append(f"    {score_display}")
            
            # Sector Performance
            sector_data = sentiment_data.get('sectors', {})
            if sector_data:
                report.append(ReportFormatter.format_subsection("Sector Performance"))
                for sector, perf in sector_data.items():
                    perf_str = f"{perf:+.2f}%"
                    if perf > 0:
                        perf_str += " 🟢"
                    elif perf < 0:
                        perf_str += " 🔴"
                    report.append(ReportFormatter.format_key_value(sector, perf_str))
        
        # ===== RISK ASSESSMENT =====
        if risk_data:
            report.append(ReportFormatter.format_section("RISK ASSESSMENT", width))
            
            # Risk Score
            risk_score = risk_data.get('risk_score')
            if risk_score is not None:
                report.append(ReportFormatter.format_key_value("Risk Score", 
                    f"{risk_score}/10 {'🔴' if risk_score > 7 else '🟡' if risk_score > 4 else '🟢'}"))
            
            # Volatility
            report.append(ReportFormatter.format_key_value("Beta", 
                risk_data.get('beta', 'N/A')))
            report.append(ReportFormatter.format_key_value("52W High", 
                risk_data.get('52w_high', risk_data.get('fiftyTwoWeekHigh', 'N/A'))))
            report.append(ReportFormatter.format_key_value("52W Low", 
                risk_data.get('52w_low', risk_data.get('fiftyTwoWeekLow', 'N/A'))))
            
            # Drawdown
            current = risk_data.get('current_price')
            high = risk_data.get('52w_high', risk_data.get('fiftyTwoWeekHigh'))
            if current and high and high != 'N/A':
                drawdown = ((float(high) - float(current)) / float(high)) * 100
                report.append(ReportFormatter.format_key_value("Drawdown from 52W High", 
                    f"{drawdown:.1f}%"))
            
            # Risk Factors
            risk_factors = risk_data.get('risk_factors', [])
            if risk_factors:
                report.append(ReportFormatter.format_subsection("Key Risk Factors"))
                report.append(ReportFormatter.format_bullet_list(risk_factors))
        
        # ===== PORTFOLIO CONTEXT =====
        if portfolio_data:
            report.append(ReportFormatter.format_section("PORTFOLIO CONTEXT", width))
            report.append(ReportFormatter.format_key_value("Portfolio Fit", 
                portfolio_data.get('portfolio_fit', 'N/A')))
            report.append(ReportFormatter.format_key_value("Suggested Allocation", 
                portfolio_data.get('suggested_allocation', 'N/A')))
            
            sector_fit = portfolio_data.get('sector_fit', '')
            if sector_fit:
                report.append(ReportFormatter.format_key_value("Sector Fit", sector_fit))
        
        # ===== FINAL RECOMMENDATION =====
        if recommendation:
            report.append(ReportFormatter.format_recommendation(
                recommendation.get('action', 'HOLD'),
                recommendation.get('confidence', 'Low'),
                recommendation.get('score', 0.0),
                width
            ))
            
            # Score Breakdown
            breakdown = recommendation.get('breakdown', {})
            if breakdown:
                report.append(ReportFormatter.format_subsection("Score Breakdown"))
                for factor, data in breakdown.items():
                    score = data.get('score', 0)
                    weight = data.get('weight', 0)
                    summary = data.get('summary', '')
                    weighted = score * weight / 100
                    report.append(f"    • {factor} ({weight}%): {score}/10 → {weighted:.1f} pts")
                    if summary:
                        report.append(f"      {summary}")
            
            # Justification
            justification = recommendation.get('justification', '')
            if justification:
                report.append(ReportFormatter.format_subsection("Justification"))
                report.append(f"    {justification}")
            
            # Key Risks
            risks = recommendation.get('risks', [])
            if risks:
                report.append(ReportFormatter.format_subsection("Key Risks to Monitor"))
                report.append(ReportFormatter.format_bullet_list(risks))
            
            # Suggested Action
            suggested = recommendation.get('suggested_action', '')
            if suggested:
                report.append(ReportFormatter.format_subsection("Suggested Action"))
                report.append(f"    {suggested}")
        
        # ===== CRITIQUE =====
        if critique:
            report.append(ReportFormatter.format_section("CRITIQUE / DEVIL'S ADVOCATE", width))
            report.append(f"    {critique}")
        
        # ===== INDIVIDUAL AGENT SUMMARIES =====
        if agent_summaries:
            report.append(ReportFormatter.format_section("INDIVIDUAL AGENT ANALYSES", width))
            
            # Define display names and order for agents
            agent_display = {
                'Market_Researcher': ('📈', 'Market Researcher'),
                'market_researcher': ('📈', 'Market Researcher'),
                'Technical_Analyst': ('📉', 'Technical Analyst'),
                'technical_analyst': ('📉', 'Technical Analyst'),
                'Sentiment_Analyst': ('📰', 'Sentiment Analyst'),
                'sentiment_analyst': ('📰', 'Sentiment Analyst'),
                'Risk_Manager': ('⚠️', 'Risk Manager'),
                'risk_manager': ('⚠️', 'Risk Manager'),
                'Portfolio_Manager': ('💼', 'Portfolio Manager'),
                'portfolio_manager': ('💼', 'Portfolio Manager'),
                'Strategy_Manager': ('🎯', 'Strategy Manager'),
                'strategy_manager': ('🎯', 'Strategy Manager'),
                'Critic': ('🔍', 'Critic'),
                'critic': ('🔍', 'Critic'),
            }
            
            # Preferred order
            preferred_order = [
                'Market_Researcher', 'market_researcher',
                'Technical_Analyst', 'technical_analyst',
                'Sentiment_Analyst', 'sentiment_analyst',
                'Risk_Manager', 'risk_manager',
                'Portfolio_Manager', 'portfolio_manager',
                'Strategy_Manager', 'strategy_manager',
                'Critic', 'critic',
            ]
            
            # Sort agents: preferred order first, then alphabetically
            def sort_key(item):
                name = item[0]
                if name in preferred_order:
                    return preferred_order.index(name)
                return 100  # Unknown agents go last
            
            for agent_name, agent_text in sorted(agent_summaries.items(), key=sort_key):
                icon, display_name = agent_display.get(agent_name, ('🤖', agent_name.replace('_', ' ').title()))
                
                report.append(ReportFormatter.format_subsection(f"{icon} {display_name}"))
                # Truncate very long agent texts to keep report readable
                lines = agent_text.strip().split('\n')
                for line in lines[:50]:  # Max 50 lines per agent
                    report.append(f"    {line}")
                if len(lines) > 50:
                    report.append(f"    ... ({len(lines) - 50} more lines truncated)")
                report.append("")  # Blank line between agents
        
        # ===== RAW CONVERSATION =====
        if raw_conversation:
            report.append(ReportFormatter.format_section("RAW AGENT CONVERSATION", width))
            report.append(raw_conversation)
        
        # ===== FOOTER =====
        report.append(f"\n{'=' * width}")
        report.append(f"  Report generated by Indian Stock Market Multi-Agent System")
        report.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"{'=' * width}\n")
        
        return "\n".join(report)

    @staticmethod
    def format_markdown_report(
        symbol: str,
        exchange: str,
        analysis_type: str,
        timestamp: str,
        fundamental_data: Optional[Dict] = None,
        technical_data: Optional[Dict] = None,
        sentiment_data: Optional[Dict] = None,
        risk_data: Optional[Dict] = None,
        portfolio_data: Optional[Dict] = None,
        recommendation: Optional[Dict] = None,
        critique: Optional[str] = None,
        raw_conversation: Optional[str] = None,
        agent_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build a Markdown-formatted report (cleaner for GitHub, docs, etc.).
        """
        md = []
        
        # Header
        md.append(f"# 📊 Indian Stock Market Analysis: {symbol}")
        md.append(f"")
        md.append(f"| Field | Value |")
        md.append(f"|-------|-------|")
        md.append(f"| **Stock** | {symbol} |")
        md.append(f"| **Exchange** | {exchange} |")
        md.append(f"| **Analysis Type** | {analysis_type.upper()} |")
        md.append(f"| **Timestamp** | {timestamp} |")
        md.append(f"| **Generated** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
        md.append(f"")
        
        # Fundamental Analysis
        if fundamental_data:
            _fval = lambda *keys: ReportFormatter._get_fundamental_val(fundamental_data, *keys)
            
            md.append(f"---")
            md.append(f"## 📈 Fundamental Analysis")
            md.append(f"")
            md.append(f"### Company Overview")
            md.append(f"")
            md.append(f"| Metric | Value |")
            md.append(f"|--------|-------|")
            md.append(f"| **Company** | {_fval('company_name', 'name', 'longName')} |")
            md.append(f"| **Sector** | {_fval('sector')} |")
            md.append(f"| **Industry** | {_fval('industry')} |")
            md.append(f"| **Market Cap** | {ReportFormatter._format_currency(_fval('market_cap', 'marketCap'))} |")
            md.append(f"")
            md.append(f"### Key Ratios")
            md.append(f"")
            md.append(f"| Ratio | Value |")
            md.append(f"|-------|-------|")
            for key, label in [('pe_ratio', 'P/E Ratio'), ('pb_ratio', 'P/B Ratio'),
                               ('roe', 'ROE'), ('roce', 'ROCE'),
                               ('debt_to_equity', 'Debt/Equity'), ('current_ratio', 'Current Ratio'),
                               ('dividend_yield', 'Dividend Yield')]:
                val = _fval(key, {
                    'pe_ratio': 'trailingPE', 'pb_ratio': 'priceToBook',
                    'dividend_yield': 'dividendYield'
                }.get(key, ''))
                if val != 'N/A':
                    md.append(f"| **{label}** | {val} |")
            md.append(f"")
        
        # Technical Analysis
        if technical_data:
            md.append(f"---")
            md.append(f"## 📉 Technical Analysis")
            md.append(f"")
            md.append(f"| Indicator | Value | Signal |")
            md.append(f"|-----------|-------|--------|")
            
            rsi = technical_data.get('rsi', {})
            if rsi:
                md.append(f"| **RSI (14)** | {rsi.get('value', 'N/A')} | {rsi.get('signal', '')} |")
            
            macd = technical_data.get('macd', {})
            if macd:
                md.append(f"| **MACD** | {macd.get('macd_line', 'N/A')} | {macd.get('signal', '')} |")
            
            ma = technical_data.get('moving_averages', {})
            if ma:
                md.append(f"| **MA (20)** | {ma.get('ma_20', 'N/A')} | — |")
                md.append(f"| **MA (50)** | {ma.get('ma_50', 'N/A')} | — |")
                md.append(f"| **MA (200)** | {ma.get('ma_200', 'N/A')} | — |")
            
            bb = technical_data.get('bollinger_bands', {})
            if bb:
                md.append(f"| **Bollinger Width** | {bb.get('width_pct', 'N/A')}% | — |")
            
            vol = technical_data.get('volume_analysis', {})
            if vol:
                md.append(f"| **Volume Ratio** | {vol.get('volume_ratio', 'N/A')} | {vol.get('trend', '')} |")
            
            trend = technical_data.get('trend', '')
            if trend:
                md.append(f"| **Overall Trend** | {trend} | — |")
            md.append(f"")
        
        # Sentiment
        if sentiment_data:
            md.append(f"---")
            md.append(f"## 📰 Sentiment Analysis")
            md.append(f"")
            
            score = sentiment_data.get('sentiment_score')
            if score is not None:
                md.append(f"**Sentiment Score:** {score:+.1f} / +10")
                md.append(f"")
            
            news = sentiment_data.get('news', [])
            if news:
                md.append(f"### Recent News")
                md.append(f"")
                for item in news[:5]:
                    md.append(f"- **{item.get('title', 'Untitled')}**")
                    md.append(f"  - Source: {item.get('source', 'Unknown')} | {item.get('timestamp', 'N/A')}")
                md.append(f"")
        
        # Risk
        if risk_data:
            md.append(f"---")
            md.append(f"## ⚠️ Risk Assessment")
            md.append(f"")
            md.append(f"| Metric | Value |")
            md.append(f"|--------|-------|")
            md.append(f"| **Risk Score** | {risk_data.get('risk_score', 'N/A')}/10 |")
            md.append(f"| **Beta** | {risk_data.get('beta', 'N/A')} |")
            md.append(f"| **52W High** | {risk_data.get('52w_high', risk_data.get('fiftyTwoWeekHigh', 'N/A'))} |")
            md.append(f"| **52W Low** | {risk_data.get('52w_low', risk_data.get('fiftyTwoWeekLow', 'N/A'))} |")
            md.append(f"")
        
        # Recommendation
        if recommendation:
            md.append(f"---")
            md.append(f"## 🎯 Final Recommendation")
            md.append(f"")
            md.append(f"| Field | Value |")
            md.append(f"|-------|-------|")
            md.append(f"| **Action** | **{recommendation.get('action', 'HOLD')}** |")
            md.append(f"| **Confidence** | {recommendation.get('confidence', 'Low')} |")
            md.append(f"| **Score** | {recommendation.get('score', 0.0):.1f}/10 |")
            md.append(f"")
            
            breakdown = recommendation.get('breakdown', {})
            if breakdown:
                md.append(f"### Score Breakdown")
                md.append(f"")
                md.append(f"| Factor | Weight | Score | Weighted |")
                md.append(f"|--------|--------|-------|----------|")
                for factor, data in breakdown.items():
                    score = data.get('score', 0)
                    weight = data.get('weight', 0)
                    weighted = score * weight / 100
                    md.append(f"| {factor} | {weight}% | {score}/10 | {weighted:.1f} |")
                md.append(f"")
            
            justification = recommendation.get('justification', '')
            if justification:
                md.append(f"**Justification:** {justification}")
                md.append(f"")
            
            risks = recommendation.get('risks', [])
            if risks:
                md.append(f"### Key Risks")
                md.append(f"")
                for risk in risks:
                    md.append(f"- {risk}")
                md.append(f"")
        
        # Critique
        if critique:
            md.append(f"---")
            md.append(f"## 🔍 Critique / Devil's Advocate")
            md.append(f"")
            md.append(f"{critique}")
            md.append(f"")
        
        # Individual Agent Summaries
        if agent_summaries:
            md.append(f"---")
            md.append(f"## 🤖 Individual Agent Analyses")
            md.append(f"")
            
            agent_display = {
                'Market_Researcher': ('📈', 'Market Researcher'),
                'market_researcher': ('📈', 'Market Researcher'),
                'Technical_Analyst': ('📉', 'Technical Analyst'),
                'technical_analyst': ('📉', 'Technical Analyst'),
                'Sentiment_Analyst': ('📰', 'Sentiment Analyst'),
                'sentiment_analyst': ('📰', 'Sentiment Analyst'),
                'Risk_Manager': ('⚠️', 'Risk Manager'),
                'risk_manager': ('⚠️', 'Risk Manager'),
                'Portfolio_Manager': ('💼', 'Portfolio Manager'),
                'portfolio_manager': ('💼', 'Portfolio Manager'),
                'Strategy_Manager': ('🎯', 'Strategy Manager'),
                'strategy_manager': ('🎯', 'Strategy Manager'),
                'Critic': ('🔍', 'Critic'),
                'critic': ('🔍', 'Critic'),
            }
            
            preferred_order = [
                'Market_Researcher', 'market_researcher',
                'Technical_Analyst', 'technical_analyst',
                'Sentiment_Analyst', 'sentiment_analyst',
                'Risk_Manager', 'risk_manager',
                'Portfolio_Manager', 'portfolio_manager',
                'Strategy_Manager', 'strategy_manager',
                'Critic', 'critic',
            ]
            
            def sort_key(item):
                name = item[0]
                if name in preferred_order:
                    return preferred_order.index(name)
                return 100
            
            for agent_name, agent_text in sorted(agent_summaries.items(), key=sort_key):
                icon, display_name = agent_display.get(agent_name, ('🤖', agent_name.replace('_', ' ').title()))
                md.append(f"### {icon} {display_name}")
                md.append(f"")
                lines = agent_text.strip().split('\n')
                for line in lines[:50]:
                    md.append(f"{line}")
                if len(lines) > 50:
                    md.append(f"")
                    md.append(f"> *... ({len(lines) - 50} more lines truncated)*")
                md.append(f"")
        
        # Footer
        md.append(f"---")
        md.append(f"*Report generated by Indian Stock Market Multi-Agent System*")
        md.append(f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(md)

    @staticmethod
    def format_html_report(
        symbol: str,
        exchange: str,
        analysis_type: str,
        timestamp: str,
        fundamental_data: Optional[Dict] = None,
        technical_data: Optional[Dict] = None,
        sentiment_data: Optional[Dict] = None,
        risk_data: Optional[Dict] = None,
        portfolio_data: Optional[Dict] = None,
        recommendation: Optional[Dict] = None,
        critique: Optional[str] = None,
        raw_conversation: Optional[str] = None,
        agent_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build a beautifully styled, self-contained HTML report.
        Uses actual API data (not LLM-generated text) for accurate metrics.
        """
        # Helper to safely get values from nested dicts
        def _val(d, *keys, default='N/A'):
            current = d
            for k in keys:
                if isinstance(current, dict):
                    current = current.get(k)
                    if current is None:
                        return default
                else:
                    return default
            return current if current is not None else default

        def _fmt_currency(v):
            if v is None or v == 'N/A':
                return 'N/A'
            try:
                val = float(v)
                if val >= 1_00_00_00_00_000:
                    return f"₹{val/1_00_00_00_000:.2f}L Cr"
                elif val >= 1_00_00_000:
                    return f"₹{val/1_00_000:.2f} Cr"
                elif val >= 1_00_000:
                    return f"₹{val/1_000:.2f} L"
                elif val >= 1_000:
                    return f"₹{val/1_000:.2f}K"
                else:
                    return f"₹{val:.2f}"
            except (ValueError, TypeError):
                return str(v)

        def _fmt_num(v, decimals=2):
            if v is None or v == 'N/A':
                return 'N/A'
            try:
                return f"{float(v):.{decimals}f}"
            except (ValueError, TypeError):
                return str(v)

        # Extract actual data from structured dicts
        # --- Fundamental (use _get_fundamental_val to search all locations) ---
        _fval = lambda *keys: ReportFormatter._get_fundamental_val(fundamental_data, *keys)
        
        company_name = _fval('company_name', 'name', 'longName') or symbol
        sector = _fval('sector')
        industry = _fval('industry')
        market_cap = _fmt_currency(_fval('market_cap', 'marketCap'))
        pe_ratio = _fmt_num(_fval('pe_ratio', 'trailingPE'))
        pb_ratio = _fmt_num(_fval('pb_ratio', 'priceToBook'))
        roe = _fmt_num(_fval('roe'))
        roce = _fmt_num(_fval('roce'))
        debt_equity = _fmt_num(_fval('debt_to_equity', 'debtToEquity'))
        current_ratio = _fmt_num(_fval('current_ratio', 'currentRatio'))
        div_yield = _fmt_num(_fval('dividend_yield', 'dividendYield'))
        revenue = _fmt_currency(_fval('revenue', 'totalRevenue'))
        net_income = _fmt_currency(_fval('net_income', 'netIncomeToCommon'))
        op_margin = _fmt_num(_fval('operating_margin', 'operatingMargins', 'opm'))

        profit_margin = _fmt_num(_fval('profit_margin', 'profitMargins'))
        fcf = _fmt_currency(_fval('free_cash_flow', 'freeCashflow'))

        # --- Technical ---
        current_price = 'N/A'
        rsi_val = 'N/A'
        rsi_signal = ''
        macd_line = 'N/A'
        macd_signal_line = 'N/A'
        macd_hist = 'N/A'
        macd_signal = ''
        ma_20 = 'N/A'
        ma_50 = 'N/A'
        ma_200 = 'N/A'
        bb_upper = 'N/A'
        bb_middle = 'N/A'
        bb_lower = 'N/A'
        bb_width = 'N/A'
        avg_vol = 'N/A'
        recent_vol = 'N/A'
        vol_ratio = 'N/A'
        vol_trend = ''
        recent_high = 'N/A'
        recent_low = 'N/A'
        trend = ''

        if technical_data:
            current_price = _fmt_num(technical_data.get('current_price', 'N/A'))
            
            rsi = technical_data.get('rsi', {})
            if rsi:
                rsi_val = _fmt_num(rsi.get('value', 'N/A'))
                rsi_signal = rsi.get('signal', '')
            
            macd = technical_data.get('macd', {})
            if macd:
                macd_line = _fmt_num(macd.get('macd_line', 'N/A'))
                macd_signal_line = _fmt_num(macd.get('signal_line', 'N/A'))
                macd_hist = _fmt_num(macd.get('histogram', 'N/A'))
                macd_signal = macd.get('signal', '')
            
            ma = technical_data.get('moving_averages', {})
            if ma:
                ma_20 = _fmt_num(ma.get('ma_20', 'N/A'))
                ma_50 = _fmt_num(ma.get('ma_50', 'N/A'))
                ma_200 = _fmt_num(ma.get('ma_200', 'N/A'))
            
            bb = technical_data.get('bollinger_bands', {})
            if bb:
                bb_upper = _fmt_num(bb.get('upper', 'N/A'))
                bb_middle = _fmt_num(bb.get('middle', 'N/A'))
                bb_lower = _fmt_num(bb.get('lower', 'N/A'))
                bb_width = _fmt_num(bb.get('width_pct', 'N/A'))
            
            vol = technical_data.get('volume_analysis', {})
            if vol:
                avg_vol = vol.get('avg_volume', 'N/A')
                recent_vol = vol.get('recent_volume', 'N/A')
                vol_ratio = _fmt_num(vol.get('volume_ratio', 'N/A'))
                vol_trend = vol.get('trend', '')
            
            sr = technical_data.get('support_resistance', {})
            if sr:
                recent_high = _fmt_num(sr.get('recent_high', 'N/A'))
                recent_low = _fmt_num(sr.get('recent_low', 'N/A'))
            
            trend = technical_data.get('trend', '')

        # --- Sentiment ---
        sentiment_score = None
        news_items = []
        if sentiment_data:
            sentiment_score = sentiment_data.get('sentiment_score')
            news_items = sentiment_data.get('news', [])

        # --- Risk ---
        risk_score = 'N/A'
        beta = 'N/A'
        w52_high = 'N/A'
        w52_low = 'N/A'
        risk_factors = []
        if risk_data:
            risk_score = risk_data.get('risk_score', 'N/A')
            beta = _fmt_num(risk_data.get('beta', 'N/A'))
            w52_high = _fmt_num(risk_data.get('52w_high', risk_data.get('fiftyTwoWeekHigh', 'N/A')))
            w52_low = _fmt_num(risk_data.get('52w_low', risk_data.get('fiftyTwoWeekLow', 'N/A')))
            risk_factors = risk_data.get('risk_factors', [])

        # --- Recommendation ---
        rec_action = 'HOLD'
        rec_confidence = 'Low'
        rec_score = 0.0
        rec_breakdown = {}
        rec_justification = ''
        rec_risks = []
        rec_suggested = ''
        if recommendation:
            rec_action = recommendation.get('action', 'HOLD')
            rec_confidence = recommendation.get('confidence', 'Low')
            rec_score = recommendation.get('score', 0.0)
            rec_breakdown = recommendation.get('breakdown', {})
            rec_justification = recommendation.get('justification', '')
            rec_risks = recommendation.get('risks', [])
            rec_suggested = recommendation.get('suggested_action', '')

        # Determine action color
        action_color = {'BUY': '#00c853', 'SELL': '#ff1744', 'HOLD': '#ffd600'}
        action_bg = {'BUY': '#e8f5e9', 'SELL': '#ffebee', 'HOLD': '#fff8e1'}
        rec_color = action_color.get(rec_action.upper(), '#9e9e9e')
        rec_bg = action_bg.get(rec_action.upper(), '#f5f5f5')

        # Build HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Analysis Report - {symbol}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: #f0f2f5; color: #1a1a2e; line-height: 1.6; padding: 20px;
  }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #fff; padding: 40px; border-radius: 16px; margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  }}
  .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.8; }}
  .header .meta {{ display: flex; flex-wrap: wrap; gap: 20px; margin-top: 16px; font-size: 14px; }}
  .header .meta span {{ opacity: 0.9; }}
  .header .meta strong {{ opacity: 1; }}
  .section {{
    background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}
  .section h2 {{ font-size: 20px; color: #1a1a2e; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e8e8e8; }}
  .section h2 .icon {{ margin-right: 8px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .metric {{
    background: #f8f9fa; border-radius: 8px; padding: 12px 16px;
    border-left: 3px solid #0f3460;
  }}
  .metric .label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
  .metric .value {{ font-size: 18px; font-weight: 700; color: #1a1a2e; margin-top: 2px; }}
  .metric .value.good {{ color: #00c853; }}
  .metric .value.bad {{ color: #ff1744; }}
  .metric .value.warn {{ color: #ff6d00; }}
  table {{
    width: 100%; border-collapse: collapse; margin-top: 8px;
  }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }}
  th {{ background: #f8f9fa; font-weight: 600; color: #555; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }}
  tr:hover {{ background: #f8f9fa; }}
  .recommendation-card {{
    text-align: center; padding: 32px; border-radius: 12px;
    background: {rec_bg}; border: 2px solid {rec_color};
  }}
  .recommendation-card .action {{ font-size: 48px; font-weight: 800; color: {rec_color}; }}
  .recommendation-card .confidence {{ font-size: 16px; color: #666; margin-top: 4px; }}
  .recommendation-card .score {{ font-size: 24px; font-weight: 700; color: {rec_color}; margin-top: 8px; }}
  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
  }}
  .badge.bullish {{ background: #e8f5e9; color: #00c853; }}
  .badge.bearish {{ background: #ffebee; color: #ff1744; }}
  .badge.neutral {{ background: #fff8e1; color: #ff8f00; }}
  .badge.overbought {{ background: #ffebee; color: #d50000; }}
  .badge.oversold {{ background: #e8f5e9; color: #00c853; }}
  .news-item {{ padding: 12px 0; border-bottom: 1px solid #f0f0f0; }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-item .title {{ font-weight: 600; font-size: 14px; }}
  .news-item .source {{ font-size: 12px; color: #888; }}
  .risk-factor {{ padding: 8px 12px; margin: 4px 0; background: #fff3e0; border-radius: 6px; border-left: 3px solid #ff6d00; font-size: 14px; }}
  .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
  .signal-indicator {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  .signal-indicator.green {{ background: #00c853; }}
  .signal-indicator.red {{ background: #ff1744; }}
  .signal-indicator.yellow {{ background: #ffd600; }}
  @media (max-width: 600px) {{
    .header {{ padding: 24px; }}
    .header h1 {{ font-size: 22px; }}
    .grid {{ grid-template-columns: 1fr; }}
    .recommendation-card .action {{ font-size: 36px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <h1>📊 {symbol}</h1>
    <div class="subtitle">Indian Stock Market Analysis Report</div>
    <div class="meta">
      <span><strong>Exchange:</strong> {exchange}</span>
      <span><strong>Analysis:</strong> {analysis_type.upper()}</span>
      <span><strong>Timestamp:</strong> {timestamp}</span>
      <span><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
    </div>
  </div>

  <!-- RECOMMENDATION -->
  <div class="section">
    <h2><span class="icon">🎯</span>Final Recommendation</h2>
    <div class="recommendation-card">
      <div class="action">{rec_action}</div>
      <div class="confidence">Confidence: {rec_confidence}</div>
      <div class="score">{rec_score:.1f} / 10</div>
    </div>
"""

        # Score Breakdown
        if rec_breakdown:
            html += """    <table>
      <thead><tr><th>Factor</th><th>Weight</th><th>Score</th><th>Weighted</th></tr></thead>
      <tbody>
"""
            for factor, data in rec_breakdown.items():
                score = data.get('score', 0)
                weight = data.get('weight', 0)
                weighted = score * weight / 100
                html += f"""        <tr><td>{factor}</td><td>{weight}%</td><td>{score}/10</td><td>{weighted:.1f}</td></tr>
"""
            html += """      </tbody>
    </table>
"""

        if rec_justification:
            html += f"""    <p style="margin-top:12px;font-size:14px;color:#555;"><strong>Justification:</strong> {rec_justification}</p>
"""

        if rec_risks:
            html += """    <div style="margin-top:12px;">
      <strong style="font-size:14px;">Key Risks:</strong>
"""
            for risk in rec_risks:
                html += f"""      <div class="risk-factor">⚠️ {risk}</div>
"""
            html += """    </div>
"""

        if rec_suggested:
            html += f"""    <p style="margin-top:12px;font-size:14px;color:#0f3460;"><strong>Suggested Action:</strong> {rec_suggested}</p>
"""

        html += """  </div>
"""

        # --- FUNDAMENTAL ANALYSIS ---
        if fundamental_data:
            html += """  <div class="section">
    <h2><span class="icon">📈</span>Fundamental Analysis</h2>
    <div class="grid">
"""
            html += f"""      <div class="metric"><div class="label">Company</div><div class="value">{company_name}</div></div>
      <div class="metric"><div class="label">Sector</div><div class="value">{sector}</div></div>
      <div class="metric"><div class="label">Industry</div><div class="value">{industry}</div></div>
      <div class="metric"><div class="label">Market Cap</div><div class="value">{market_cap}</div></div>
"""
            html += """    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Key Ratios</h3>
    <div class="grid">
"""
            html += f"""      <div class="metric"><div class="label">P/E Ratio</div><div class="value">{pe_ratio}</div></div>
      <div class="metric"><div class="label">P/B Ratio</div><div class="value">{pb_ratio}</div></div>
      <div class="metric"><div class="label">ROE</div><div class="value">{roe}%</div></div>
      <div class="metric"><div class="label">ROCE</div><div class="value">{roce}%</div></div>
      <div class="metric"><div class="label">Debt/Equity</div><div class="value">{debt_equity}</div></div>
      <div class="metric"><div class="label">Current Ratio</div><div class="value">{current_ratio}</div></div>
      <div class="metric"><div class="label">Dividend Yield</div><div class="value">{div_yield}%</div></div>
"""
            html += """    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Financial Health</h3>
    <div class="grid">
"""
            html += f"""      <div class="metric"><div class="label">Revenue (TTM)</div><div class="value">{revenue}</div></div>
      <div class="metric"><div class="label">Net Income</div><div class="value">{net_income}</div></div>
      <div class="metric"><div class="label">Operating Margin</div><div class="value">{op_margin}%</div></div>
      <div class="metric"><div class="label">Profit Margin</div><div class="value">{profit_margin}%</div></div>
      <div class="metric"><div class="label">Free Cash Flow</div><div class="value">{fcf}</div></div>
"""
            html += """    </div>
  </div>
"""

        # --- TECHNICAL ANALYSIS ---
        if technical_data:
            rsi_badge = 'neutral'
            if rsi_signal == 'Overbought': rsi_badge = 'overbought'
            elif rsi_signal == 'Oversold': rsi_badge = 'oversold'
            
            macd_badge = 'neutral'
            if macd_signal == 'Bullish': macd_badge = 'bullish'
            elif macd_signal == 'Bearish': macd_badge = 'bearish'

            vol_badge = 'neutral'
            if vol_trend == 'High': vol_badge = 'bullish'
            elif vol_trend == 'Low': vol_badge = 'bearish'

            trend_badge = 'neutral'
            if 'Uptrend' in trend: trend_badge = 'bullish'
            elif 'Downtrend' in trend: trend_badge = 'bearish'

            html += f"""  <div class="section">
    <h2><span class="icon">📉</span>Technical Analysis</h2>
    <div class="grid">
      <div class="metric"><div class="label">Current Price</div><div class="value">₹{current_price}</div></div>
      <div class="metric"><div class="label">RSI (14)</div><div class="value">{rsi_val} <span class="badge {rsi_badge}">{rsi_signal}</span></div></div>
      <div class="metric"><div class="label">MACD Signal</div><div class="value"><span class="badge {macd_badge}">{macd_signal}</span></div></div>
      <div class="metric"><div class="label">Overall Trend</div><div class="value"><span class="badge {trend_badge}">{trend}</span></div></div>
    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Moving Averages</h3>
    <div class="grid">
      <div class="metric"><div class="label">MA (20-day)</div><div class="value">₹{ma_20}</div></div>
      <div class="metric"><div class="label">MA (50-day)</div><div class="value">₹{ma_50}</div></div>
      <div class="metric"><div class="label">MA (200-day)</div><div class="value">₹{ma_200}</div></div>
    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Bollinger Bands</h3>
    <div class="grid">
      <div class="metric"><div class="label">Upper Band</div><div class="value">₹{bb_upper}</div></div>
      <div class="metric"><div class="label">Middle Band</div><div class="value">₹{bb_middle}</div></div>
      <div class="metric"><div class="label">Lower Band</div><div class="value">₹{bb_lower}</div></div>
      <div class="metric"><div class="label">Band Width</div><div class="value">{bb_width}%</div></div>
    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Volume Analysis</h3>
    <div class="grid">
      <div class="metric"><div class="label">Avg Volume</div><div class="value">{avg_vol}</div></div>
      <div class="metric"><div class="label">Recent Volume</div><div class="value">{recent_vol}</div></div>
      <div class="metric"><div class="label">Volume Ratio</div><div class="value">{vol_ratio} <span class="badge {vol_badge}">{vol_trend}</span></div></div>
    </div>
    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Support & Resistance</h3>
    <div class="grid">
      <div class="metric"><div class="label">Recent High</div><div class="value">₹{recent_high}</div></div>
      <div class="metric"><div class="label">Recent Low</div><div class="value">₹{recent_low}</div></div>
    </div>
  </div>
"""

        # --- SENTIMENT ---
        if sentiment_data:
            html += """  <div class="section">
    <h2><span class="icon">📰</span>Sentiment Analysis</h2>
"""
            if sentiment_score is not None:
                sent_badge = 'neutral'
                if sentiment_score > 5: sent_badge = 'bullish'
                elif sentiment_score < -5: sent_badge = 'bearish'
                html += f"""    <div class="grid">
      <div class="metric"><div class="label">Sentiment Score</div><div class="value">{sentiment_score:+.1f} / +10 <span class="badge {sent_badge}">{'Bullish' if sentiment_score > 5 else 'Bearish' if sentiment_score < -5 else 'Neutral'}</span></div></div>
    </div>
"""
            if news_items:
                html += """    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Recent News</h3>
"""
                for item in news_items[:5]:
                    title = item.get('title', 'Untitled')
                    source = item.get('source', 'Unknown')
                    ts = item.get('timestamp', 'N/A')
                    html += f"""    <div class="news-item">
      <div class="title">{title}</div>
      <div class="source">{source} &middot; {ts}</div>
    </div>
"""
            html += """  </div>
"""

        # --- RISK ---
        if risk_data:
            risk_badge = 'neutral'
            try:
                rs = float(risk_score)
                if rs > 7: risk_badge = 'bearish'
                elif rs > 4: risk_badge = 'neutral'
                else: risk_badge = 'bullish'
            except: pass

            html += f"""  <div class="section">
    <h2><span class="icon">⚠️</span>Risk Assessment</h2>
    <div class="grid">
      <div class="metric"><div class="label">Risk Score</div><div class="value">{risk_score}/10 <span class="badge {risk_badge}">{'High' if risk_badge == 'bearish' else 'Medium' if risk_badge == 'neutral' else 'Low'}</span></div></div>
      <div class="metric"><div class="label">Beta</div><div class="value">{beta}</div></div>
      <div class="metric"><div class="label">52-Week High</div><div class="value">₹{w52_high}</div></div>
      <div class="metric"><div class="label">52-Week Low</div><div class="value">₹{w52_low}</div></div>
    </div>
"""
            if risk_factors:
                html += """    <h3 style="font-size:16px;margin:16px 0 8px;color:#333;">Key Risk Factors</h3>
"""
                for factor in risk_factors:
                    html += f"""    <div class="risk-factor">⚠️ {factor}</div>
"""
            html += """  </div>
"""

        # --- PORTFOLIO ---
        if portfolio_data:
            html += """  <div class="section">
    <h2><span class="icon">💼</span>Portfolio Context</h2>
    <div class="grid">
"""
            html += f"""      <div class="metric"><div class="label">Portfolio Fit</div><div class="value">{portfolio_data.get('portfolio_fit', 'N/A')}</div></div>
      <div class="metric"><div class="label">Suggested Allocation</div><div class="value">{portfolio_data.get('suggested_allocation', 'N/A')}</div></div>
      <div class="metric"><div class="label">Sector Fit</div><div class="value">{portfolio_data.get('sector_fit', 'N/A')}</div></div>
"""
            html += """    </div>
  </div>
"""

        # --- CRITIQUE ---
        if critique:
            html += f"""  <div class="section">
    <h2><span class="icon">🔍</span>Critique / Devil's Advocate</h2>
    <p style="font-size:14px;color:#555;line-height:1.7;">{critique}</p>
  </div>
"""

        # --- INDIVIDUAL AGENT SUMMARIES ---
        if agent_summaries:
            html += """  <div class="section">
    <h2><span class="icon">🤖</span>Individual Agent Analyses</h2>
"""
            agent_display = {
                'Market_Researcher': ('📈', 'Market Researcher'),
                'market_researcher': ('📈', 'Market Researcher'),
                'Technical_Analyst': ('📉', 'Technical Analyst'),
                'technical_analyst': ('📉', 'Technical Analyst'),
                'Sentiment_Analyst': ('📰', 'Sentiment Analyst'),
                'sentiment_analyst': ('📰', 'Sentiment Analyst'),
                'Risk_Manager': ('⚠️', 'Risk Manager'),
                'risk_manager': ('⚠️', 'Risk Manager'),
                'Portfolio_Manager': ('💼', 'Portfolio Manager'),
                'portfolio_manager': ('💼', 'Portfolio Manager'),
                'Strategy_Manager': ('🎯', 'Strategy Manager'),
                'strategy_manager': ('🎯', 'Strategy Manager'),
                'Critic': ('🔍', 'Critic'),
                'critic': ('🔍', 'Critic'),
            }
            preferred_order = [
                'Market_Researcher', 'market_researcher',
                'Technical_Analyst', 'technical_analyst',
                'Sentiment_Analyst', 'sentiment_analyst',
                'Risk_Manager', 'risk_manager',
                'Portfolio_Manager', 'portfolio_manager',
                'Strategy_Manager', 'strategy_manager',
                'Critic', 'critic',
            ]
            def sort_key(item):
                name = item[0]
                if name in preferred_order:
                    return preferred_order.index(name)
                return 100
            
            for agent_name, agent_text in sorted(agent_summaries.items(), key=sort_key):
                icon, display_name = agent_display.get(agent_name, ('🤖', agent_name.replace('_', ' ').title()))
                escaped_text = agent_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html += f"""    <details style="margin-bottom:12px;">
      <summary style="cursor:pointer;font-size:15px;color:#0f3460;font-weight:600;padding:8px 0;">{icon} {display_name}</summary>
      <pre style="margin-top:8px;padding:16px;background:#f8f9fa;color:#1a1a2e;border-radius:8px;font-size:13px;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;max-height:400px;overflow-y:auto;border:1px solid #e8e8e8;">{escaped_text}</pre>
    </details>
"""
            html += """  </div>
"""

        # --- RAW CONVERSATION (collapsible) ---
        if raw_conversation:
            escaped_conv = raw_conversation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html += f"""  <div class="section">
    <h2><span class="icon">💬</span>Raw Agent Conversation</h2>
    <details>
      <summary style="cursor:pointer;font-size:14px;color:#0f3460;font-weight:600;">Click to expand/collapse</summary>
      <pre style="margin-top:12px;padding:16px;background:#1a1a2e;color:#e0e0e0;border-radius:8px;font-size:12px;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;max-height:600px;overflow-y:auto;">{escaped_conv}</pre>
    </details>
  </div>
"""

        # --- FOOTER ---
        html += f"""  <div class="footer">
    <p>Report generated by Indian Stock Market Multi-Agent System</p>
    <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  </div>

</div>
</body>
</html>"""

        return html

    @staticmethod
    def save_report(report: str, symbol: str, output_dir: str = "reports", 
                    fmt: str = "txt") -> str:
        """
        Save a report to a file.
        
        Args:
            report: The report content
            symbol: Stock symbol (for filename)
            output_dir: Directory to save reports
            fmt: Format extension ('txt', 'md', 'html')
        
        Returns:
            Path to the saved file
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{timestamp}.{fmt}"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        
        return filepath

    @staticmethod
    def _format_currency(value: Any) -> str:
        """Format a value as currency with appropriate suffix."""
        if value is None or value == 'N/A':
            return 'N/A'
        try:
            val = float(value)
            if val >= 1_00_00_00_00_00_000:  # 1 Lakh Crore+
                return f"₹{val/1_00_00_00_00_000:.2f}L Cr"
            elif val >= 1_00_00_00_000:  # 1 Crore+
                return f"₹{val/1_00_00_000:.2f} Cr"
            elif val >= 1_00_000:  # 1 Lakh+
                return f"₹{val/1_00_000:.2f} L"
            elif val >= 1_000:
                return f"₹{val/1_000:.2f}K"
            else:
                return f"₹{val:.2f}"
        except (ValueError, TypeError):
            return str(value)
