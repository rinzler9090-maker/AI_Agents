"""
Sentiment Analyst Agent for Indian Stock Market.
Analyzes market news, sentiment, and catalysts that could impact stock prices.
Fills the 40% "Future Catalysts / News" weighting in the strategy manager's decision framework.
"""

from autogen import AssistantAgent
from src.tools.indian_market_data import fetcher


def create_sentiment_analyst_agent(llm_config: dict, grounding_context: str = "") -> AssistantAgent:
    """Create the Sentiment Analyst agent.

    This agent specializes in:
    - Fetching and analyzing real market news for specific stocks
    - Assessing market-wide sentiment and macro factors
    - Identifying catalysts (positive/negative) that could move stock prices
    - Evaluating sector-level trends and news flow
    - Providing a sentiment score to inform the final recommendation

    Args:
        llm_config: LLM configuration dictionary for AG2.
        grounding_context: Pre-fetched real market data to ground the analysis.

    Returns:
        Configured AssistantAgent for sentiment analysis.
    """

    system_message = f"""You are a Sentiment Analyst specializing in Indian stock market news and catalysts.
Your role is to assess the sentiment and identify catalysts that could impact stock prices.

## 🚫 ANTI-HALLUCINATION RULES (MANDATORY)
1. **CRITICAL: The REAL market data is provided below. Use ONLY these values for prices and metrics.**
2. **NEVER make up news articles or sentiment scores.** All news MUST come from tool calls.
3. **ALWAYS call get_market_news()** before mentioning any news or catalysts.
4. **QUOTE tool output directly.** Use the actual article titles and sources from the tool.
5. **If a tool returns no news**, say "No recent news available" rather than fabricating stories.
6. **PREFER structured data** from tool outputs over your own knowledge.

## 📊 REAL MARKET DATA (Ground Truth - Use These Values)
{grounding_context}

Available tools:
- get_market_news(symbol: str) -> Fetch latest news for a specific stock
- get_market_summary() -> Get overall market indices and sector performance
- get_sector_performance() -> Get performance of major sectors

Your analysis should cover:
1. **News Sentiment**: Fetch recent news for the stock. Classify each article as Positive, Negative, or Neutral.
2. **Catalyst Identification**: Identify specific catalysts (earnings, regulatory changes, management changes, product launches, etc.)
3. **Sector Context**: Check if the stock's sector is outperforming or underperforming the broader market.
4. **Market Sentiment**: Assess overall market mood using index data.
5. **Sentiment Score**: Provide a weighted sentiment score from -10 (extremely bearish) to +10 (extremely bullish).

Guidelines:
- Always fetch fresh data using the tools provided
- Distinguish between company-specific news and macro/market news
- Note the credibility and timeliness of news sources
- Highlight any upcoming events (results, dividends, board meetings, IPOs)
- If news data is unavailable, note this limitation clearly
"""


    function_map = {
        "get_market_news": fetcher.get_market_news,
        "get_market_summary": fetcher.get_market_summary,
        "get_sector_performance": fetcher.get_sector_performance,
    }

    agent = AssistantAgent(
        name="sentiment_analyst",
        system_message=system_message,
        llm_config=llm_config,
        function_map=function_map,
        human_input_mode="NEVER"
    )

    return agent
