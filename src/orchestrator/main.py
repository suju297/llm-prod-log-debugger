import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler
from rich.live import Live
from rich.markdown import Markdown
from src.orchestrator.engine import run_pipeline, run_tools_only, Event
from src.models import IncidentReport
from src.utils import load_config, write_json, ensure_dir


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# CLI setup
app = typer.Typer(help="Multi-LLM Production Log Debugger")
console = Console()


def _load_configuration(config_path: Optional[Path], show_env_hint: bool = True) -> Dict[str, Any]:
    """Load configuration file and surface friendly errors."""
    try:
        return load_config(str(config_path)) if config_path else load_config()
    except Exception as exc:
        console.print(f"[red]Error loading config: {exc}[/red]")
        if show_env_hint:
            console.print("[yellow]Make sure you have created a .env file with your GEMINI_API_KEY[/yellow]")
        raise typer.Exit(1)


def _validate_inputs(log_file: Path, code_files: List[Path]) -> None:
    """Ensure log and code files exist before running analysis."""
    if not log_file.exists():
        console.print(f"[red]Error: Log file not found: {log_file}[/red]")
        raise typer.Exit(1)

    missing_files = [f for f in code_files if not f.exists()]
    if missing_files:
        console.print(f"[red]Error: Code files not found: {missing_files}[/red]")
        raise typer.Exit(1)


def _render_tools_results(results: Dict[str, Any], output_dir: Path) -> None:
    """Pretty-print tool-only run output and persist results."""
    console.print("\n[bold green]✓ Tools run complete![/bold green]\n")
    table = Table(title="Tools Test Results")
    table.add_column("Tool", style="cyan")
    table.add_column("Result", style="green")

    parsed = results.get("parsed_logs")
    if parsed:
        summary = parsed["summary"]
        table.add_row("Parse Logs", f"{summary['total_lines']} lines parsed")
        table.add_row("├─ Errors", str(summary["error_count"]))
        table.add_row("└─ Warnings", str(summary["warn_count"]))

    chunk = results.get("chunked_logs")
    if chunk:
        table.add_row("Chunking", f"{chunk['original_count']} → {chunk['chunked_count']} lines")
        table.add_row("└─ Redacted", "Yes" if chunk.get("redacted") else "No")

    grep = results.get("grep_test")
    if grep:
        table.add_row("Grep Test", f"{grep['total_matches']} matches in {grep['files_searched']} files")

    for step, duration in results.get("timings", {}).items():
        table.add_row(f"Time: {step}", f"{duration:.2f}s")

    console.print(table)

    results_path = output_dir / "tools_test_results.json"
    write_json(results_path, results)
    console.print(f"\n[bold]📁 Results saved to:[/bold] {results_path}")


def _render_analysis_summary(report: IncidentReport, metrics: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    """Show a concise summary once the multi-agent run completes."""
    console.print("\n[bold green]✓ Analysis Complete![/bold green]\n")
    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="cyan", justify="right", no_wrap=True)
    summary.add_column(style="white")
    summary.add_row("Root Cause", report.root_cause)
    summary.add_row("Fix", report.fix)
    summary.add_row("Remaining Risks", f"{len(report.remaining_risks)} identified")
    console.print(Panel(summary, title="📋 Summary", border_style="green"))

    run_details = Table.grid(padding=(0, 1))
    run_details.add_column(style="cyan", justify="right", no_wrap=True)
    run_details.add_column(style="green")
    tokens = metrics["token_usage"]["total"]
    analyzer_tokens = metrics["token_usage"]["analyzer"]["total"]
    critic_tokens = metrics["token_usage"]["critic"]["total"]
    cost_info = metrics["estimated_cost"]
    run_details.add_row("Model", cfg["gemini"]["model"])
    run_details.add_row("Conversation Rounds", str(metrics.get("conversation_rounds", 1)))
    run_details.add_row("Tokens Used", f"{tokens['total']} (Analyzer {analyzer_tokens} / Critic {critic_tokens})")
    run_details.add_row(
        "Estimated Cost",
        f"${cost_info['amount']:.4f} ({cost_info['note']})"
    )
    chunk_info = metrics.get("chunking_info")
    if chunk_info:
        run_details.add_row(
            "Log Reduction",
            f"{chunk_info['original_lines']} → {chunk_info['chunked_lines']} lines"
        )
    console.print(Panel(run_details, title="📊 Run Details", border_style="cyan"))

    timings = Table(title="Stage Timings")
    timings.add_column("Stage", style="cyan")
    timings.add_column("Duration", style="green")
    for step, duration in metrics.get("timings", {}).items():
        timings.add_row(step.replace("_", " ").title(), f"{duration:.2f}s")

    console.print("\n", timings)
    console.print(f"\n[bold]📁 Full report saved to:[/bold] {report.raw_conversation_path}")


