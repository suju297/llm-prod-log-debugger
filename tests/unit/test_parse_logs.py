import pytest
from src.tools import parse_logs


class TestParseLogs:
    def test_parse_simple_logs(self):
        raw_logs = """2024-03-14T10:00:00Z INFO Starting server
2024-03-14T10:00:01Z ERROR Failed to connect to database
2024-03-14T10:00:02Z WARN Retrying connection"""
        
        result = parse_logs(raw_logs)
        
        assert len(result["entries"]) == 3
        assert result["summary"]["error_count"] == 1
        assert result["summary"]["warn_count"] == 1
    
    def test_parse_with_request_ids(self):
        raw_logs = """2024-03-14T10:00:00Z INFO [request-id: abc-123] Processing request
2024-03-14T10:00:01Z ERROR [request-id: abc-123] Request failed"""
        
        result = parse_logs(raw_logs)
        
        assert len(result["entries"]) == 2
        assert result["entries"][0]["request_id"] == "abc-123"
        assert "abc-123" in result["groups"]["by_request_id"]
    
    def test_parse_empty_logs(self):
        result = parse_logs("")
        assert len(result["entries"]) == 0
        assert result["summary"]["total_lines"] == 0
