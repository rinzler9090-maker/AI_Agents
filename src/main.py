"""
Main entry point for the Indian Stock Market Multi-Agent System.
Orchestrates a group chat of AI agents to analyze Indian stocks comprehensively.

Usage:
    python -m src.main --stock RELIANCE
    python src/main.py --stock RELIANCE --output --format md
    python src/main.py --stock TCS --fresh --output --format txt
"""

import os
import sys

# Ensure the project root is in the Python path for direct execution
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import logging
from datetime import datetime
from autogen import UserProxyAgent, GroupChat, GroupChatManager

from src.agents.market_researcher import create_market_researcher_agent
from src.agents.technical_analyst import create_technical_analyst_agent
from src.agents.sentiment_analyst import create_sentiment_analyst_agent
from src.agents.risk_manager import create_risk_manager_agent
from src.agents.portfolio_manager import create_portfolio_manager_agent
from src.agents.strategy_manager import create_strategy_manager_agent
from src.agents.critic import create_critic_agent
from src.utils.helpers import get_llm_config, setup_logging, validate_stock_symbol, retry_on_api_error

from src.utils.report_formatter import ReportFormatter
from src.tools.data_prefetcher import prefetch_all_data, build_grounding_context, parse_screener_company_data
import re



logger = logging.getLogger(__name__)


def create_agents(llm_config: dict, analysis_type: str = "full", grounding_context: str = ""):
    """
    Create and return the list of agents based on analysis type.

    Args:
        llm_config: LLM configuration dictionary.
        analysis_type: Type of analysis to run ('full', 'fundamental', 'technical', 'quick').
        grounding_context: Pre-fetched real market data for grounding.

    Returns:
        Tuple of (agents_list, user_proxy_agent).
    """
    print("Creating agents...")

    # Pass grounding context to ALL agents so they all have access to real data
    researcher = create_market_researcher_agent(llm_config, grounding_context)
    technical = create_technical_analyst_agent(llm_config, grounding_context)
    sentiment = create_sentiment_analyst_agent(llm_config, grounding_context)
    risk = create_risk_manager_agent(llm_config, grounding_context)
    portfolio = create_portfolio_manager_agent(llm_config, grounding_context)
    manager = create_strategy_manager_agent(llm_config, grounding_context)
    critic = create_critic_agent(llm_config, grounding_context)


    user_proxy = UserProxyAgent(
        name="user",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        system_message="You are a user initiating a stock analysis request.",
        code_execution_config=False
    )

    if analysis_type == "fundamental":
        # Only fundamental analysis agents
        agents = [user_proxy, researcher, manager, critic]
        print("  Mode: Fundamental Analysis (Researcher + Manager + Critic)")
    elif analysis_type == "technical":
        # Only technical analysis agents
        agents = [user_proxy, technical, manager, critic]
        print("  Mode: Technical Analysis (Technical Analyst + Manager + Critic)")
    elif analysis_type == "quick":
        # Quick overview with fewer agents
        agents = [user_proxy, researcher, technical, manager]
        print("  Mode: Quick Analysis (Researcher + Technical + Manager)")
    else:
        # Full analysis with all 7 agents
        agents = [user_proxy, researcher, technical, sentiment, risk, portfolio, manager, critic]
        print("  Mode: Full Analysis (All 8 agents)")

    return agents, user_proxy


