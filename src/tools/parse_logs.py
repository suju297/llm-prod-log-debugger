import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dateutil import parser as date_parser
from src.models import LogEntry


def parse_logs(raw_logs: str) -> Dict[str, Any]:
    """Parse raw logs into structured JSON format."""
    lines = raw_logs.strip().split('\n')
    entries = []
    
    # Common log patterns
    timestamp_patterns = [
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)',  # ISO8601
        r'(\w{3} \d{1,2}, \d{4} \d{1,2}:\d{2}:\d{2} [AP]M)',  # Common format
        r'(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})',  # Apache format
    ]
    
    level_pattern = r'\b(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL)\b'
    request_id_patterns = [
        r'(?:request[_-]?id|req[_-]?id|trace[_-]?id)[:\s]*([a-f0-9-]{32,36})',
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',  # UUID
        r'(?:request[_-]?id|req[_-]?id|trace[_-]?id)[^\w-]*([A-Za-z0-9_-]+)',  # fallback short IDs
    ]
    
    # Support for multiline stack traces
    current_entry = None
    
    for line in lines:
        if not line.strip():
            continue
        
        # Check if this is a continuation of a stack trace
        if current_entry and (line.startswith('    at ') or line.startswith('\t')):
            current_entry.msg += '\n' + line
            current_entry.raw_line += '\n' + line
            continue
            
        # Extract timestamp
        ts = None
        ts_match = None
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                ts_match = match
                try:
                    ts_str = match.group(1)
                    # Use dateutil parser for flexible parsing
                    ts = date_parser.parse(ts_str)
                except Exception as e:
                    # Fallback to current time if parsing fails
                    ts = datetime.now()
                break
        
        if not ts:
            ts = datetime.now()
        
        # Extract level
        level_match = re.search(level_pattern, line, re.IGNORECASE)
        level = level_match.group(1).upper() if level_match else "INFO"
        
        # Extract request ID
        req_id = None
        for pattern in request_id_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                req_id = match.group(1)
                break
        
        # Extract message (remove timestamp, level, etc)
        msg = line
        if ts_match:
            msg = msg.replace(ts_match.group(0), '')
        if level_match:
            msg = re.sub(level_pattern, '', msg, count=1, flags=re.IGNORECASE)
        msg = msg.strip()
        
        entry = LogEntry(
            ts=ts,
            level=level,
            req_id=req_id,
            msg=msg,
            raw_line=line
        )
        entries.append(entry)
        
        # Track current entry for multiline support
        if level in ["ERROR", "FATAL", "WARN", "WARNING"]:
            current_entry = entry
        else:
            current_entry = None
    
    # Group by request ID or error proximity
    groups = _group_entries(entries)
    
    return {
        "entries": [_entry_to_dict(e) for e in entries],
        "groups": groups,
        "summary": {
            "total_lines": len(entries),
            "error_count": sum(1 for e in entries if e.level == "ERROR"),
            "warn_count": sum(1 for e in entries if e.level in ["WARN", "WARNING"]),
        }
    }


def _entry_to_dict(entry: LogEntry) -> Dict[str, Any]:
    """Convert LogEntry to dict."""
    return {
        "timestamp": entry.ts.isoformat(),
        "level": entry.level,
        "request_id": entry.req_id,
        "message": entry.msg,
        "raw": entry.raw_line
    }


def _group_entries(entries: List[LogEntry]) -> Dict[str, Any]:
    """Group entries by request ID or error proximity."""
    groups = {}
    
    # Group by request ID
    for entry in entries:
        if entry.req_id:
            if entry.req_id not in groups:
                groups[entry.req_id] = []
            groups[entry.req_id].append(_entry_to_dict(entry))
    
    # Find error clusters (entries within ±5 lines of errors)
    error_indices = [i for i, e in enumerate(entries) if e.level == "ERROR"]
    error_clusters = []
    
    for idx in error_indices:
        cluster = []
        start = max(0, idx - 5)
        end = min(len(entries), idx + 6)
        for i in range(start, end):
            cluster.append(_entry_to_dict(entries[i]))
        error_clusters.append({
            "error_index": idx,
            "entries": cluster
        })
    
    return {
        "by_request_id": groups,
        "error_clusters": error_clusters
    }
