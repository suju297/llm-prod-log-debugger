import json
from typing import Dict, Any
from src.agents.base import BaseAgent
from src.models import ToolCall
from src.utils.validators import validate_critic_json


class CriticAgent(BaseAgent):
    """Critic agent that validates hypothesis and creates final report."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("Critic", "critic.md", config)
    
    def parse_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate Critic response."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = {}  # Treat as empty if not valid JSON

        validation_errors = validate_critic_json(data)
        if validation_errors:
            error_message = f"Invalid critic response format: {'; '.join(validation_errors)}"
            self.logger.error(error_message)
            # Return a structured error that the pipeline can handle
            return {
                "verdict": "error",
                "final_report": "Could not generate a valid report due to response format errors.",
                "remaining_risks": [error_message],
                "tool_calls": [],
                "_error": True,
                "raw_data": {"error": error_message, "content": content},
            }

        # Parse optional tool calls
        tool_calls = []
        for tc in data.get("tool_calls", []):
            tool_calls.append(ToolCall(
                name=tc["name"],
                args=tc["args"]
            ))
        
        return {
            "verdict": data["verdict"],
            "issues_found": data.get("issues_found", []),
            "open_issues": data.get("open_issues", []),
            "assumptions_challenged": data.get("assumptions_challenged", []),
            "final_report": data["final_report"],
            "remaining_risks": data["remaining_risks"],
            "confidence_score": data.get("confidence_score", 0.0),
            "tool_calls": tool_calls,
            "raw_data": data
        }
