import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.vendors.llm_client_base import LLMClient
from src.utils import read_text


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str, prompt_file: str, config: Optional[Dict[str, Any]] = None, 
                 client: Optional[LLMClient] = None):
        self.name = name
        self.prompt = self._load_prompt(prompt_file)
        self.config = config
        self.logger = logger
        
        # Use provided client or create based on config
        if client:
            self.client = client
        else:
            self._create_client(config)
    
    def _create_client(self, config: Optional[Dict[str, Any]] = None):
        """Create LLM client based on config."""
        from src.utils import load_config
        
        cfg = config or load_config()
        backend = cfg.get("gemini", {}).get("backend", "sdk")
        
        if backend == "sdk":
            from src.vendors.genai_sdk_client import GeminiSDKClient
            self.client = GeminiSDKClient(cfg)
        else:
            from src.vendors.gemini_client_rest import GeminiRESTClient
            self.client = GeminiRESTClient(cfg)
    
    def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt from markdown file."""
        prompt_path = Path(__file__).parent / "prompts" / prompt_file
        return read_text(prompt_path)
    
    @abstractmethod
    def parse_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate agent response."""
        pass
    
    def call(self, messages: List[Dict[str, str]], 
             tools_schema: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Call the agent with messages and optional tools."""
        # Prepend system prompt
        full_messages = [
            {"role": "system", "content": self.prompt}
        ] + messages
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.generate(full_messages, tools_schema)
                
                # Parse the content
                raw_content = response["content"] or ""
                try:
                    parsed = self.parse_response(raw_content)
                except json.JSONDecodeError:
                    repaired = self.try_repair_json(raw_content)
                    parsed = self.parse_response(repaired)
                
                parsed["_raw_response"] = response
                parsed["_latency"] = response["latency"]
                
                return parsed
                
            except json.JSONDecodeError as e:
                logger.error(f"{self.name} returned invalid JSON: {e}")
                
                if attempt < max_retries - 1:
                    # Try to fix JSON
                    fixed_content = self._attempt_json_fix(response["content"])
                    if fixed_content:
                        try:
                            parsed = self.parse_response(fixed_content)
                            parsed["_raw_response"] = response
                            parsed["_json_fixed"] = True
                            return parsed
                        except:
                            pass
                    
                    # Request repair from model
                    repair_message = {
                        "role": "user",
                        "content": f"Your response contained invalid JSON. Error: {str(e)}\n\nPlease respond with valid JSON only, no markdown or explanations."
                    }
                    full_messages.append(repair_message)
                    logger.info(f"Requesting JSON repair from {self.name}")
                    continue
                
                raise
                
            except Exception as e:
                logger.error(f"{self.name} call failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying {self.name} call...")
                    continue
                raise
        
        raise Exception(f"{self.name} failed after {max_retries} attempts")
    
    def try_repair_json(self, text: str) -> str:
        """Try to extract JSON from text using regex."""
        # Look for JSON-like structure
        pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(0)
        
        # If no match, try the existing repair method
        fixed = self._attempt_json_fix(text)
        if fixed:
            return fixed
            
        # Last resort: return empty JSON
        return "{}"
    
    def _attempt_json_fix(self, content: str) -> Optional[str]:
        """Attempt to fix common JSON formatting issues."""
        # Remove markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        # Remove any text before first { or [
        json_start = -1
        for i, char in enumerate(content):
            if char in '{[':
                json_start = i
                break
        
        if json_start > 0:
            content = content[json_start:]
        
        # Remove any text after last } or ]
        json_end = -1
        for i in range(len(content) - 1, -1, -1):
            if content[i] in '}]':
                json_end = i + 1
                break
        
        if json_end > 0 and json_end < len(content):
            content = content[:json_end]
        
        # Try to parse
        try:
            json.loads(content.strip())
            return content.strip()
        except:
            return None