def parse_recommendation_from_summary(summary_text: str) -> dict:
    """
    Parse the agent conversation summary to extract a structured recommendation dict.
    
    The agents typically output a summary with sections like:
    - Final Recommendation: BUY/SELL/HOLD
    - Confidence: High/Medium/Low
    - Weighted Score: X.X/10
    - Score Breakdown with factors, weights, and scores
    
    Args:
        summary_text: Raw summary text from the agent conversation
    
    Returns:
        Structured recommendation dict with action, confidence, score, breakdown, etc.
    """
    rec = {
        'action': 'HOLD',
        'confidence': 'Low',
        'score': 0.0,
        'breakdown': {},
        'justification': '',
        'risks': [],
        'suggested_action': '',
    }
    
    if not summary_text:
        return rec
    
    text = summary_text
    
    # 1. Extract Action (BUY/SELL/HOLD)
    action_match = re.search(r'(?:Action|Recommendation|Decision)\s*[:：]\s*\*{0,2}(BUY|SELL|HOLD)\*{0,2}', text, re.IGNORECASE)
    if action_match:
        rec['action'] = action_match.group(1).upper()
    
    # 2. Extract Confidence
    conf_match = re.search(r'Confidence\s*[:：]\s*(\w+)', text, re.IGNORECASE)
    if conf_match:
        conf = conf_match.group(1).capitalize()
        if conf in ['High', 'Medium', 'Low']:
            rec['confidence'] = conf
    
    # 3. Extract Weighted Score (e.g., "5.0/10" or "Score: 5.0")
    score_match = re.search(r'(?:Weighted\s*)?[Ss]core\s*[:：]?\s*(\d+\.?\d*)\s*/\s*10', text)
    if score_match:
        rec['score'] = float(score_match.group(1))
    else:
        # Try simpler pattern: "Score: X.X"
        score_match = re.search(r'[Ss]core\s*[:：]\s*(\d+\.?\d*)', text)
        if score_match:
            rec['score'] = float(score_match.group(1))
    
    # 4. Extract Score Breakdown (e.g., "Fundamentals 5.8, Sentiment 4.5, Technical 4.2")
    # Pattern: FactorName X.X/10 or FactorName X.X
    breakdown_pattern = re.findall(r'(\w[\w\s]+?)\s*(\d+\.?\d*)\s*/\s*10', text)
    if not breakdown_pattern:
        breakdown_pattern = re.findall(r'(\w[\w\s]+?)\s*[:：]?\s*(\d+\.?\d*)\s*[分/]', text)
    if not breakdown_pattern:
        # Try: "Factor: X.X (Weight: Y%)" or "Factor (Y%): X.X"
        breakdown_pattern = re.findall(r'(\w[\w\s]+?)\s*\((\d+)%\)\s*[:：]?\s*(\d+\.?\d*)', text)
        if breakdown_pattern:
            breakdown_pattern = [(m[0], m[2]) for m in breakdown_pattern]
    
    # Known factor names to look for
    known_factors = ['Fundamentals?', 'Technical', 'Sentiment', 'Risk', 'Portfolio', 
                     'Valuation', 'Growth', 'Momentum', 'Quality', 'Management']
    for factor_pattern in known_factors:
        match = re.search(rf'({factor_pattern})\s*[:：]?\s*(\d+\.?\d*)', text, re.IGNORECASE)
        if match:
            factor_name = match.group(1).strip()
            factor_score = float(match.group(2))
            # Assign default weights based on factor
            weights = {
                'Fundamental': 25, 'Fundamentals': 25,
                'Technical': 20, 'Sentiment': 15,
                'Risk': 20, 'Portfolio': 20,
                'Valuation': 25, 'Growth': 20,
                'Momentum': 15, 'Quality': 20, 'Management': 15,
            }
            weight = weights.get(factor_name, 20)
            rec['breakdown'][factor_name] = {
                'score': factor_score,
                'weight': weight,
                'summary': ''
            }
    
    # 5. Extract Justification (text after "Rationale:" or "Justification:")
    just_match = re.search(r'(?:Rationale|Justification)\s*[:：]\s*(.+?)(?:\n\n|\n(?:\d+\.|Key Levels|Suggested|Avoid|$))', text, re.DOTALL)
    if just_match:
        rec['justification'] = just_match.group(1).strip()
    
    # 6. Extract Key Risks
    risk_section = re.search(r'(?:Key Risks?|Risks? to Monitor)\s*[:：]\s*(.+?)(?:\n\n|\n(?:\d+\.|Suggested|$))', text, re.DOTALL)
    if risk_section:
        risks_text = risk_section.group(1)
        risks = re.findall(r'[•·\-*]\s*(.+?)(?:\n|$)', risks_text)
        if risks:
            rec['risks'] = [r.strip() for r in risks if r.strip()]
    
    # 7. Extract Suggested Action
    suggested_match = re.search(r'(?:Suggested Action|Suggested)\s*[:：]\s*(.+?)(?:\n\n|\n(?:\d+\.|$))', text, re.DOTALL)
    if suggested_match:
        rec['suggested_action'] = suggested_match.group(1).strip()
    
    # If no breakdown was found but we have a score, create a simple breakdown
    if not rec['breakdown'] and rec['score'] > 0:
        rec['breakdown'] = {
            'Overall': {
                'score': rec['score'],
                'weight': 100,
                'summary': 'Aggregate score from agent analysis'
            }
        }
    
    return rec


