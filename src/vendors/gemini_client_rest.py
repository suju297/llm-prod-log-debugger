import json
import time
import logging
import os
from typing import Dict, List, Any, Optional
import requests
from src.utils import load_config


logger = logging.getLogger(__name__)


class GeminiRESTClient:
    """Legacy REST client for Gemini API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_config()
        self.api_key = self.config['gemini'].get('api_key') or os.getenv(self.config['gemini']['api_key_env'])
        if not self.api_key:
            raise ValueError(f"Gemini API key missing")
            
        self.model = self.config['gemini']['model']
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.temperature = self.config['gemini']['temperature']
        self.max_tokens = self.config['gemini']['max_tokens']
        self.retry_config = self.config['retry']
        self.token_usage = {"input": 0, "output": 0, "total": 0}
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion using REST API."""
        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature or self.temperature,
                "maxOutputTokens": max_tokens or self.max_tokens,
            }
        }
        
        # Add response schema if provided
        if response_schema:
            payload["generationConfig"]["responseSchema"] = response_schema
        
        # Add tools if provided
        if tools_schema:
            payload["tools"] = [{
                "functionDeclarations": tools_schema
            }]
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": self.api_key
        }
        
        # Retry logic
        for attempt in range(self.retry_config['attempts']):
            try:
                start_time = time.time()
                response = requests.post(self.api_url, json=payload, headers=headers, params=params)
                latency = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract response and function calls
                    candidate = data.get("candidates", [{}])[0]
                    content = candidate.get("content", {})
                    
                    # Update token usage
                    if "usageMetadata" in data:
                        usage = data["usageMetadata"]
                        self.token_usage["input"] += usage.get("promptTokenCount", 0)
                        self.token_usage["output"] += usage.get("candidatesTokenCount", 0)
                        self.token_usage["total"] += usage.get("totalTokenCount", 0)
                    
                    result = {
                        "content": "",
                        "function_calls": [],
                        "latency": latency,
                        "raw_response": data
                    }
                    
                    # Extract text and function calls
                    for part in content.get("parts", []):
                        if "text" in part:
                            result["content"] = part["text"]
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            result["function_calls"].append({
                                "name": fc["name"],
                                "args": fc.get("args", {})
                            })
                    
                    return result
                
                elif response.status_code == 429:  # Rate limit
                    if attempt < self.retry_config['attempts'] - 1:
                        backoff = self.retry_config['backoff_seconds'] * (2 ** attempt)
                        logger.warning(f"Rate limited, retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue
                
                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    if attempt < self.retry_config['attempts'] - 1:
                        time.sleep(self.retry_config['backoff_seconds'])
                        continue
                    raise Exception(error_msg)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < self.retry_config['attempts'] - 1:
                    time.sleep(self.retry_config['backoff_seconds'])
                    continue
                raise
        
        raise Exception(f"Failed after {self.retry_config['attempts']} attempts")
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get current token usage stats."""
        return self.token_usage.copy()
