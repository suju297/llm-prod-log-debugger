from datetime import datetime
from typing import List, Dict, Any, Tuple
from dateutil import parser as date_parser
from src.models import LogEntry


def score_log_groups(groups: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[str, float]]:
    """Score log groups by relevance for analysis."""
    scored_groups = []
    current_time = datetime.now()
    
    for group_id, entries in groups.items():
        # Calculate score based on error density and recency
        error_count = sum(1 for e in entries if e.get("level") == "ERROR")
        warn_count = sum(1 for e in entries if e.get("level") in ["WARN", "WARNING"])
        
        # Basic scoring: errors weighted more than warnings
        score = (error_count * 3) + warn_count
        
        # Age penalty - reduce score for older entries
        if entries and "timestamp" in entries[-1]:
            try:
                # Parse the most recent timestamp in the group
                last_ts = date_parser.parse(entries[-1]["timestamp"])
                age_hours = (current_time - last_ts).total_seconds() / 3600
                
                # Apply age penalty: -1 point per hour old, max penalty of -10
                age_penalty = min(age_hours, 10)
                score = max(0, score - age_penalty)
            except Exception as e:
                # If timestamp parsing fails, don't apply penalty
                pass
        
        scored_groups.append((group_id, score))
    
    # Sort by score descending
    return sorted(scored_groups, key=lambda x: x[1], reverse=True)


def select_best_chunk(parsed_logs: Dict[str, Any], max_lines: int = 120) -> Dict[str, Any]:
    """Select the most relevant log chunk for analysis."""
    groups = parsed_logs.get("groups", {})
    
    # Score groups by request ID
    if groups.get("by_request_id"):
        scored = score_log_groups(groups["by_request_id"])
        if scored:
            best_group_id = scored[0][0]
            best_entries = groups["by_request_id"][best_group_id]
            
            # Truncate if needed
            if len(best_entries) > max_lines:
                best_entries = best_entries[:max_lines]
            
            return {
                "entries": best_entries,
                "group_id": best_group_id,
                "total_groups": len(groups["by_request_id"]),
                "score": scored[0][1]
            }
    
    # Fallback to error clusters
    error_clusters = groups.get("error_clusters", [])
    if error_clusters:
        # Get most recent error cluster
        best_cluster = None
        best_time = None
        
        for cluster in error_clusters:
            if cluster["entries"]:
                try:
                    # Get timestamp of error entry
                    error_idx = cluster.get("error_index", 0)
                    if error_idx < len(cluster["entries"]):
                        ts_str = cluster["entries"][error_idx].get("timestamp")
                        if ts_str:
                            ts = date_parser.parse(ts_str)
                            if best_time is None or ts > best_time:
                                best_time = ts
                                best_cluster = cluster
                except:
                    pass
        
        if best_cluster:
            entries = best_cluster["entries"][:max_lines]
            return {
                "entries": entries,
                "cluster_index": error_clusters.index(best_cluster),
                "total_clusters": len(error_clusters)
            }
    
    # Fallback to all entries (most recent first)
    all_entries = parsed_logs.get("entries", [])
    
    # Sort by timestamp if available
    try:
        sorted_entries = sorted(
            all_entries,
            key=lambda e: date_parser.parse(e.get("timestamp", "")) if e.get("timestamp") else datetime.min,
            reverse=True
        )
    except:
        sorted_entries = all_entries
    
    return {
        "entries": sorted_entries[:max_lines],
        "truncated": len(all_entries) > max_lines,
        "fallback": True
    }
