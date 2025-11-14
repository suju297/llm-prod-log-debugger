import os
import time
import logging
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types as genai_types
from src.utils import load_config


logger = logging.getLogger(__name__)


class GeminiSDKClient:
    """Gemini client using the official google-genai SDK (v1.50+)."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_config()
        
        # Resolve API key (config overrides ENV)
        self.api_key = self.config["gemini"].get("api_key") or os.getenv(self.config["gemini"]["api_key_env"])
        if not self.api_key:
            raise ValueError(f"Gemini API key missing - set {self.config['gemini']['api_key_env']}")
        
        self.model = self.config["gemini"]["model"]
        self.temperature = self.config["gemini"]["temperature"]
        self.max_tokens = self.config["gemini"]["max_tokens"]
        
        # New SDK client entry point
        self.client = genai.Client(api_key=self.api_key)
        self.token_usage = {"input": 0, "output": 0, "total": 0}
    
    def _to_contents(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert chat-style messages into Gemini content payloads."""
        contents: List[Dict[str, Any]] = []
        system_content = ""
        
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_content += msg["content"] + "\n\n"
                continue
            
            text = msg["content"]
            if system_content and role == "user":
                text = system_content + text
                system_content = ""
            
            api_role = "user" if role in ("user", "system") else "model"
            contents.append({
                "role": api_role,
                "parts": [genai_types.Part.from_text(text=text)]
            })
        
        if system_content:
            contents.insert(0, {
                "role": "user",
                "parts": [genai_types.Part.from_text(text=system_content.strip())]
            })
        
        return contents
    
    def _to_tools(self, tools_schema: Optional[List[Dict[str, Any]]]) -> Optional[List[genai_types.Tool]]:
        """Translate JSON tool schema into SDK Tool declarations."""
        if not tools_schema:
            return None
        
        declarations = []
        for schema in tools_schema:
            declarations.append(genai_types.FunctionDeclaration(
                name=schema["name"],
                description=schema.get("description", ""),
                parameters=schema.get("parameters", {})
            ))
        
        return [genai_types.Tool(function_declarations=declarations)]
    
    def _update_usage(self, usage: Optional[genai_types.UsageMetadata]) -> None:
        """Aggregate token usage information from the response."""
        if not usage:
            return

        usage_data = usage.model_dump(mode="python")
        prompt_tokens = (
            (usage_data.get("prompt_token_count") or 0) +
            (usage_data.get("tool_use_prompt_token_count") or 0)
        )
        response_tokens = (
            usage_data.get("response_token_count") or
            usage_data.get("candidates_token_count") or
            0
        )
        total_tokens = usage_data.get("total_token_count") or (prompt_tokens + response_tokens)
        
        self.token_usage["input"] += prompt_tokens
        self.token_usage["output"] += response_tokens
        self.token_usage["total"] += total_tokens
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion using the Gemini SDK."""
        start_time = time.time()
        
        config = genai_types.GenerateContentConfig(
            temperature=temperature or self.temperature,
            max_output_tokens=max_tokens or self.max_tokens,
            response_mime_type="application/json"
        )
        if response_schema:
            config.response_schema = response_schema
        
        contents = self._to_contents(messages)
        tools = self._to_tools(tools_schema)
        
        try:
            logger.info(f"Gemini Request: model={self.model}, tools_provided={tools is not None}")
            if tools:
                config.tools = tools
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
            latency = time.time() - start_time
            
            text_content = response.text or ""
            function_calls = []
            for fc in response.function_calls or []:
                function_calls.append({
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {}
                })
            
            self._update_usage(getattr(response, "usage_metadata", None))
            
            return {
                "content": text_content,
                "function_calls": function_calls,
                "latency": latency,
                "raw_response": response.to_json_dict()
            }
        
        except Exception as exc:
            logger.error(f"SDK generation failed: {exc}")
            raise
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get current token usage."""
        return dict(self.token_usage)