def main():
    """Main entry point for the multi-agent stock analysis system."""
    parser = argparse.ArgumentParser(
        description="Indian Stock Market Multi-Agent Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py --stock RELIANCE
  python src/main.py --stock TCS --analysis_type technical
  python src/main.py --stock HDFCBANK --analysis_type quick --max_round 8
  python src/main.py --stock INFY --analysis_type fundamental --verbose
  python src/main.py --stock RELIANCE --output                        # Save report to file
  python src/main.py --stock TCS --output --format md                 # Save as Markdown
  python src/main.py --stock INFY --output --format txt               # Save as plain text
  python src/main.py --stock RELIANCE --fresh                         # Bypass cache for fresh data
  python src/main.py --stock TCS --fresh --output --format md         # Fresh data + Markdown report
        """
    )
    parser.add_argument(
        "--stock", type=str, required=True,
        help="Stock symbol to analyze (e.g., RELIANCE, TCS, HDFCBANK)"
    )
    parser.add_argument(
        "--exchange", type=str, default="NSE", choices=["NSE", "BSE"],
        help="Stock exchange (default: NSE)"
    )
    parser.add_argument(
        "--analysis_type", type=str, default="full",
        choices=["full", "fundamental", "technical", "quick"],
        help="Type of analysis to perform (default: full)"
    )
    parser.add_argument(
        "--max_round", type=int, default=12,
        help="Maximum conversation rounds (default: 12 for full analysis)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--output", action="store_true",
        help="Save the analysis report to a file (default: reports/<SYMBOL>_<TIMESTAMP>.txt)"
    )
    parser.add_argument(
        "--format", type=str, default="txt", choices=["txt", "md", "html"],
        help="Output format for the report file: txt (plain text), md (Markdown), or html (HTML) (default: txt)"
    )

    parser.add_argument(
        "--output-dir", type=str, default="reports",
        help="Directory to save report files (default: reports/)"
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Force fresh data by bypassing cache. "
             "This sets SCREENER_CACHE_TTL=0 and adds a cache-busting timestamp to API calls."
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # If --fresh is set, bypass cache
    if args.fresh:
        print("\n🔄 FRESH DATA MODE: Bypassing cache for latest data...")
        os.environ["SCREENER_CACHE_TTL"] = "0"
        # Add a cache-busting timestamp to force fresh data from Screener API
        os.environ["SCREENER_FRESH"] = datetime.now().isoformat()

    try:
        # Validate stock symbol
        symbol = validate_stock_symbol(args.stock)

        # Get LLM configuration
        llm_config = get_llm_config()

        # ===== ANTI-HALLUCINATION: Pre-fetch real market data =====
        print(f"\n{'='*60}")
        print(f"  📡 PHASE 1: PRE-FETCHING REAL MARKET DATA")
        print(f"{'='*60}")
        real_data = prefetch_all_data(symbol, args.exchange)
        grounding_context = build_grounding_context(real_data)
        
        # Print the grounding context for transparency
        print(f"\n{grounding_context}")
        print(f"\n{'='*60}")
        print(f"  🧠 PHASE 2: MULTI-AGENT ANALYSIS")
        print(f"{'='*60}")

        # Create agents with grounding context
        agents, user_proxy = create_agents(llm_config, args.analysis_type, grounding_context)

        # Build the query
        if args.analysis_type == "fundamental":
            query = (
                f"Analyze {symbol} on {args.exchange} using Screener.in data. "
                f"Provide comprehensive fundamental analysis including financial health, "
                f"key ratios, growth metrics, and peer comparison. "
                f"Then provide a final recommendation (BUY/SELL/HOLD) with confidence level."
            )
        elif args.analysis_type == "technical":
            query = (
                f"Analyze {symbol} on {args.exchange} from a technical perspective. "
                f"Provide RSI, MACD, moving averages, Bollinger Bands, volume analysis, "
                f"and support/resistance levels. "
                f"Then provide a final recommendation (BUY/SELL/HOLD) with confidence level."
            )
        elif args.analysis_type == "quick":
            query = (
                f"Provide a quick overview of {symbol} on {args.exchange}. "
                f"Cover key fundamentals, technical indicators, and a brief recommendation."
            )
        else:
            query = (
                f"Analyze {symbol} on {args.exchange} comprehensively. "
                f"Market Researcher: Provide fundamentals, ratios, financials, and peer comparison. "
                f"Technical Analyst: Provide RSI, MACD, moving averages, and trend analysis. "
                f"Sentiment Analyst: Fetch and analyze recent news and market sentiment. "
                f"Risk Manager: Assess volatility, drawdown risk, and provide risk score. "
                f"Portfolio Manager: Evaluate sector fit and suggest allocation. "
                f"Strategy Manager: Synthesize all inputs and provide a weighted final recommendation (BUY/SELL/HOLD). "
                f"Critic: Challenge the recommendation and identify any overlooked risks."
            )

        # Configure group chat
        # Calculate appropriate max_round based on number of agents
        calculated_rounds = max(args.max_round, len(agents) * 2)
        
        # ===== ANTI-HALLUCINATION: Inject real data as the FIRST message =====
        # This makes the ground truth data an immutable part of the conversation
        # that every agent sees before they start speaking. Unlike system messages,
        # conversation messages cannot be ignored by the LLM.
        initial_message = (
            f"## 📊 GROUND TRUTH DATA FOR {symbol} (REAL MARKET DATA - MUST USE THESE VALUES)\n\n"
            f"{grounding_context}\n\n"
            f"---\n"
            f"**IMPORTANT INSTRUCTION FOR ALL AGENTS:** The data above is the ONLY correct data for {symbol}. "
            f"If any agent mentions prices, ratios, or metrics that differ from this ground truth data, "
            f"they are WRONG. You MUST correct them using the values above. "
            f"Never make up or guess numbers - use ONLY what is shown above."
        )
        
        groupchat = GroupChat(
            agents=agents,
            messages=[{"role": "user", "content": initial_message, "name": "system"}],
            max_round=calculated_rounds,
            allow_repeat_speaker=False,
            speaker_selection_method="round_robin"
        )

        manager_agent = GroupChatManager(
            groupchat=groupchat,
            llm_config=llm_config
        )

        print("\n" + "=" * 80)
        print(f"  INDIAN STOCK MARKET MULTI-AGENT ANALYSIS")
        print(f"  Stock: {symbol} | Exchange: {args.exchange}")
        print(f"  Analysis Type: {args.analysis_type.upper()}")
        print(f"  Max Rounds: {calculated_rounds}")
        if args.fresh:
            print(f"  Data Mode: FRESH (cache bypassed)")
        if args.output:
            print(f"  Output: Save to {args.output_dir}/ ({args.format.upper()} format)")
        print("=" * 80)
        print(f"\nStarting multi-agent discussion...\n")

        # Capture the conversation summary with retry logic for transient API errors
        @retry_on_api_error(max_retries=3, base_delay=3.0, backoff_factor=2.0)
        def run_analysis_chat():
            """Run the multi-agent chat analysis with retry support."""
            return user_proxy.initiate_chat(
                manager_agent,
                message=query,
                summary_method="reflection_with_llm",
                summary_args={
                    "summary_prompt": (
                        "Provide a concise summary of the analysis including: "
                        "1) Key fundamental metrics, "
                        "2) Technical outlook, "
                        "3) Sentiment/catalysts, "
                        "4) Risk assessment, "
                        "5) Final recommendation with confidence level. "
                        "6) Score: X.X/10 (a numeric weighted score out of 10). "
                        "IMPORTANT: You MUST include a line like 'Score: X.X/10' with a numeric value."
                    )
                }
            )

        chat_result = run_analysis_chat()
        
        # ===== EXTRACT INDIVIDUAL AGENT SUMMARIES =====
        agent_summaries = {}
        if hasattr(chat_result, 'chat_history') and chat_result.chat_history:
            for msg in chat_result.chat_history:
                speaker = msg.get('name', '') or msg.get('role', '')
                content = msg.get('content', '')
                if speaker and content and speaker.lower() != 'user' and speaker.lower() != 'system':
                    # Skip the initial grounding message
                    if 'GROUND TRUTH DATA' in content or 'REAL MARKET DATA' in content:
                        continue
                    if speaker not in agent_summaries:
                        agent_summaries[speaker] = []
                    agent_summaries[speaker].append(content)
        
        # Join multi-message agents into single text
        for agent_name in agent_summaries:
            agent_summaries[agent_name] = "\n\n".join(agent_summaries[agent_name])
        
        print(f"\n  📋 Extracted summaries from {len(agent_summaries)} agents: {', '.join(agent_summaries.keys())}")


        print("\n" + "=" * 80)
        print("  ANALYSIS COMPLETE")
        print("=" * 80)

        # ===== SAVE REPORT TO FILE =====
        if args.output:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract summary from chat result
            summary_text = chat_result.summary if hasattr(chat_result, 'summary') else ""
            
            # ===== BUILD STRUCTURED DATA FOR REPORTS =====
            tech_data = real_data.get('technical', {})
            risk_data = real_data.get('risk', {})
            
            # Build fundamental_data by merging ALL available data sources
            fundamental_data = {}
            
            # 1. Parse Screener API data (overview.top_ratios + table rows)
            screener_raw = real_data.get('fundamental', {}).get('screener', {})
            parsed_screener = parse_screener_company_data(screener_raw)
            if parsed_screener:
                for k, v in parsed_screener.items():
                    if v is not None and k not in fundamental_data:
                        fundamental_data[k] = v
            
            # 2. Merge yfinance stock data (sector, industry, PE, market cap, etc.)
            if risk_data:
                for key, val in risk_data.items():
                    if val is not None and key not in fundamental_data:
                        fundamental_data[key] = val
            
            # 3. Map yfinance keys to formatter-expected keys
            if risk_data:
                yfinance_to_formatter = {
                    'pe_ratio': 'pe_ratio',
                    'pb_ratio': 'pb_ratio',
                    'market_cap': 'market_cap',
                    'dividend_yield': 'dividend_yield',
                    'sector': 'sector',
                    'industry': 'industry',
                    'company_name': 'company_name',
                }
                for yf_key, formatter_key in yfinance_to_formatter.items():
                    val = risk_data.get(yf_key)
                    if val is not None and formatter_key not in fundamental_data:
                        fundamental_data[formatter_key] = val
            
            # 4. Calculate risk_score from available data
            # Risk score = composite of: beta, volatility, debt/equity, PE premium
            risk_score = None
            try:
                beta = risk_data.get('beta')
                pe = fundamental_data.get('pe_ratio', risk_data.get('pe_ratio'))
                debt_eq = fundamental_data.get('debt_to_equity')
                
                score = 5.0  # Start at neutral
                
                # Beta contribution (0.37 = low risk, >1.5 = high risk)
                if beta is not None:
                    beta_f = float(beta)
                    if beta_f < 0.5: score -= 1.5  # Very defensive
                    elif beta_f < 0.8: score -= 1.0
                    elif beta_f < 1.0: score -= 0.5
                    elif beta_f > 1.5: score += 1.5
                    elif beta_f > 1.2: score += 1.0
                    elif beta_f > 1.0: score += 0.5
                
                # PE ratio contribution (high PE = more risk)
                if pe is not None:
                    pe_f = float(pe)
                    if pe_f > 50: score += 2.0
                    elif pe_f > 30: score += 1.0
                    elif pe_f > 20: score += 0.5
                    elif pe_f < 10: score -= 1.0
                
                # Debt/Equity contribution
                if debt_eq is not None:
                    de_f = float(debt_eq)
                    if de_f > 2.0: score += 2.0
                    elif de_f > 1.0: score += 1.0
                    elif de_f > 0.5: score += 0.5
                    elif de_f < 0.2: score -= 0.5
                
                # Clamp to 1-10 range
                risk_score = max(1.0, min(10.0, round(score, 1)))
            except (ValueError, TypeError):
                risk_score = None
            
            if risk_score is not None:
                risk_data['risk_score'] = risk_score
            
            # 5. Keep original nested structure for _get_fundamental_val helper
            screener_data = real_data.get('fundamental', {})
            fundamental_data['screener'] = screener_data.get('screener', {})
            fundamental_data['ratios'] = screener_data.get('ratios', {})
            fundamental_data['profit-loss'] = screener_data.get('profit-loss', {})
            fundamental_data['balance-sheet'] = screener_data.get('balance-sheet', {})
            fundamental_data['cash-flow'] = screener_data.get('cash-flow', {})
            
            # Debug: print available keys
            print(f"\n  📊 Report data keys available:")
            print(f"     Fundamental: {[k for k in fundamental_data.keys() if not k.startswith('_') and k not in ('screener', 'ratios', 'company', 'financials', 'profit-loss', 'balance-sheet', 'cash-flow')][:25]}")
            print(f"     Technical: {list(tech_data.keys())[:10]}")
            print(f"     Risk: {list(risk_data.keys())[:10]}")
            
            sentiment_data = real_data.get('sentiment', {})

            # ===== PARSE RECOMMENDATION FROM AGENT CONVERSATION =====
            recommendation = parse_recommendation_from_summary(summary_text)
            print(f"\n  🎯 Parsed Recommendation: {recommendation.get('action')} | "
                  f"Score: {recommendation.get('score')}/10 | "
                  f"Confidence: {recommendation.get('confidence')}")
            if recommendation.get('breakdown'):
                breakdown_str = ', '.join(f"{k}: {v['score']}/10" for k, v in recommendation['breakdown'].items())
                print(f"     Breakdown: {breakdown_str}")
            
            # Build the report
            if args.format == "md":
                report = ReportFormatter.format_markdown_report(
                    symbol=symbol,
                    exchange=args.exchange,
                    analysis_type=args.analysis_type,
                    timestamp=timestamp,
                    fundamental_data=fundamental_data,
                    technical_data=tech_data,
                    sentiment_data=sentiment_data,
                    risk_data=risk_data,
                    portfolio_data=None,
                    recommendation=recommendation,
                    critique=None,
                    raw_conversation=summary_text,
                    agent_summaries=agent_summaries,
                )
            elif args.format == "html":
                report = ReportFormatter.format_html_report(
                    symbol=symbol,
                    exchange=args.exchange,
                    analysis_type=args.analysis_type,
                    timestamp=timestamp,
                    fundamental_data=fundamental_data,
                    technical_data=tech_data,
                    sentiment_data=sentiment_data,
                    risk_data=risk_data,
                    portfolio_data=None,
                    recommendation=recommendation,
                    critique=None,
                    raw_conversation=summary_text,
                    agent_summaries=agent_summaries,
                )
            else:
                report = ReportFormatter.format_analysis_summary(
                    symbol=symbol,
                    exchange=args.exchange,
                    analysis_type=args.analysis_type,
                    timestamp=timestamp,
                    fundamental_data=fundamental_data,
                    technical_data=tech_data,
                    sentiment_data=sentiment_data,
                    risk_data=risk_data,
                    portfolio_data=None,
                    recommendation=recommendation,
                    critique=None,
                    raw_conversation=summary_text,
                    agent_summaries=agent_summaries,
                )
            
            # Save the report
            filepath = ReportFormatter.save_report(
                report=report,
                symbol=symbol,
                output_dir=args.output_dir,
                fmt=args.format
            )
            
            print(f"\n📄 Report saved to: {os.path.abspath(filepath)}")
            print(f"   Format: {args.format.upper()}")
            print(f"   Size: {os.path.getsize(filepath):,} bytes")


    except ValueError as e:
        print(f"\nConfiguration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(0)
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unexpected error during analysis")
        print(f"\nUnexpected Error: {e}", file=sys.stderr)
        
        # Provide helpful guidance for common API errors
        if "504" in error_msg or "502" in error_msg or "503" in error_msg:
            print("\n💡 TIP: This is a server-side timeout error from the LLM API provider.", file=sys.stderr)
            print("   The API server is temporarily overloaded or unreachable.", file=sys.stderr)
            print("   Suggestions:", file=sys.stderr)
            print("   • Wait a few minutes and try again (the issue is usually transient)", file=sys.stderr)
            print("   • Check your internet connection", file=sys.stderr)
            print("   • Try a different model by updating your .env file", file=sys.stderr)
            print("   • Use --verbose for more detailed logs", file=sys.stderr)
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            print("\n💡 TIP: Rate limit exceeded. The API is receiving too many requests.", file=sys.stderr)
            print("   Suggestions:", file=sys.stderr)
            print("   • Wait a minute before trying again", file=sys.stderr)
            print("   • Reduce the number of concurrent analyses", file=sys.stderr)
        elif "401" in error_msg or "unauthorized" in error_msg.lower() or "authentication" in error_msg.lower():
            print("\n💡 TIP: Authentication failed. Your API key may be invalid or expired.", file=sys.stderr)
            print("   Check your .env file and verify the API key is correct.", file=sys.stderr)
        
        print("\nPlease check the logs above for more details.", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    main()
