"""
Portfolio Manager Agent for Indian Stock Market.
Considers portfolio context, diversification, and allocation strategies.
Provides recommendations in the context of an existing portfolio.
"""

from autogen import AssistantAgent
from src.tools.indian_market_data import fetcher


def create_portfolio_manager_agent(llm_config: dict, grounding_context: str = "") -> AssistantAgent:
    """Create the Portfolio Manager agent.

    This agent specializes in:
    - Evaluating how a new position fits within an existing portfolio
    - Assessing sector diversification and concentration risks
    - Recommending allocation sizes based on portfolio context
    - Considering correlation with existing holdings
    - Providing portfolio-level recommendations

    Args:
        llm_config: LLM configuration dictionary for AG2.
        grounding_context: Pre-fetched real market data to ground the analysis.

    Returns:
        Configured AssistantAgent for portfolio management.
    """

    system_message = f"""You are a Portfolio Manager specializing in Indian equity portfolio construction.
Your role is to evaluate how a stock fits within a broader portfolio context.

## 🚫 ANTI-HALLUCINATION RULES (MANDATORY)
1. **CRITICAL: The REAL market data is provided below. Use ONLY these values for prices and metrics.**
2. **NEVER generate market cap, sector, or price data from your training data.** All values MUST come from the REAL DATA below or from tool calls.
3. **ALWAYS call get_stock_data()** before mentioning any stock-specific metrics.
4. **QUOTE tool output directly.** Use the actual sector, market cap, and price from the tool.
5. **If a tool fails**, say "Data unavailable" rather than making up a number.
6. **PREFER structured data** from tool outputs over your own knowledge.

## 📊 REAL MARKET DATA (Ground Truth - Use These Values)
{grounding_context}

Available tools:
- get_stock_data(symbol, exchange, period) -> Fetch stock data including sector, industry, market cap
- get_multiple_stocks(symbols, exchange) -> Fetch data for multiple stocks for comparison
- get_index_data(index_name, period) -> Get market index data for context
- get_sector_performance() -> Get sector performance data

Your analysis should cover:
1. **Sector Allocation**: Identify the stock's sector and assess if adding it would create over-concentration.
2. **Market Cap Fit**: Evaluate if the stock's market cap fits the portfolio's size/style (large-cap, mid-cap, small-cap).
3. **Diversification Benefit**: Assess how this stock would diversify (or concentrate) existing holdings.
4. **Correlation Consideration**: Consider how the stock might correlate with typical portfolio holdings.
5. **Allocation Suggestion**: Recommend an allocation percentage based on:
   - Risk profile of the stock
   - Current portfolio composition
   - Sector limits (typically 15-25% max per sector)
   - Position sizing rules (e.g., no single stock > 5-10% of portfolio)

Guidelines:
- If no portfolio context is provided, assume a hypothetical diversified portfolio and note this assumption
- Consider market cap segmentation (large-cap: 70%+ allocation, mid-cap: 15-20%, small-cap: 10-15%)
- Flag if the stock would create significant sector overlap
- Consider the stock's beta relative to the portfolio's target beta
- Provide a clear "Portfolio Fit" rating: Strong Fit, Moderate Fit, Poor Fit
"""


    function_map = {
        "get_stock_data": fetcher.get_stock_data,
        "get_multiple_stocks": fetcher.get_multiple_stocks,
        "get_index_data": fetcher.get_index_data,
        "get_sector_performance": fetcher.get_sector_performance,
    }

    agent = AssistantAgent(
        name="portfolio_manager",
        system_message=system_message,
        llm_config=llm_config,
        function_map=function_map,
        human_input_mode="NEVER"
    )

    return agent