def _run_tools_mode(log_file: Path, code_files: List[Path], cfg: Dict[str, Any]) -> None:
    """Execute deterministic tools without spinning up the agents."""
    console.print(Panel.fit(
        "[bold yellow]Running in tools-only mode (no LLM calls)[/bold yellow]\n"
        f"Log file: {log_file}\n"
        f"Code files: {', '.join(str(f) for f in code_files)}",
        title="🔧 Tools Test"
    ))

    try:
        with console.status("[bold green]Running tools..."):
            results = run_tools_only(
                str(log_file),
                [str(f) for f in code_files],
                config=cfg
            )
    except Exception as exc:
        console.print(f"\n[red]Error during tools test: {exc}[/red]")
        logger.error("Tools test failed", exc_info=True)
        raise typer.Exit(1)

    output_dir = ensure_dir(cfg["output"]["dir"])
    _render_tools_results(results, output_dir)


def setup_logging(verbose: bool = False, live: bool = False):
    """Configure logging based on verbosity."""
    # Set console log level
    if live:
        # In live mode, suppress most logs to console
        level = logging.WARNING
    else:
        level = logging.DEBUG if verbose else logging.INFO
    
    # Update console handler
    for handler in logging.getLogger().handlers:
        if isinstance(handler, RichHandler):
            handler.setLevel(level)
    
    # Ensure output directory exists
    Path("out").mkdir(exist_ok=True)
    
    # Also log to file (always at INFO level)
    file_handler = logging.FileHandler("out/run.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    file_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(file_handler)


def _run_analysis_pipeline(log_file: Path, code_files: List[Path], cfg: Dict[str, Any], live: bool = False):
    """Helper function to run analysis pipeline with or without live display."""
    if live:
        console.print(Panel.fit(
            f"[bold blue]Live Analysis Mode[/bold blue]\n"
            f"Log file: {log_file}\n"
            f"Code files: {', '.join(str(f) for f in code_files)}\n"
            f"Model: {cfg['gemini']['model']}",
            title="🔍 Multi-Agent Log Debugger"
        ))

        def handle_event(event: Event):
            if event.kind == "agent_message":
                agent = event.payload["agent"]
                msg_data = event.payload["message"]

                if "hypothesis" in msg_data:
                    content = f"**{agent}**\n\n"
                    content += f"**Hypothesis:** {msg_data['hypothesis']}\n\n"
                    content += f"**Confidence:** {msg_data['confidence']}\n\n"
                    if msg_data.get("assumptions"):
                        content += "**Assumptions:**\n"
                        for assumption in msg_data["assumptions"]:
                            content += f"- {assumption}\n"
                    if msg_data.get("questions_for_critic"):
                        content += "\n**Questions for Critic:**\n"
                        for q in msg_data["questions_for_critic"]:
                            content += f"- {q}\n"
                elif "verdict" in msg_data:
                    content = f"**{agent}**\n\n"
                    content += f"**Verdict:** {msg_data['verdict']}\n\n"
                    if msg_data.get("issues_found"):
                        content += "**Issues Found:**\n"
                        for issue in msg_data["issues_found"]:
                            content += f"- {issue}\n"
                    if msg_data.get("open_issues"):
                        content += "\n**Open Issues:**\n"
                        for issue in msg_data["open_issues"]:
                            content += f"- {issue}\n"
                    if msg_data.get("final_report"):
                        content += f"\n{msg_data['final_report']}"
                else:
                    content = f"**{agent}**\n\n{msg_data}"

                try:
                    live_display.update(Markdown(content))
                except Exception:
                    live_display.update(Panel(content, title=agent))

            elif event.kind == "tool_result" and event.payload["tool"] != "parse_logs":
                tool = event.payload["tool"]
                success = event.payload.get("success", True)
                status = "✓" if success else "✗"

                if tool == "grep_error" and event.payload.get("summary"):
                    summary = event.payload["summary"]
                    content = (
                        f"[dim]Tool: {tool} {status} - "
                        f"{summary['total_matches']} matches in {summary['files_searched']} files[/dim]"
                    )
                else:
                    content = f"[dim]Tool: {tool} {status}[/dim]"

                try:
                    live_display.update(content)
                except Exception:
                    pass

            elif event.kind == "log_chunk_selected":
                content = (
                    f"[dim]Selected {event.payload['selected_count']} log entries "
                    f"from {event.payload['source']}[/dim]"
                )
                try:
                    live_display.update(content)
                except Exception:
                    pass

        try:
            with Live(console=console, refresh_per_second=4) as live_display:
                report, metrics = run_pipeline(
                    str(log_file),
                    [str(f) for f in code_files],
                    on_event=handle_event,
                    config=cfg
                )

                summary = "\n[bold green]✓ Analysis Complete![/bold green]\n\n"
                summary += f"**Model:** {cfg['gemini']['model']}\n"
                summary += f"**Total Rounds:** {metrics.get('conversation_rounds', 1)}\n"
                summary += f"**Total Tokens:** {metrics['token_usage']['total']['total']}\n"
                summary += (
                    f"**Estimated Cost:** ${metrics['estimated_cost']['amount']:.4f} "
                    f"({metrics['estimated_cost']['note']})\n\n"
                )
                summary += f"📁 Report saved to: {report.raw_conversation_path}"

                live_display.update(Markdown(summary))

                return report, metrics
        except Exception as exc:
            console.print(f"\n[red]Error during analysis: {exc}[/red]")
            logger.error("Analysis failed", exc_info=True)
            raise typer.Exit(1)
    else:
        console.print(Panel.fit(
            f"[bold blue]Analyzing Incident[/bold blue]\n"
            f"Log file: {log_file}\n"
            f"Code files: {', '.join(str(f) for f in code_files)}\n"
            f"Model: {cfg['gemini']['model']}",
            title="🔍 Multi-Agent Log Debugger"
        ))

        try:
            with console.status("[bold green]Running analysis..."):
                report, metrics = run_pipeline(
                    str(log_file),
                    [str(f) for f in code_files],
                    config=cfg
                )
            return report, metrics
        except Exception as exc:
            console.print(f"\n[red]Error during analysis: {exc}[/red]")
            logger.error("Analysis failed", exc_info=True)
            raise typer.Exit(1)


@app.command()
def analyze(
    log_file: Path = typer.Argument(..., help="Path to log file"),
    code_files: List[Path] = typer.Argument(..., help="Paths to code files"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
    live: bool = typer.Option(False, "--live", help="Show live agent conversation"),
    config: Optional[Path] = typer.Option(None, "-c", "--config", help="Custom config file"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Run tools only, skip LLM calls (for testing)")
):
    """Analyze production logs and generate an incident report."""
    setup_logging(verbose, live)
    _validate_inputs(log_file, code_files)

    cfg = _load_configuration(config, show_env_hint=not no_llm)

    if no_llm:
        _run_tools_mode(log_file, code_files, cfg)
        return

    report, metrics = _run_analysis_pipeline(log_file, code_files, cfg, live=live)
    _render_analysis_summary(report, metrics, cfg)


@app.command()
def demo():
    """Run demo with sample data."""
    console.print("[bold]Running demo analysis...[/bold]")
    
    # Use sample files
    sample_dir = Path("samples")
    log_file = sample_dir / "logs_npe.txt"
    code_files = [
        sample_dir / "code" / "UserService.java",
        sample_dir / "code" / "AuthMiddleware.js"
    ]
    
    # Check if samples exist
    if not log_file.exists():
        console.print("[yellow]Creating sample files...[/yellow]")
        create_sample_files()
    
    setup_logging(verbose=False, live=True)
    _validate_inputs(log_file, code_files)
    cfg = _load_configuration(None)

    report, metrics = _run_analysis_pipeline(log_file, code_files, cfg, live=True)
    _render_analysis_summary(report, metrics, cfg)


def create_sample_files():
    """Create sample log and code files for demo."""
    from src.utils import write_text, ensure_dir
    
    samples_dir = ensure_dir("samples")
    code_dir = ensure_dir(samples_dir / "code")
    
    # Sample NPE logs
    npe_logs = """2024-03-14T14:30:00.123Z INFO [request-id: a1b2c3d4] Server started on port 8080
2024-03-14T14:30:15.456Z INFO [request-id: a1b2c3d4] Processing user login request
2024-03-14T14:30:15.789Z DEBUG [request-id: a1b2c3d4] Fetching user profile for ID: 12345
2024-03-14T14:30:16.012Z ERROR [request-id: a1b2c3d4] NullPointerException in UserService
java.lang.NullPointerException: Cannot invoke "com.example.Profile.getName()" because "user.profile" is null
    at com.example.UserService.getUserDetails(UserService.java:42)
    at com.example.LoginController.handleLogin(LoginController.java:28)
2024-03-14T14:30:16.234Z WARN [request-id: a1b2c3d4] Login failed for user 12345
2024-03-14T14:30:16.567Z ERROR [request-id: a1b2c3d4] Request failed with status 500
2024-03-14T14:31:00.890Z INFO [request-id: e5f6g7h8] Processing user login request
2024-03-14T14:31:01.123Z ERROR [request-id: e5f6g7h8] NullPointerException in UserService
java.lang.NullPointerException: Cannot invoke "com.example.Profile.getName()" because "user.profile" is null
    at com.example.UserService.getUserDetails(UserService.java:42)"""
    
    # Sample UserService.java
    user_service = """package com.example;

public class UserService {
    private final UserRepository userRepository;
    private final ProfileService profileService;
    
    public UserService(UserRepository userRepository, ProfileService profileService) {
        this.userRepository = userRepository;
        this.profileService = profileService;
    }
    
    public UserDetails getUserDetails(Long userId) {
        User user = userRepository.findById(userId);
        
        if (user == null) {
            throw new UserNotFoundException("User not found: " + userId);
        }
        
        // Fetch profile - may return null for new users
        user.profile = profileService.getProfile(userId);
        
        UserDetails details = new UserDetails();
        details.setId(user.getId());
        details.setEmail(user.getEmail());
        details.setName(user.profile.getName()); // Line 42 - NPE here!
        details.setCreatedAt(user.getCreatedAt());
        
        return details;
    }
}"""
    
    # Sample AuthMiddleware.js
    auth_middleware = """const jwt = require('jsonwebtoken');
const config = require('./config');

class AuthMiddleware {
    constructor(userService) {
        this.userService = userService;
    }
    
    async validateToken(req, res, next) {
        const token = req.headers.authorization?.split(' ')[1];
        
        if (!token) {
            return res.status(401).json({ error: 'No token provided' });
        }
        
        try {
            const decoded = jwt.verify(token, config.JWT_SECRET);
            const user = await this.userService.getUserDetails(decoded.userId);
            
            if (!user) {
                return res.status(401).json({ error: 'Invalid token' });
            }
            
            req.user = user;
            next();
        } catch (error) {
            console.error('Auth validation failed:', error);
            return res.status(401).json({ error: 'Invalid token' });
        }
    }
}

module.exports = AuthMiddleware;"""
    
    # Write sample files
    write_text(samples_dir / "logs_npe.txt", npe_logs)
    write_text(code_dir / "UserService.java", user_service)
    write_text(code_dir / "AuthMiddleware.js", auth_middleware)
    
    console.print("[green]Sample files created successfully![/green]")


if __name__ == "__main__":
    app()
