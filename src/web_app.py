"""
Web Application for Indian Stock Market Analysis.
Serves as a data proxy - fetches stock data from Screener API, yfinance, Alpha Vantage.
WebLLM runs in the browser for AI analysis.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

# Ensure the project root is in the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import jinja2

from src.tools.screener_api import screener, search_companies
from src.tools.indian_market_data import fetcher
from src.tools.alpha_vantage import is_available as av_is_available
from src.tools.alpha_vantage import get_news_for_sentiment_analyst as av_get_news
from src.tools.data_prefetcher import prefetch_all_data, build_grounding_context, parse_screener_company_data

logger = logging.getLogger(__name__)


# ============================================================
# FastAPI Application
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logging.basicConfig(level=logging.INFO)
    logger.info("🚀 Stock Analysis Data Proxy starting...")
    yield
    logger.info("Shutting down...")

app = FastAPI(title="Indian Stock Market Analysis - Data Proxy", lifespan=lifespan)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
template_loader = jinja2.FileSystemLoader(templates_dir)
template_env = jinja2.Environment(loader=template_loader, autoescape=True)


# ============================================================
# API Routes - Data Proxy
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web page."""
    template = template_env.get_template("index.html")
    html = template.render()
    return HTMLResponse(html)


# Local cache of NSE stocks for instant search (deduplicated)
NSE_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "sector": "Oil & Gas"},
    {"symbol": "TCS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "sector": "Banking"},
    {"symbol": "INFY", "name": "Infosys Ltd", "sector": "IT"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "sector": "Banking"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "sector": "Automobile"},
    {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "sector": "Telecom"},
    {"symbol": "ITC", "name": "ITC Ltd", "sector": "FMCG"},
    {"symbol": "WIPRO", "name": "Wipro Ltd", "sector": "IT"},
    {"symbol": "TATASTEEL", "name": "Tata Steel Ltd", "sector": "Metals & Mining"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "sector": "FMCG"},
    {"symbol": "NTPC", "name": "NTPC Ltd", "sector": "Power"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "sector": "Automobile"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd", "sector": "Pharma"},
    {"symbol": "TATAPOWER", "name": "Tata Power Co Ltd", "sector": "Power"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd", "sector": "Conglomerate"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "sector": "Finance"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "sector": "Banking"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd", "sector": "Construction"},
    {"symbol": "ADANIPORTS", "name": "Adani Ports and Special Economic Zone Ltd", "sector": "Infrastructure"},
    {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "sector": "Consumer Durables"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd", "sector": "Banking"},
    {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd", "sector": "Finance"},
    {"symbol": "BPCL", "name": "Bharat Petroleum Corporation Ltd", "sector": "Oil & Gas"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries Ltd", "sector": "FMCG"},
    {"symbol": "CIPLA", "name": "Cipla Ltd", "sector": "Pharma"},
    {"symbol": "COALINDIA", "name": "Coal India Ltd", "sector": "Metals & Mining"},
    {"symbol": "DIVISLAB", "name": "Divi's Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "EICHERMOT", "name": "Eicher Motors Ltd", "sector": "Automobile"},
    {"symbol": "GRASIM", "name": "Grasim Industries Ltd", "sector": "Cement"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Ltd", "sector": "IT"},
    {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd", "sector": "Automobile"},
    {"symbol": "HINDALCO", "name": "Hindalco Industries Ltd", "sector": "Metals & Mining"},
    {"symbol": "ICICIPRULI", "name": "ICICI Prudential Life Insurance Co Ltd", "sector": "Insurance"},
    {"symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd", "sector": "Banking"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd", "sector": "Metals & Mining"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra Ltd", "sector": "Automobile"},
    {"symbol": "NESTLEIND", "name": "Nestle India Ltd", "sector": "FMCG"},
    {"symbol": "ONGC", "name": "Oil and Natural Gas Corporation Ltd", "sector": "Oil & Gas"},
    {"symbol": "POWERGRID", "name": "Power Grid Corporation of India Ltd", "sector": "Power"},
    {"symbol": "SBILIFE", "name": "SBI Life Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "SHREECEM", "name": "Shree Cement Ltd", "sector": "Cement"},
    {"symbol": "TATACONSUM", "name": "Tata Consumer Products Ltd", "sector": "FMCG"},
    {"symbol": "TECHM", "name": "Tech Mahindra Ltd", "sector": "IT"},
    {"symbol": "TITAN", "name": "Titan Company Ltd", "sector": "Consumer Durables"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd", "sector": "Cement"},
    {"symbol": "UPL", "name": "UPL Ltd", "sector": "Agrochemicals"},
    {"symbol": "ADANIGREEN", "name": "Adani Green Energy Ltd", "sector": "Power"},
    {"symbol": "ADANIPOWER", "name": "Adani Power Ltd", "sector": "Power"},
    {"symbol": "ADANITRANS", "name": "Adani Transmission Ltd", "sector": "Power"},
    {"symbol": "AMBUJACEM", "name": "Ambuja Cements Ltd", "sector": "Cement"},
    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto Ltd", "sector": "Automobile"},
    {"symbol": "BANDHANBNK", "name": "Bandhan Bank Ltd", "sector": "Banking"},
    {"symbol": "BERGEPAINT", "name": "Berger Paints India Ltd", "sector": "Consumer Durables"},
    {"symbol": "BIOCON", "name": "Biocon Ltd", "sector": "Pharma"},
    {"symbol": "BOSCHLTD", "name": "Bosch Ltd", "sector": "Automobile"},
    {"symbol": "CADILAHC", "name": "Cadila Healthcare Ltd", "sector": "Pharma"},
    {"symbol": "COLPAL", "name": "Colgate Palmolive (India) Ltd", "sector": "FMCG"},
    {"symbol": "CONCOR", "name": "Container Corporation of India Ltd", "sector": "Logistics"},
    {"symbol": "DABUR", "name": "Dabur India Ltd", "sector": "FMCG"},
    {"symbol": "DLF", "name": "DLF Ltd", "sector": "Real Estate"},
    {"symbol": "GAIL", "name": "GAIL (India) Ltd", "sector": "Oil & Gas"},
    {"symbol": "GODREJCP", "name": "Godrej Consumer Products Ltd", "sector": "FMCG"},
    {"symbol": "GODREJPROP", "name": "Godrej Properties Ltd", "sector": "Real Estate"},
    {"symbol": "HAVELLS", "name": "Havells India Ltd", "sector": "Consumer Durables"},
    {"symbol": "HDFCAMC", "name": "HDFC Asset Management Company Ltd", "sector": "Finance"},
    {"symbol": "HINDZINC", "name": "Hindustan Zinc Ltd", "sector": "Metals & Mining"},
    {"symbol": "IOC", "name": "Indian Oil Corporation Ltd", "sector": "Oil & Gas"},
    {"symbol": "IRCTC", "name": "Indian Railway Catering and Tourism Corp Ltd", "sector": "Services"},
    {"symbol": "JUBLFOOD", "name": "Jubilant FoodWorks Ltd", "sector": "FMCG"},
    {"symbol": "LICHSGFIN", "name": "LIC Housing Finance Ltd", "sector": "Finance"},
    {"symbol": "MCDOWELL-N", "name": "United Spirits Ltd", "sector": "FMCG"},
    {"symbol": "MUTHOOTFIN", "name": "Muthoot Finance Ltd", "sector": "Finance"},
    {"symbol": "NAUKRI", "name": "Info Edge (India) Ltd", "sector": "IT"},
    {"symbol": "NMDC", "name": "NMDC Ltd", "sector": "Metals & Mining"},
    {"symbol": "PAGEIND", "name": "Page Industries Ltd", "sector": "Consumer Durables"},
    {"symbol": "PATANJALI", "name": "Patanjali Foods Ltd", "sector": "FMCG"},
    {"symbol": "PIDILITIND", "name": "Pidilite Industries Ltd", "sector": "Chemicals"},
    {"symbol": "PIIND", "name": "PI Industries Ltd", "sector": "Agrochemicals"},
    {"symbol": "PNB", "name": "Punjab National Bank", "sector": "Banking"},
    {"symbol": "RAMCOCEM", "name": "The Ramco Cements Ltd", "sector": "Cement"},
    {"symbol": "SAIL", "name": "Steel Authority of India Ltd", "sector": "Metals & Mining"},
    {"symbol": "SRTRANSFIN", "name": "Shriram Transport Finance Co Ltd", "sector": "Finance"},
    {"symbol": "TORNTPHARM", "name": "Torrent Pharmaceuticals Ltd", "sector": "Pharma"},
    {"symbol": "TRENT", "name": "Trent Ltd", "sector": "Retail"},
    {"symbol": "TVSMOTOR", "name": "TVS Motor Company Ltd", "sector": "Automobile"},
    {"symbol": "VEDL", "name": "Vedanta Ltd", "sector": "Metals & Mining"},
    {"symbol": "YESBANK", "name": "Yes Bank Ltd", "sector": "Banking"},
    {"symbol": "ZEEL", "name": "Zee Entertainment Enterprises Ltd", "sector": "Media"},
    {"symbol": "ZOMATO", "name": "Zomato Ltd", "sector": "Services"},
    {"symbol": "DMART", "name": "Avenue Supermarts Ltd", "sector": "Retail"},
    {"symbol": "ICICIGI", "name": "ICICI Lombard General Insurance Co Ltd", "sector": "Insurance"},
    {"symbol": "MARICO", "name": "Marico Ltd", "sector": "FMCG"},
    {"symbol": "MFSL", "name": "Max Financial Services Ltd", "sector": "Finance"},
    {"symbol": "NHPC", "name": "NHPC Ltd", "sector": "Power"},
    {"symbol": "NIACL", "name": "The New India Assurance Co Ltd", "sector": "Insurance"},
    {"symbol": "NYKAA", "name": "FSN E-Commerce Ventures Ltd", "sector": "Retail"},
    {"symbol": "POLICYBZR", "name": "PB Fintech Ltd", "sector": "Finance"},
    {"symbol": "PVRINOX", "name": "PVR INOX Ltd", "sector": "Media"},
    {"symbol": "SBICARD", "name": "SBI Cards and Payment Services Ltd", "sector": "Finance"},
    {"symbol": "SYNGENE", "name": "Syngene International Ltd", "sector": "Pharma"},
    {"symbol": "TATACOMM", "name": "Tata Communications Ltd", "sector": "Telecom"},
    {"symbol": "TATAELXSI", "name": "Tata Elxsi Ltd", "sector": "IT"},
    {"symbol": "VOLTAS", "name": "Voltas Ltd", "sector": "Consumer Durables"},
    {"symbol": "NTPCGREEN", "name": "NTPC Green Energy Ltd", "sector": "Power"},
    {"symbol": "MEESHO", "name": "Meesho Inc", "sector": "E-commerce"},
    {"symbol": "HFCL", "name": "HFCL Ltd", "sector": "Telecom"},
]

@app.get("/api/stocks/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    """Search for Indian stocks by name or symbol - instant local search."""
    try:
        query = q.strip().upper()
        results = []
        
        # Search local cache first (instant)
        for stock in NSE_STOCKS:
            if query in stock["symbol"] or query in stock["name"].upper():
                results.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "sector": stock["sector"],
                    "exchange": "NSE",
                    "source": "local"
                })
                if len(results) >= 15:
                    break
        
        # If no local results, try Screener API (async, non-blocking)
        if not results:
            try:
                screener_results = search_companies(q, limit=10)
                if screener_results and 'error' not in screener_results:
                    companies = screener_results.get('data', screener_results.get('results', []))
                    if isinstance(companies, list):
                        for company in companies:
                            results.append({
                                "symbol": company.get('symbol', company.get('ticker', '')),
                                "name": company.get('company_name', company.get('name', '')),
                                "sector": company.get('sector', ''),
                                "exchange": "NSE",
                                "source": "screener"
                            })
            except Exception as e:
                logger.debug(f"Screener search failed: {e}")
        
        if not results:
            results.append({
                "symbol": q.upper(),
                "name": f"{q.upper()} (try exact NSE symbol)",
                "sector": "",
                "exchange": "NSE",
                "source": "suggestion"
            })
        
        return {"results": results[:20]}
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": [], "error": str(e)}


@app.get("/api/stocks/popular")
async def get_popular_stocks():
    """Return a list of popular NSE stocks."""
    popular = [
        {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "sector": "Oil & Gas"},
        {"symbol": "TCS", "name": "Tata Consultancy Services", "sector": "IT"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "sector": "Banking"},
        {"symbol": "INFY", "name": "Infosys Ltd", "sector": "IT"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "sector": "Banking"},
        {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "sector": "Automobile"},
        {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "sector": "Telecom"},
        {"symbol": "ITC", "name": "ITC Ltd", "sector": "FMCG"},
        {"symbol": "WIPRO", "name": "Wipro Ltd", "sector": "IT"},
        {"symbol": "TATASTEEL", "name": "Tata Steel Ltd", "sector": "Metals"},
        {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "sector": "FMCG"},
        {"symbol": "NTPC", "name": "NTPC Ltd", "sector": "Power"},
        {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "sector": "Automobile"},
        {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd", "sector": "Pharma"},
        {"symbol": "TATAPOWER", "name": "Tata Power Co Ltd", "sector": "Power"},
        {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd", "sector": "Conglomerate"},
        {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "sector": "Finance"},
        {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "sector": "Banking"},
        {"symbol": "LT", "name": "Larsen & Toubro Ltd", "sector": "Construction"},
    ]
    return {"results": popular}


@app.get("/api/stocks/data/{symbol}")
async def get_stock_data(symbol: str, exchange: str = "NSE"):
    """
    Fetch comprehensive stock data for analysis.
    Returns all data needed for WebLLM to analyze.
    """
    try:
        symbol = symbol.upper()
        exchange = exchange.upper()
        
        # Fetch all data using the existing prefetcher
        real_data = prefetch_all_data(symbol, exchange)
        
        # Build grounding context
        grounding_context = build_grounding_context(real_data)
        
        # Parse fundamental data
        fundamental_data = {}
        screener_raw = real_data.get('fundamental', {}).get('screener', {})
        parsed_screener = parse_screener_company_data(screener_raw)
        if parsed_screener:
            fundamental_data.update(parsed_screener)
        
        risk_data = real_data.get('risk', {})
        if risk_data:
            for key, val in risk_data.items():
                if val is not None and key not in fundamental_data:
                    fundamental_data[key] = val
        
        # Calculate risk score
        risk_score = None
        try:
            beta = risk_data.get('beta')
            pe = fundamental_data.get('pe_ratio', risk_data.get('pe_ratio'))
            debt_eq = fundamental_data.get('debt_to_equity')
            
            score = 5.0
            if beta is not None:
                beta_f = float(beta)
                if beta_f < 0.5: score -= 1.5
                elif beta_f < 0.8: score -= 1.0
                elif beta_f < 1.0: score -= 0.5
                elif beta_f > 1.5: score += 1.5
                elif beta_f > 1.2: score += 1.0
                elif beta_f > 1.0: score += 0.5
            
            if pe is not None:
                pe_f = float(pe)
                if pe_f > 50: score += 2.0
                elif pe_f > 30: score += 1.0
                elif pe_f > 20: score += 0.5
                elif pe_f < 10: score -= 1.0
            
            if debt_eq is not None:
                de_f = float(debt_eq)
                if de_f > 2.0: score += 2.0
                elif de_f > 1.0: score += 1.0
                elif de_f > 0.5: score += 0.5
                elif de_f < 0.2: score -= 0.5
            
            risk_score = max(1.0, min(10.0, round(score, 1)))
        except (ValueError, TypeError):
            pass
        
        return {
            "symbol": symbol,
            "exchange": exchange,
            "company_name": risk_data.get('company_name', symbol),
            "sector": risk_data.get('sector', 'N/A'),
            "industry": risk_data.get('industry', 'N/A'),
            "current_price": real_data.get('technical', {}).get('current_price'),
            "technical": real_data.get('technical', {}),
            "fundamental": fundamental_data,
            "risk": {**risk_data, 'risk_score': risk_score} if risk_score else risk_data,
            "sentiment": real_data.get('sentiment', {}),
            "grounding_context": grounding_context,
            "fetched_at": datetime.now().isoformat(),
            "errors": real_data.get('errors', [])
        }
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/sectors")
async def get_sectors():
    """List all market sectors."""
    try:
        sectors = screener.list_sectors()
        return sectors
    except Exception as e:
        logger.error(f"Error fetching sectors: {e}")
        return {"error": str(e)}


@app.get("/api/stocks/sector/{sector_slug}")
async def get_sector_companies(sector_slug: str):
    """Get companies in a sector."""
    try:
        data = screener.get_sector(sector_slug, include_all_pages=True)
        return data
    except Exception as e:
        logger.error(f"Error fetching sector {sector_slug}: {e}")
        return {"error": str(e)}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "screener_api": screener.health_check(),
        "alpha_vantage": av_is_available()
    }


# ============================================================
# Main Entry Point
# ============================================================
def main():
    """Start the web server."""
    port = int(os.getenv("WEB_PORT", "8000"))
    host = os.getenv("WEB_HOST", "127.0.0.1")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     📊 Indian Stock Market Analysis - WebLLM Edition        ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://{host}:{port}                                      ║
║  Data Proxy API ready - WebLLM runs in browser              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "src.web_app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
