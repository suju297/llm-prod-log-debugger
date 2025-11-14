import re
from pathlib import Path
from typing import Dict, List, Any, Union


def grep_error(pattern: str, files: List[Union[str, Path]]) -> Dict[str, Any]:
    """Search for pattern in files using regex."""
    results = []
    total_matches = 0
    
    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        return {
            "error": True,
            "message": f"Invalid regex pattern: {e}",
            "results": []
        }
    
    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            results.append({
                "file": str(file_path),
                "error": f"File not found: {file_path}",
                "matches": []
            })
            continue
        
        try:
            content = path.read_text(encoding='utf-8')
            lines = content.split('\n')
            matches = []
            
            for line_no, line in enumerate(lines, 1):
                if compiled_pattern.search(line):
                    # Get context (±2 lines)
                    start = max(0, line_no - 3)
                    end = min(len(lines), line_no + 2)
                    context_lines = []
                    
                    for i in range(start, end):
                        prefix = ">>> " if i == line_no - 1 else "    "
                        context_lines.append(f"{i+1:4d}: {prefix}{lines[i]}")
                    
                    matches.append({
                        "line_number": line_no,
                        "line": line,
                        "context": "\n".join(context_lines)
                    })
                    total_matches += 1
            
            results.append({
                "file": str(file_path),
                "matches": matches,
                "match_count": len(matches)
            })
            
        except Exception as e:
            results.append({
                "file": str(file_path),
                "error": str(e),
                "matches": []
            })
    
    return {
        "error": False,
        "pattern": pattern,
        "total_matches": total_matches,
        "results": results
    }
