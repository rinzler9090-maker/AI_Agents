# Indian Stock Market Multi-Agent System

A sophisticated multi-agent system built with **AG2 (AutoGen)** for comprehensive analysis of Indian stocks. The system orchestrates 8 specialized AI agents that collaborate to provide fundamental analysis, technical analysis, sentiment assessment, risk management, portfolio context, and a final weighted recommendation.

## Features

### 8 Specialized Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Market Researcher** | Fundamental analysis via Screener.in | Financials, ratios, peers, sectors, screens |
| **Technical Analyst** | Price action & indicators | RSI, MACD, MAs, Bollinger Bands, volume |
| **Sentiment Analyst** | News & market sentiment | Real news via yfinance, sector performance |
| **Risk Manager** | Volatility & risk assessment | Beta, drawdown, position sizing |
| **Portfolio Manager** | Diversification & allocation | Sector fit, market cap, correlation |
| **Strategy Manager** | Weighted final decision | Synthesizes all inputs (35/25/20/10/10 weighting) |
| **Critic** | Devil's advocate | Stress-tests recommendations |

### Analysis Modes

- **Full Analysis** (default): All 8 agents for comprehensive coverage
- **Fundamental Analysis**: Market Researcher + Strategy Manager + Critic
- **Technical Analysis**: Technical Analyst + Strategy Manager + Critic
- **Quick Analysis**: Market Researcher + Technical Analyst + Strategy Manager

### Data Sources

- **Screener.in API** (unofficial): Fundamental data, ratios, financials, screens
- **Yahoo Finance (yfinance)**: Real-time prices, historical data, news, technical indicators
- **NSE/BSE**: Indian stock exchange data

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd AI_Agents

# Create virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the root directory (copy from `.env.example`):

```env
# Choose ONE of the following LLM providers:

# OpenAI
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4

# OR Anthropic
# ANTHROPIC_API_KEY=your-api-key-here
# ANTHROPIC_MODEL=claude-3-opus-20240229

# OR NVIDIA NIM (OpenAI-compatible)
# NIM_API_KEY=your-nvidia-api-key-here
# NIM_MODEL=meta/llama3-70b-instruct
# NIM_BASE=https://integrate.api.nvidia.com/v1

# Screener API (optional - for running the Screener.in MCP server)
# SCREENER_API_BASE_URL=http://127.0.0.1:8000
# SCREENER_API_KEY=optional-api-key
```

## Usage

### 🖥️ Web App (Browser-based with WebLLM)

Run the AI analysis entirely in your browser using WebLLM (no API keys needed for the AI model):

```bash
# Start the data proxy server
python src/web_app.py
```

Then open **http://127.0.0.1:8000** in your browser.

**How it works:**
1. The Python server acts as a **data proxy** — it fetches real stock data from Screener.in, Yahoo Finance, and Alpha Vantage
2. The AI model (**WebLLM**) runs **directly in your browser** using WebGPU — no cloud API calls needed
3. Select a stock, choose analysis type, and get AI-powered analysis with real market data

> **Note:** The first load will download the WebLLM model (~2-4 GB) to your browser cache. This is a one-time download.

### 🖥️ CLI (Multi-Agent System)

For the full multi-agent experience with 8 specialized AI agents:

```bash
# Full analysis with all 8 agents (default)
python src/main.py --stock RELIANCE
# OR: python -m src.main --stock RELIANCE

# Technical analysis only
python src/main.py --stock TCS --analysis_type technical

# Quick overview
python src/main.py --stock HDFCBANK --analysis_type quick

# Fundamental analysis with verbose logging
python src/main.py --stock INFY --analysis_type fundamental --verbose

# Specify BSE exchange
python src/main.py --stock RELIANCE --exchange BSE

# Custom conversation rounds
python src/main.py --stock WIPRO --max_round 15
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--stock` | (required) | Stock symbol (e.g., RELIANCE, TCS) |
| `--exchange` | NSE | Stock exchange (NSE or BSE) |
| `--analysis_type` | full | Analysis mode: full, fundamental, technical, quick |
| `--max_round` | 12 | Maximum conversation rounds |
| `--verbose` | false | Enable debug logging |
| `--output` | false | Save analysis report to a file |
| `--format` | txt | Output format: `txt` (plain text) or `md` (Markdown) |
| `--output-dir` | reports | Directory to save report files |
| `--fresh` | false | Bypass cache for fresh Screener.in data |

### Output Examples

```bash
# Save report as plain text (default)
python src/main.py --stock RELIANCE --output

# Save report as Markdown (great for GitHub/docs)
python src/main.py --stock TCS --output --format md

# Save to a custom directory
python src/main.py --stock INFY --output --output-dir my_reports

# Fresh data + Markdown report
python src/main.py --stock HDFCBANK --fresh --output --format md
```

Reports are saved to the `reports/` directory (or custom `--output-dir`) with filenames like:
- `RELIANCE_20260405_143022.txt` (plain text)
- `TCS_20260405_143022.md` (Markdown)

### Fresh Data Mode

The Screener.in API caches data for 5 minutes by default. To get the latest data:

```bash
# Bypass cache for this analysis
python src/main.py --stock RELIANCE --fresh

# Fresh data + save report
python src/main.py --stock TCS --fresh --output --format md
```

The `--fresh` flag:
1. Sets `SCREENER_CACHE_TTL=0` to bypass the API's internal cache
2. Adds a cache-busting timestamp parameter to every API request
3. Ensures you get the most recent data from Screener.in

> **Note:** Screener.in data itself may have a delay (typically 1 day for financial statements). For real-time price data, the system uses yfinance which is always live.


## Project Structure

```
AI_Agents/
├── src/
│   ├── agents/
│   │   ├── market_researcher.py   # Fundamental analysis agent
│   │   ├── technical_analyst.py   # Technical analysis agent
│   │   ├── sentiment_analyst.py   # News & sentiment agent
│   │   ├── risk_manager.py        # Risk assessment agent
│   │   ├── portfolio_manager.py   # Portfolio context agent
│   │   ├── strategy_manager.py    # Final decision agent
│   │   └── critic.py              # Devil's advocate agent
│   ├── tools/
│   │   ├── screener_api.py        # Screener.in API client
│   │   └── indian_market_data.py  # yfinance data fetcher
│   ├── utils/
│   │   └── helpers.py             # LLM config, validation
│   └── main.py                    # Entry point
├── tests/                         # Unit tests
├── requirements.txt               # Dependencies
└── README.md                      # Documentation
```

## Decision Framework

The Strategy Manager uses a weighted framework to produce the final recommendation:

| Factor | Weight | Source Agent |
|--------|--------|-------------|
| Fundamentals | 35% | Market Researcher |
| Catalysts/Sentiment | 25% | Sentiment Analyst |
| Technical Analysis | 20% | Technical Analyst |
| Risk Assessment | 10% | Risk Manager |
| Portfolio Context | 10% | Portfolio Manager |

## Requirements

- Python 3.9+
- AG2 (AutoGen) >= 0.2.0
- yfinance >= 0.2.0
- pandas >= 2.0.0
- numpy >= 1.24.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0

## License

MIT
