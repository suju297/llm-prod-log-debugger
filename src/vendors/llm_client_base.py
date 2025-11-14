from typing import Any, Dict, List, Optional, Protocol


class LLMClient(Protocol):
    """Protocol for LLM clients."""
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate completion from messages.
        
        Returns:
            Dict with keys:
            - content: str
            - function_calls: List[Dict[str, Any]]
            - latency: float
            - raw_response: Any
        """
        ...
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage statistics.
        
        Returns:
            Dict with keys: input, output, total
        """
        ...
