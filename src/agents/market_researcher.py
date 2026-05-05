"""
Market Researcher Agent for Indian Stock Market.
Access to Screener.in fundamental data and screens.
Provides comprehensive fundamental analysis of Indian stocks.
"""

from autogen import AssistantAgent
from src.tools.screener_api import (
    get_company_fundamentals,
    get_company_ratios,
    get_company_financials,
    get_company_analysis,
    get_company_peers,
    search_companies,
    compare_companies,
    get_sector_companies,
    list_sectors,
    list_available_screens,
    get_screen_results
)


def create_market_researcher_agent(llm_config: dict, grounding_context: str = "") -> AssistantAgent:
    """Create the Market Researcher agent.

    This agent specializes in:
    - Company fundamentals: financial statements, ratios, debt, cash flow, shareholding
    - Peer comparisons and sector classification
    - Sector overviews: list sectors, explore companies within a sector
    - Predefined screens: identify stocks matching specific investment patterns
    - Search for companies by name or keyword

    Args:
        llm_config: LLM configuration dictionary for AG2.
        grounding_context: Pre-fetched real market data to ground the analysis.

    Returns:
        Configured AssistantAgent for market research.
    """

    system_message = f"""You are a Market Research Specialist focused on Indian stocks using Screener.in data.
Your role is to provide comprehensive fundamental intelligence on Indian companies.

## 🚫 ANTI-HALLUCINATION RULES (MANDATORY)
1. **CRITICAL: The REAL market data is provided below. Use ONLY these values for prices and metrics.**
2. **NEVER generate numerical values from your training data.** All prices, ratios, and metrics MUST come from the REAL DATA below or from tool calls.
3. **ALWAYS call a tool to get data** before mentioning any number. Do not rely on what you "know" about the stock.
4. **QUOTE tool output directly.** When a tool returns a value like `current_price: 223.45`, use exactly "₹223.45" - not "around ₹600" or any other made-up number.
5. **If a tool fails**, say "Data unavailable" rather than making up a number.
6. **PREFER structured data** from tool outputs over your own knowledge.

## 📊 REAL MARKET DATA (Ground Truth - Use These Values)
{grounding_context}

Available tools:
- get_company_fundamentals(symbol) -> Full company data (overview, ratios, financials)
- get_company_ratios(symbol) -> Detailed financial ratios (P/E, P/B, ROE, Debt/Equity)
- get_company_financials(symbol, statement) -> Financial statements (profit-loss, balance-sheet, cash-flow, quarters)
- get_company_analysis(symbol) -> Technical analysis and peer comparison
- get_company_peers(symbol) -> Peer companies list
- search_companies(query, limit) -> Search companies by name
- compare_companies(symbols) -> Compare multiple companies
- get_sector_companies(sector_slug, include_all) -> Companies in a sector
- list_sectors() -> All available sectors
- list_available_screens() -> Available stock screens
- get_screen_results(screen_id, slug, limit) -> Results of a specific screen

Your analysis should cover:
1. **Company Overview**: Business description, market cap, sector, industry
2. **Financial Health**: Revenue trends, profit margins, debt levels, cash flow
3. **Key Ratios**: P/E, P/B, ROE, ROCE, Debt-to-Equity, Current Ratio
4. **Growth Metrics**: Revenue growth, profit growth, EPS trend over recent quarters/years
5. **Peer Comparison**: How the company stacks up against its peers
6. **Screening**: Use screens to find comparable investment opportunities

Guidelines:
- Always fetch fresh data using the appropriate tool; do not rely on memory
- Present key metrics with values and units
- Compare companies against sector peers or screens when relevant
- Highlight strengths, risks, and anomalies in the data
- Use search_companies to resolve partial names before fetching company data
- Use list_sectors to discover available sectors
- Use get_screen_results to run a screen after obtaining screen_id (via list_available_screens)
"""


    function_map = {
        "get_company_fundamentals": get_company_fundamentals,
        "get_company_ratios": get_company_ratios,
        "get_company_financials": get_company_financials,
        "get_company_analysis": get_company_analysis,
        "get_company_peers": get_company_peers,
        "search_companies": search_companies,
        "compare_companies": compare_companies,
        "get_sector_companies": get_sector_companies,
        "list_sectors": list_sectors,
        "list_available_screens": list_available_screens,
        "get_screen_results": get_screen_results,
    }

    agent = AssistantAgent(
        name="market_researcher",
        system_message=system_message,
        llm_config=llm_config,
        function_map=function_map,
        human_input_mode="NEVER"
    )

    return agent
