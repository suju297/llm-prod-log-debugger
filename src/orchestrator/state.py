import json
from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


def _to_jsonable(content: Any) -> Any:
    """Convert content to JSON-serializable format."""
    if isinstance(content, dict):
        return content
    if is_dataclass(content):
        return asdict(content)
    if hasattr(content, "model_dump"):  # pydantic models
        return content.model_dump()
    if hasattr(content, "__dict__"):  # other objects
        return content.__dict__
    return content  # fallback to str conversion later


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationState:
    """Manages conversation history and context."""
    
    def __init__(self):
        self.messages: List[Message] = []
        self.context: Dict[str, Any] = {}
        self.tool_results: Dict[str, Any] = {}
    
    def add_system(self, content: str) -> None:
        """Add system message."""
        self.messages.append(Message(MessageRole.SYSTEM, content))
    
    def add_user(self, content: Any) -> None:
        """Add user message."""
        self.messages.append(Message(MessageRole.USER, _to_jsonable(content)))
    
    def add_agent(self, agent_name: str, content: Any) -> None:
        """Add agent response."""
        self.messages.append(Message(
            MessageRole.ASSISTANT,
            _to_jsonable(content),
            metadata={"agent": agent_name}
        ))
    
    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Add tool execution result."""
        jsonable_result = _to_jsonable(result)
        self.messages.append(Message(
            MessageRole.TOOL,
            jsonable_result,
            metadata={"tool": tool_name}
        ))
        self.tool_results[tool_name] = jsonable_result
    
    def get_messages_for_api(self, max_tool_result_chars: int = 1500) -> List[Dict[str, str]]:
        """Convert messages to format for API calls."""
        api_messages = []
        
        for msg in self.messages:
            if msg.role == MessageRole.TOOL:
                # Truncate tool results to prevent token explosion
                result_str = json.dumps(msg.content, default=str)
                if len(result_str) > max_tool_result_chars:
                    result_str = result_str[:max_tool_result_chars] + "... (truncated)"
                content = f"Tool '{msg.metadata['tool']}' returned: {result_str}"
                api_messages.append({"role": "user", "content": content})
            else:
                # Content is already JSON-safe from add_user/add_agent
                content = msg.content
                if isinstance(content, (dict, list)):
                    content = json.dumps(content, default=str)
                api_messages.append({
                    "role": msg.role.value,
                    "content": str(content)
                })
        
        return api_messages
    
    def to_json(self) -> Dict[str, Any]:
        """Export state to JSON."""
        return {
            "messages": [
                {
                    "role": msg.role.value,
                    "content": msg.content,  # Already JSON-safe
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in self.messages
            ],
            "context": self.context,
            "tool_results": self.tool_results
        }
