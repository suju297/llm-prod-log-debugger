import json
from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.models import Hypothesis, ToolCall
from src.utils.validators import validate_hypothesis_json


class AnalyzerAgent(BaseAgent):
    """Analyzer agent that creates initial hypothesis from logs and code."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("Analyzer", "analyzer.md", config)
    
    def parse_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate Analyzer response."""
        data = json.loads(content)
        
        # Validate using schema validator
        validation_errors = validate_hypothesis_json(data)
        if validation_errors:
            raise ValueError(f"Invalid hypothesis format: {'; '.join(validation_errors)}")
        
        # Parse tool calls
        tool_calls = []
        for tc in data.get("tool_calls", []):
            tool_calls.append(ToolCall(
                name=tc["name"],
                args=tc["args"]
            ))
        
        # Create hypothesis object
        hypothesis = Hypothesis(
            root_cause=data["hypothesis"],
            evidence=data["evidence"],
            suspect_files=data["suspect_files"],
            fix_suggestion=data["fix_suggestion"],
            confidence=float(data["confidence"])
        )
        
        return {
            "hypothesis": hypothesis,
            "assumptions": data.get("assumptions", []),
            "questions_for_critic": data.get("questions_for_critic", []),
            "tool_calls": tool_calls,
            "raw_data": data
        }
