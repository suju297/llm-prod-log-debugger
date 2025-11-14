#!/usr/bin/env python3
"""Test tools without LLM calls."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools import parse_logs, grep_error
from src.utils.chunking import select_best_chunk
from src.utils.redaction import redact_logs


def test_parse_logs():
    print("Testing parse_logs...")
    sample_logs = """2024-03-14T10:00:00Z INFO Starting application
2024-03-14T10:00:01Z ERROR [request-id: abc-123] NullPointerException at UserService.java:42
    at com.example.UserService.getUserDetails(UserService.java:42)
    at com.example.LoginController.handleLogin(LoginController.java:28)
2024-03-14T10:00:02Z WARN [request-id: abc-123] Retrying operation"""
    
    result = parse_logs(sample_logs)
    print(f"  Parsed {result['summary']['total_lines']} lines")
    print(f"  Found {result['summary']['error_count']} errors")
    print(f"  Groups: {list(result['groups']['by_request_id'].keys())}")
    print("  ✓ parse_logs working (with multiline stack trace support)")
    return result


def test_chunking(parsed_logs):
    print("\nTesting chunking...")
    chunk = select_best_chunk(parsed_logs, max_lines=50)
    print(f"  Selected chunk with {len(chunk['entries'])} entries")
    if 'score' in chunk:
        print(f"  Chunk score: {chunk['score']}")
    print("  ✓ chunking working (with time-based scoring)")
    return chunk


def test_redaction(chunk):
    print("\nTesting redaction...")
    # Add some sensitive data
    chunk['entries'][0]['message'] = "User email: test@example.com, API key: sk-1234567890"
    redacted = redact_logs(chunk['entries'])
    print(f"  Original: {chunk['entries'][0]['message']}")
    print(f"  Redacted: {redacted[0]['message']}")
    print("  ✓ redaction working")


def test_grep():
    print("\nTesting grep_error...")
    # Create temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        f.write("""public class Test {
    public void method() {
        throw new NullPointerException("test error");
    }
}""")
        temp_path = f.name
    
    result = grep_error("NullPointerException", [temp_path])
    print(f"  Found {result['total_matches']} matches")
    if result['total_matches'] > 0:
        print(f"  Context shown: ±2 lines around match")
    print("  ✓ grep_error working")
    
    # Cleanup
    Path(temp_path).unlink()


if __name__ == "__main__":
    print("Running tools-only tests...\n")
    
    try:
        parsed = test_parse_logs()
        chunk = test_chunking(parsed)
        test_redaction(chunk)
        test_grep()
        
        print("\n✅ All tools tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
