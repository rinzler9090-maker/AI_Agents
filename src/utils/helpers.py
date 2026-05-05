"""
Helper utilities for the multi-agent system.
Provides LLM configuration, logging setup, and common utilities.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Disable Docker requirement for AG2 code execution
# AG2 defaults to Docker for code execution, but we don't need it for analysis
os.environ.setdefault("AUTOGEN_USE_DOCKER", "False")

logger = logging.getLogger(__name__)

# Type variable for the retry decorator
F = TypeVar('F', bound=Callable[..., Any])


def retry_on_api_error(
    max_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Callable[[F], F]:
    """
    Decorator that retries a function on transient API errors with exponential backoff.
    
    Handles:
      - openai.InternalServerError (5xx)
      - openai.RateLimitError (429)
      - openai.APITimeoutError
      - openai.APIConnectionError
      - Generic ConnectionError / TimeoutError
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay in seconds before first retry (default: 2.0).
        backoff_factor: Multiplier for delay after each retry (default: 2.0).
        retryable_status_codes: HTTP status codes that should trigger a retry.
    
    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: F) -> F:
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = base_delay
            
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a retryable error
                    should_retry = False
                    error_msg = str(e)
                    
                    # OpenAI-specific errors
                    if hasattr(e, 'status_code') and e.status_code in retryable_status_codes:
                        should_retry = True
                    elif hasattr(e, 'status_code') and hasattr(e, 'message'):
                        # openai APIStatusError
                        if e.status_code in retryable_status_codes:
                            should_retry = True
                    
                    # Check error message for common transient patterns
                    if any(pattern in error_msg for pattern in [
                        '504', '502', '503', '500', '429',
                        'timeout', 'Timeout', 'TIMEOUT',
                        'gateway', 'Gateway', 'GATEWAY',
                        'service unavailable', 'Service Unavailable',
                        'server error', 'Server Error',
                        'connection', 'Connection',
                        'rate limit', 'Rate Limit',
                    ]):
                        should_retry = True
                    
                    if not should_retry:
                        raise
                    
                    if attempt < max_retries:
                        jitter = 0.1 * time.time()  # Small random jitter
                        sleep_time = delay + (jitter % 0.5)
                        logger.warning(
                            f"API call failed (attempt {attempt}/{max_retries}): {error_msg[:120]}"
                            f"\n  Retrying in {sleep_time:.1f}s..."
                        )
                        time.sleep(sleep_time)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"API call failed after {max_retries} attempts: {error_msg[:200]}"
                        )
            
            # If we exhausted retries, raise the last exception
            raise last_exception
        
        return wrapper  # type: ignore
    
    return decorator


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )



def get_llm_config() -> Dict[str, Any]:
    """
    Build LLM configuration based on environment variables.

    Supports OpenAI, Anthropic Claude, and NVIDIA NIM (OpenAI-compatible).

    Returns:
        LLM configuration dictionary for AG2.

    Raises:
        ValueError: If no API key is configured.
    """
    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        config = {
            "config_list": [
                {
                    "model": os.getenv("OPENAI_MODEL", "gpt-4"),
                    "api_key": openai_key,
                    "api_type": "openai",
                    "temperature": 0.0  # Zero temperature = deterministic, reduces hallucinations
                }
            ]
        }
        logging.getLogger(__name__).info(
            f"Using OpenAI model: {os.getenv('OPENAI_MODEL', 'gpt-4')} (temperature=0)"
        )
        return config


    # Anthropic/Claude
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        config = {
            "config_list": [
                {
                    "model": os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
                    "api_key": anthropic_key,
                    "api_type": "anthropic"
                }
            ]
        }
        logging.getLogger(__name__).info(
            f"Using Anthropic model: {os.getenv('ANTHROPIC_MODEL', 'claude-3-opus-20240229')}"
        )
        return config

    # NVIDIA NIM (OpenAI-compatible endpoint)
    nim_key = os.getenv("NIM_API_KEY")
    if nim_key:
        config = {
            "config_list": [
                {
                    "model": os.getenv("NIM_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
                    "api_key": nim_key,
                    "api_type": "openai",
                    "base_url": os.getenv("NIM_BASE", "https://integrate.api.nvidia.com/v1")
                }
            ]
        }
        logging.getLogger(__name__).info(
            f"Using NVIDIA NIM model: {os.getenv('NIM_MODEL', 'nvidia/nemotron-3-super-120b-a12b')}"
        )
        return config

    # No API key found - provide helpful error
    error_msg = (
        "No API key found. Please set one of the following environment variables in your .env file:\n"
        "  - OPENAI_API_KEY (for OpenAI models)\n"
        "  - ANTHROPIC_API_KEY (for Anthropic Claude models)\n"
        "  - NIM_API_KEY (for NVIDIA NIM models)\n\n"
        "See .env.example for reference."
    )
    raise ValueError(error_msg)


def validate_stock_symbol(symbol: str) -> str:
    """
    Validate and normalize a stock symbol.

    Args:
        symbol: Stock symbol to validate.

    Returns:
        Uppercase, stripped symbol.

    Raises:
        ValueError: If symbol is empty or invalid.
    """
    if not symbol or not symbol.strip():
        raise ValueError("Stock symbol cannot be empty")
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum():
        raise ValueError(f"Invalid stock symbol: '{symbol}'. Symbols should be alphanumeric (e.g., RELIANCE, TCS).")
    return cleaned
