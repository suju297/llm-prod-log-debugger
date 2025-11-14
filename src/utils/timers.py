import time
from contextlib import contextmanager
from typing import Dict


class Timer:
    def __init__(self):
        self.timings: Dict[str, float] = {}
    
    @contextmanager
    def time(self, name: str):
        start = time.time()
        yield
        self.timings[name] = time.time() - start
    
    def get_summary(self) -> Dict[str, float]:
        return self.timings.copy()
