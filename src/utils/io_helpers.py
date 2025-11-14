import json
from pathlib import Path
from typing import Any, Dict, List, Union


def read_text(path: Union[str, Path]) -> str:
    """Read text file and return contents."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(path: Union[str, Path], content: str) -> None:
    """Write text to file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def write_json(path: Union[str, Path], data: Any, indent: int = 2) -> None:
    """Write JSON to file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, default=str)


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure directory exists."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
