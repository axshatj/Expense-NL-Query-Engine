import time
import logging
import re
import openai
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

def get_llm_client(api_key: str = None) -> openai.OpenAI:
    key_to_use = api_key or OPENAI_API_KEY
    return openai.OpenAI(api_key=key_to_use, base_url=OPENAI_BASE_URL or None)

def call_llm_with_retry(client: openai.OpenAI, **kwargs):
    """
    Calls the LLM chat completions API and automatically retries with backoff on rate limits (429).
    """
    max_retries = 6
    base_delay = 5.0
    
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            msg = str(e)
            logger.warning(f"Rate limit hit (RateLimitError): {msg}. Attempt {attempt + 1}/{max_retries}")
            
            # Extract retry delay from error message if possible
            retry_match = re.search(r"retry in (\d+\.?\d*)s", msg, re.IGNORECASE)
            if retry_match:
                sleep_time = float(retry_match.group(1)) + 1.5
            else:
                sleep_time = base_delay * (2.2 ** attempt)
            
            logger.info(f"Sleeping for {sleep_time:.2f} seconds before retrying...")
            time.sleep(sleep_time)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "resource_exhausted" in msg.lower():
                logger.warning(f"Rate limit hit (Exception): {msg}. Attempt {attempt + 1}/{max_retries}")
                retry_match = re.search(r"retry in (\d+\.?\d*)s", msg, re.IGNORECASE)
                if retry_match:
                    sleep_time = float(retry_match.group(1)) + 1.5
                else:
                    sleep_time = base_delay * (2.2 ** attempt)
                logger.info(f"Sleeping for {sleep_time:.2f} seconds before retrying...")
                time.sleep(sleep_time)
            else:
                # Other exceptions (like authentication errors or validation errors) should be raised immediately
                raise e
                
    # Final try that raises the exception to the caller if retries are exhausted
    return client.chat.completions.create(**kwargs)
