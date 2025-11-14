from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    ts: datetime
    level: str
    req_id: Optional[str]
    msg: str
    raw_line: str
