from dataclasses import dataclass
from typing import List


@dataclass
class Hypothesis:
    root_cause: str
    evidence: List[str]
    suspect_files: List[str]
    fix_suggestion: str
    confidence: float
