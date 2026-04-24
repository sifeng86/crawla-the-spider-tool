"""
LLM handler with response caching to reduce token costs.
Supports Google Gemini via LangChain.
"""
import hashlib
import os
import re
import json
from typing import Optional, Dict, Any
from threading import Lock
from bs4 import BeautifulSoup


# In-memory LLM response cache
_llm_cache: Dict[str, str] = {}
_cache_lock = Lock()


def clean_webpage_content(content: str) -> str:
    """
    Cleans webpage content by removing HTML tags, scripts, and unnecessary characters.
    
    Args:
        content: Raw HTML content
        
    Returns:
        Cleaned text content
    """
    # Parse HTML content
    soup = BeautifulSoup(content, "html.parser")
    
    # Remove script, style, and other non-content elements
    for element in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        element.decompose()
    
    # Extract text and normalize whitespace
    text = soup.get_text(separator=" ")
    text = re.sub(r'[^\w\s.,!?;:\-\'\"()]', '', text)  # Keep basic punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    
    # Truncate if too long (to limit token usage)
    max_chars = 10000
    if len(text) > max_chars:
        text = text[:max_chars] + "... [truncated]"
    
    return text


def load_config() -> Dict[str, Any]:
    """
    Loads configuration from the config.json file.
    Returns empty dict if file is missing (LLM will rely on env var fallback).
    """
    config_path = os.path.join(os.path.dirname(__file__), "../setting/config.json")
    try:
        with open(config_path, "r") as config_file:
            return json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_cache_key(prompt: str, content: str) -> str:
    """
    Generate a cache key from prompt and content.
    
    Args:
        prompt: User prompt
        content: Webpage content (first 500 chars used for key)
        
    Returns:
        MD5 hash as cache key
    """
    # Use first 500 chars of content to make key more specific but not too long
    content_preview = (content or "")[:500]
    key_string = f"{prompt}:{content_preview}"
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cached_response(cache_key: str) -> Optional[str]:
    """
    Get cached LLM response if available.
    
    Args:
        cache_key: Cache key to look up
        
    Returns:
        Cached response or None
    """
    with _cache_lock:
        return _llm_cache.get(cache_key)


def cache_response(cache_key: str, response: str):
    """
    Cache an LLM response.
    
    Args:
        cache_key: Cache key
        response: Response to cache
    """
    with _cache_lock:
        # Limit cache size to prevent memory issues
        if len(_llm_cache) > 100:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(_llm_cache.keys())[:20]
            for key in oldest_keys:
                _llm_cache.pop(key, None)
        _llm_cache[cache_key] = response


def clear_cache():
    """Clear the LLM response cache."""
    with _cache_lock:
        _llm_cache.clear()


def get_gemini_response(prompt: str, webpage_content: Optional[str] = None) -> str:
    """
    Get response from Gemini LLM with caching support.
    
    Args:
        prompt: User prompt/question
        webpage_content: Optional webpage content to analyze
        
    Returns:
        LLM response text
    """
    try:
        # Check cache first
        cache_key = get_cache_key(prompt, webpage_content or "")
        cached = get_cached_response(cache_key)
        if cached:
            print("[LLM Cache] Hit - returning cached response")
            return cached
        
        print("[LLM Cache] Miss - calling Gemini API")
        
        # Load configuration
        config = load_config()
        llm_config = config.get("llm", {}).get("gemini", {})

        # API key: config.json takes precedence, fallback to env var
        api_key = llm_config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not configured. Set GOOGLE_API_KEY in .env or llm.gemini.api_key in config.json")

        # Import here to avoid loading if not needed
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Initialize the Gemini model
        llm = ChatGoogleGenerativeAI(
            model=llm_config.get("model", "gemini-2.0-flash"),
            google_api_key=api_key,
            temperature=llm_config.get("temperature", 0.7),
            max_output_tokens=llm_config.get("max_output_tokens", 2048),
        )
        
        # Clean and prepare content
        if webpage_content:
            webpage_content = clean_webpage_content(webpage_content)
        
        # Build the complete prompt
        if webpage_content:
            complete_prompt = f"""Analyze the following webpage content and answer the question.

Webpage Content:
{webpage_content}

Question: {prompt}

Provide a concise and accurate response based on the webpage content."""
        else:
            complete_prompt = prompt
        
        # Get response from model
        response = llm.invoke(complete_prompt)
        result = response.content
        
        # Cache the response
        cache_response(cache_key, result)
        
        return result
        
    except Exception as e:
        error_msg = f"LLM Error: {str(e)}"
        print(error_msg)
        return error_msg


def get_gemini_response_with_retry(
    prompt: str,
    webpage_content: Optional[str] = None,
    max_retries: int = 2
) -> str:
    """
    Get Gemini response with retry logic.
    
    Args:
        prompt: User prompt
        webpage_content: Optional webpage content
        max_retries: Maximum retry attempts
        
    Returns:
        LLM response text
    """
    import time
    
    for attempt in range(max_retries + 1):
        try:
            return get_gemini_response(prompt, webpage_content)
        except Exception as e:
            if attempt < max_retries:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"[LLM] Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise

def get_gemini_self_healing(step_name: str, failed_param: str, html_snippet: str) -> Optional[str]:
    """Use LLM to fix broken CSS selectors."""
    prompt = f"The web scraping step '{step_name}' failed using the parameter '{failed_param}'. Based on this HTML snippet, provide a working CSS selector to extract the likely intended data. ONLY return the new selector string, without markdown or explanation.\n\nHTML:\n{html_snippet}"
    try:
        res = get_gemini_response(prompt)
        return res.strip().strip('`').strip()
    except:
        return None

def get_gemini_smart_extraction(schema: str, webpage_content: str) -> str:
    """Use LLM to extract data based on JSON Schema."""
    prompt = f"Extract information from the webpage and return ONLY a valid JSON object adhering strictly to this JSON schema:\n{schema}\nDo not include markdown blocks or other text."
    return get_gemini_response(prompt, webpage_content)