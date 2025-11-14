from dataclasses import dataclass
from typing import List


@dataclass
class IncidentReport:
    title: str
    summary: str
    root_cause: str
    evidence: List[str]
    fix: str
    impact: str
    remaining_risks: List[str]
    raw_conversation_path: str
