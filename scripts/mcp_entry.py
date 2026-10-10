"""Start the checkout's MCP adapter from any working directory.

Used by local clients and Secure MCP Tunnel, without an editable install or
assuming that `python` on PATH points to the intended interpreter.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spec2proof.mcp_server import main

if __name__ == "__main__":
    if "--data-dir" not in sys.argv:
        sys.argv.extend(["--data-dir", str(ROOT / ".spec2proof")])
    main()
