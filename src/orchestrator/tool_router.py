import logging
from typing import Dict, Any, List
from src.models import ToolCall
from src.tools import parse_logs, grep_error


logger = logging.getLogger(__name__)


class ToolRouter:
    """Routes tool calls to appropriate implementations."""
    
    def __init__(self):
        self.tools = {
            "parse_logs": parse_logs,
            "grep_error": grep_error,
        }
    
    def dispatch(self, call: ToolCall) -> Dict[str, Any]:
        """Dispatch tool call and return result."""
        logger.info(f"Dispatching tool call: {call.name}")
        
        if call.name not in self.tools:
            error_msg = f"Unknown tool: {call.name}"
            logger.error(error_msg)
            return {
                "error": True,
                "message": error_msg
            }
        
        try:
            tool_func = self.tools[call.name]
            result = tool_func(**call.args)
            logger.info(f"Tool {call.name} completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Tool {call.name} failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "error": True,
                "message": error_msg,
                "exception": str(e)
            }
    
    def get_schemas(self) -> List[Dict[str, Any]]:
        """Get tool schemas for function calling."""
        import json
        from pathlib import Path
        
        schema_path = Path(__file__).parent.parent / "config" / "tool_schemas.json"
        with open(schema_path, 'r') as f:
            return json.load(f)
