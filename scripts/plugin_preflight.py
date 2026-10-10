"""Check local plugin readiness, without printing or transmitting credentials."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
LOCAL.mkdir(exist_ok=True)
data_dir = str((ROOT / ".spec2proof").resolve())
entry = str(ROOT / "scripts" / "mcp_entry.py")
argv = [sys.executable, entry, "--data-dir", data_dir]
config = {"mcpServers": {"spec2proof": {"command": sys.executable, "args": argv[1:]}}}
(LOCAL / "mcp.local.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
checks = {}
requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "spec2proof-preflight", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "ui://spec2proof/workbench"}},
]
with tempfile.TemporaryDirectory(dir=LOCAL, prefix="launch-check-") as temporary:
    probe = subprocess.run(argv, cwd=temporary, input="\n".join(json.dumps(row) for row in requests) + "\n",
                           capture_output=True, text=True, timeout=15)
    if probe.returncode == 0:
        try:
            rows = [json.loads(line) for line in probe.stdout.splitlines()]
            checks["launch_from_other_directory"] = rows[0]["result"]["serverInfo"]["name"] == "spec2proof"
            tools = rows[1]["result"]["tools"]
            checks["tool_count"] = len(tools)
            checks["sidebar_and_thread_entrypoints"] = tools[0]["_meta"]["openai/ui"]["entrypoints"] == [{"type": "global"}, {"type": "thread"}]
            checks["mcp_app_resource"] = rows[2]["result"]["contents"][0]["mimeType"] == "text/html;profile=mcp-app"
        except (KeyError, IndexError, json.JSONDecodeError):
            checks["launch_from_other_directory"] = False
    else:
        checks["launch_from_other_directory"] = False
checks["tunnel_client_on_path"] = bool(shutil.which("tunnel-client"))
checks["openai_api_key_in_process"] = bool(os.environ.get("OPENAI_API_KEY"))
checks["control_plane_key_in_process"] = bool(os.environ.get("CONTROL_PLANE_API_KEY"))
report = {"local_checks": checks, "local_config": str(LOCAL / "mcp.local.json"),
          "mcp_command_for_tunnel": subprocess.list2cmdline(argv),
          "shared_data_directory": data_dir,
          "not_verified": ["Platform tunnel permissions", "tunnel association with personal ChatGPT workspace", "live tunnel transport", "ChatGPT plugin installation and panel rendering"]}
(LOCAL / "plugin-preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if checks.get("launch_from_other_directory") and checks.get("mcp_app_resource") else 1)
