import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Callable, NamedTuple, Optional
from src.agents import AnalyzerAgent, CriticAgent
from src.models import IncidentReport, ToolCall
from src.orchestrator.state import ConversationState
from src.orchestrator.tool_router import ToolRouter
from src.utils import read_text, write_text, write_json, ensure_dir, Timer, load_config
from src.utils.chunking import select_best_chunk
from src.utils.redaction import redact_logs
from src.utils.validators import validate_incident_report


logger = logging.getLogger(__name__)


class Event(NamedTuple):
    """Event emitted during pipeline execution."""
    kind: str
    payload: Dict[str, Any]


def run_pipeline(
    log_path: str,
    code_paths: List[str],
    on_event: Callable[[Event], None] = lambda e: None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[IncidentReport, Dict]:
    """Main orchestration pipeline with event streaming."""
    timer = Timer()
    config = config or load_config()
    
    # Get max tool result chars from config
    max_tool_chars = config.get('limits', {}).get('max_tool_result_chars', 1500)
    
    # Initialize components
    tool_router = ToolRouter()
    analyzer = AnalyzerAgent(config)
    critic = CriticAgent(config)
    state = ConversationState()
    
    try:
        # Step 1: Read and parse logs
        with timer.time("read_logs"):
            raw_logs = read_text(log_path)
            logger.info(f"Read {len(raw_logs)} chars from {log_path}")
        
        with timer.time("parse_logs"):
            parsed_logs = tool_router.dispatch(
                ToolCall(name="parse_logs", args={"raw_logs": raw_logs})
            )
            state.add_tool_result("parse_logs", parsed_logs)
            logger.info(f"Parsed {parsed_logs['summary']['total_lines']} log lines")
            
            # Don't emit full parse_logs result - too noisy
            on_event(Event("tool_result", {
                "tool": "parse_logs",
                "summary": parsed_logs['summary']
            }))
        
        # Step 2: Chunk and redact logs
        with timer.time("chunk_and_redact"):
            # Select best chunk to avoid token limits
            max_lines = config['limits']['max_log_lines']
            chunked_logs = select_best_chunk(parsed_logs, max_lines)
            logger.info(f"Selected chunk with {len(chunked_logs['entries'])} entries")
            
            # Apply PII redaction
            redacted_entries = redact_logs(chunked_logs['entries'])
            chunked_logs['entries'] = redacted_entries
            logger.info("Applied PII redaction to log entries")
            
            # Emit event about chunk selection
            on_event(Event("log_chunk_selected", {
                "selected_count": len(chunked_logs['entries']),
                "source": chunked_logs.get('group_id') or chunked_logs.get('cluster_index', 'fallback'),
                "total_groups": chunked_logs.get('total_groups', 0)
            }))
        
        # Step 3: Read code files
        with timer.time("read_code"):
            code_contents = {}
            total_chars = 0
            max_chars = config['limits']['max_code_chars']
            
            for code_path in code_paths:
                try:
                    content = read_text(code_path)
                    # Limit code size
                    if total_chars + len(content) > max_chars:
                        remaining = max_chars - total_chars
                        if remaining > 0:
                            content = content[:remaining]
                            logger.warning(f"Truncated {code_path} to fit size limit")
                        else:
                            logger.warning(f"Skipping {code_path} - size limit reached")
                            continue
                    
                    code_contents[code_path] = content
                    total_chars += len(content)
                except Exception as e:
                    logger.warning(f"Failed to read {code_path}: {e}")
            
            state.context["code_files"] = code_contents
            logger.info(f"Read {len(code_contents)} code files, {total_chars} chars total")
        
        # Create log summary for prompt (not full logs)
        log_summary = {
            "total_lines": parsed_logs['summary']['total_lines'],
            "error_count": parsed_logs['summary']['error_count'],
            "warn_count": parsed_logs['summary']['warn_count'],
            "selected_chunk_size": len(chunked_logs['entries']),
            "recent_errors": [
                {"timestamp": e["timestamp"], "message": e["message"][:200]}
                for e in chunked_logs['entries']
                if e["level"] == "ERROR"
            ][:5]  # Only top 5 errors
        }
        
        # Only include full logs if debug mode
        if config.get('debug', {}).get('include_full_logs', False):
            log_summary["full_logs"] = chunked_logs
        
        # Get multi-round config
        min_rounds = config.get('pipeline', {}).get('min_rounds', 2)
        max_rounds = config.get('pipeline', {}).get('max_rounds', 3)
        
        # Step 4: Multi-round analysis
        with timer.time("multi_round_analysis"):
            state.add_user({
                "log_summary": log_summary,
                "code_snippets": code_contents
            })
            
            for round_num in range(1, max_rounds + 1):
                # Analyzer turn
                with timer.time(f"analyzer_round_{round_num}"):
                    analyzer_response = analyzer.call(
                        state.get_messages_for_api(max_tool_chars),
                        tool_router.get_schemas()
                    )
                    
                    # Store raw data to avoid serialization issues
                    state.add_agent(f"analyzer_round_{round_num}", analyzer_response["raw_data"])
                    
                    on_event(Event("agent_message", {
                        "agent": f"Analyzer (Round {round_num})",
                        "message": analyzer_response["raw_data"],
                        "round": round_num
                    }))
                    
                    hypothesis = analyzer_response["hypothesis"]
                    logger.info(f"Round {round_num} - Analyzer hypothesis: {hypothesis.root_cause}")
                    logger.info(f"Round {round_num} - Confidence: {hypothesis.confidence}")
                
                # Execute Analyzer's requested tools
                with timer.time(f"tool_execution_round_{round_num}"):
                    for tool_call in analyzer_response.get("tool_calls", []):
                        logger.info(f"Executing tool: {tool_call.name}")
                        result = tool_router.dispatch(tool_call)
                        state.add_tool_result(tool_call.name, result)
                        
                        # Emit tool result (summarized)
                        on_event(Event("tool_result", {
                            "tool": tool_call.name,
                            "args": tool_call.args,
                            "success": not result.get("error", False),
                            "summary": {
                                "total_matches": result.get("total_matches", 0),
                                "files_searched": len(result.get("results", []))
                            } if tool_call.name == "grep_error" else None
                        }))
                
                # Critic turn
                with timer.time(f"critic_round_{round_num}"):
                    critic_response = critic.call(
                        state.get_messages_for_api(max_tool_chars),
                        tool_router.get_schemas()
                    )
                    
                    state.add_agent(f"critic_round_{round_num}", critic_response["raw_data"])
                    
                    on_event(Event("agent_message", {
                        "agent": f"Critic (Round {round_num})",
                        "message": critic_response["raw_data"],
                        "round": round_num
                    }))
                    
                    logger.info(f"Round {round_num} - Critic verdict: {critic_response['verdict']}")
                    
                    # Execute Critic's requested tools
                    critic_tools = critic_response.get("tool_calls", [])
                    if critic_tools:
                        logger.info(f"Critic requested {len(critic_tools)} tool calls")
                        for tool_call in critic_tools:
                            result = tool_router.dispatch(tool_call)
                            state.add_tool_result(tool_call.name, result)
                            
                            on_event(Event("tool_result", {
                                "tool": tool_call.name,
                                "args": tool_call.args,
                                "success": not result.get("error", False)
                            }))
                    
                    # Check if we can confirm
                    open_issues = critic_response.get("open_issues", [])
                    if (critic_response["verdict"] == "confirmed" and 
                        not open_issues and 
                        round_num >= min_rounds):
                        logger.info(f"Analysis confirmed after {round_num} rounds")
                        break
                    
                    # Prepare for next round if needed
                    if round_num < max_rounds:
                        # Add feedback for next round
                        state.add_user({
                            "critic_feedback": {
                                "issues_found": critic_response.get("issues_found", []),
                                "open_issues": open_issues,
                                "suggestions": "Please address the issues found and provide updated analysis."
                            }
                        })
        
        # Step 5: Generate final report
        with timer.time("generate_report"):
            output_dir = ensure_dir(config['output']['dir'])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save conversation history
            conv_path = output_dir / f"conversation_{timestamp}.json"
            write_json(conv_path, state.to_json())
            
            # Create incident report
            report = IncidentReport(
                title=f"Incident Analysis - {timestamp}",
                summary=hypothesis.root_cause,
                root_cause=hypothesis.root_cause,
                evidence=hypothesis.evidence,
                fix=hypothesis.fix_suggestion,
                impact="See report for details",
                remaining_risks=critic_response["remaining_risks"],
                raw_conversation_path=str(conv_path)
            )
            
            # Validate report before saving
            validation_errors = validate_incident_report(report)
            if validation_errors:
                logger.warning(f"Report validation issues: {validation_errors}")
            
            # Save markdown report
            md_path = output_dir / f"report_{timestamp}.md"
            write_text(md_path, critic_response["final_report"])
            
            # Aggregate token usage from both agents
            analyzer_tokens = analyzer.client.get_token_usage()
            critic_tokens = critic.client.get_token_usage()
            total_tokens = {
                "input": analyzer_tokens["input"] + critic_tokens["input"],
                "output": analyzer_tokens["output"] + critic_tokens["output"],
                "total": analyzer_tokens["total"] + critic_tokens["total"]
            }
            
            # Calculate cost using pricing from config
            pricing = config['gemini']['pricing']
            cost_per_1k_input = pricing['input_per_1k_tokens']
            cost_per_1k_output = pricing['output_per_1k_tokens']
            estimated_cost = (
                (total_tokens["input"] / 1000) * cost_per_1k_input +
                (total_tokens["output"] / 1000) * cost_per_1k_output
            )
            
            # Save metrics
            metrics = {
                "timings": timer.get_summary(),
                "token_usage": {
                    "analyzer": analyzer_tokens,
                    "critic": critic_tokens,
                    "total": total_tokens
                },
                "estimated_cost": {
                    "amount": round(estimated_cost, 4),
                    "currency": pricing['currency'],
                    "note": pricing['note']
                },
                "confidence_scores": {
                    "analyzer": hypothesis.confidence,
                    "critic": critic_response.get("confidence_score", 0.0)
                },
                "conversation_rounds": round_num,
                "chunking_info": {
                    "original_lines": parsed_logs['summary']['total_lines'],
                    "chunked_lines": len(chunked_logs['entries']),
                    "method": chunked_logs.get('group_id', chunked_logs.get('cluster_index', 'fallback'))
                }
            }
            
            # Add warning if confidence still low
            critical_threshold = config.get('thresholds', {}).get('critical_confidence', 0.5)
            if hypothesis.confidence < critical_threshold:
                metrics["warning"] = f"Low confidence score: {hypothesis.confidence}"
                logger.warning(f"Final confidence still low: {hypothesis.confidence}")
            
            metrics_path = output_dir / f"metrics_{timestamp}.json"
            write_json(metrics_path, metrics)
            
            logger.info(f"Report saved to {md_path}")
            logger.info(f"Metrics saved to {metrics_path}")
            logger.info(f"Total tokens used: {total_tokens['total']}")
            logger.info(f"Estimated cost: ${estimated_cost:.4f}")
            
            # Emit final event
            on_event(Event("pipeline_complete", {
                "report_path": str(md_path),
                "metrics_path": str(metrics_path),
                "conversation_path": str(conv_path),
                "total_rounds": round_num,
                "total_tokens": total_tokens["total"],
                "estimated_cost": estimated_cost
            }))
        
        return report, metrics
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


def run_tools_only(
    log_path: str,
    code_paths: List[str],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Run only the tools without LLM calls (for testing/debugging)."""
    timer = Timer()
    config = config or load_config()
    tool_router = ToolRouter()
    results = {}
    
    try:
        # Parse logs
        with timer.time("parse_logs"):
            raw_logs = read_text(log_path)
            parsed_logs = tool_router.dispatch(
                ToolCall(name="parse_logs", args={"raw_logs": raw_logs})
            )
            results["parsed_logs"] = parsed_logs
        
        # Chunk and redact
        with timer.time("chunk_and_redact"):
            max_lines = config['limits']['max_log_lines']
            chunked_logs = select_best_chunk(parsed_logs, max_lines)
            redacted_entries = redact_logs(chunked_logs['entries'])
            results["chunked_logs"] = {
                "original_count": len(parsed_logs['entries']),
                "chunked_count": len(chunked_logs['entries']),
                "redacted": True
            }
        
        # Test grep on code files
        with timer.time("grep_test"):
            if code_paths:
                grep_results = tool_router.dispatch(
                    ToolCall(name="grep_error", args={
                        "pattern": "error|exception|null",
                        "files": code_paths
                    })
                )
                results["grep_test"] = {
                    "total_matches": grep_results.get("total_matches", 0),
                    "files_searched": len(code_paths)
                }
        
        results["timings"] = timer.get_summary()
        return results
        
    except Exception as e:
        logger.error(f"Tools-only run failed: {e}", exc_info=True)
        raise


# Alias for backwards compatibility
run_pipeline_sync = run_pipeline
