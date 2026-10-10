"""Dependency-free MCP stdio adapter for the bounded local hackathon demo.

Supports initialize, ping, tools/list+call, resources/list+read. No approval tool:
only the local browser can submit the review action. Use a private Secure MCP
Tunnel for ChatGPT; this is not a public multi-user service.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from .core import ProofStore

URI = "ui://spec2proof/workbench"
META = {"ui": {"resourceUri": URI}, "openai/ui": {"entrypoints": [{"type": "global"}, {"type": "thread"}]}}


def schema(properties=None, required=None):
    return {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}


ID = {"type": "string", "pattern": "^[a-f0-9]{32}$"}
TOOLS = [
    {"name": "open_spec2proof", "title": "Open Spec2Proof", "description": "Open the acceptance-test evidence workbench.", "inputSchema": schema(), "_meta": META},
    {"name": "create_proof", "title": "Create acceptance criteria", "description": "Compile a full-refund policy for unused items within 1–365 inclusive calendar days. Returns explicit assumptions for user review. No arbitrary code.",
     "inputSchema": schema({"requirement": {"type": "string", "minLength": 20, "maxLength": 2000}}, ["requirement"]), "_meta": {"ui": {"resourceUri": URI}}},
    {"name": "run_baseline", "title": "Run acceptance tests", "description": "Run real Python tests on the deliberately buggy fixture. First show the contract and obtain user confirmation.",
     "inputSchema": schema({"proof_id": ID, "confirmed": {"type": "boolean", "const": True}}, ["proof_id", "confirmed"])},
    {"name": "propose_patch", "title": "Diagnose and propose patch", "description": "Explain failures and propose a two-line template repair. Does not apply anything; review and approval happen in the local browser.",
     "inputSchema": schema({"proof_id": ID}, ["proof_id"])},
    {"name": "get_proof", "title": "Read proof evidence", "description": "Read tests, failure evidence, pending diff, and any reviewer-approved rerun.",
     "inputSchema": schema({"proof_id": ID}, ["proof_id"]), "_meta": {"ui": {"resourceUri": URI}}},
]
for tool in TOOLS:
    tool["annotations"] = {"readOnlyHint": tool["name"] in ("open_spec2proof", "get_proof"),
                           "destructiveHint": False, "openWorldHint": False}


class Adapter:
    def __init__(self, data_dir):
        self.store = ProofStore(data_dir)

    def call(self, name, args):
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if tool is None:
            raise ValueError("Unknown tool")
        definition = tool["inputSchema"]
        if not isinstance(args, dict) or set(args) - set(definition["properties"]) or set(definition["required"]) - set(args):
            raise ValueError("Invalid tool arguments")
        if name == "open_spec2proof":
            return {"message": "Ready. Create a refund-policy proof. Approvals are available only at the local app, http://127.0.0.1:8765."}
        if name == "create_proof":
            return self.store.create(args["requirement"])
        if name == "run_baseline":
            if args.get("confirmed") is not True:
                raise ValueError("User confirmation of the contract is required")
            return self.store.run(args["proof_id"])
        if name == "propose_patch":
            value = self.store.propose(args["proof_id"])
        else:
            value = self.store.get(args["proof_id"])
        value["review_url"] = f"http://127.0.0.1:8765/?proof={value['id']}&view=approval#patch-card"
        value["review_instructions"] = "Keep start.ps1 running on this computer, open review_url in your browser, review the diff, check the approval box, then select Approve patch & rerun tests. Refresh the plugin proof afterward."
        return value

    def dispatch(self, request):
        request_id = request.get("id")
        if request_id is None:
            return None
        method = request.get("method")
        params = request.get("params") or {}
        try:
            if method == "initialize":
                version = params.get("protocolVersion")
                result = {"protocolVersion": version if version in ("2024-11-05", "2025-03-26", "2025-06-18") else "2025-06-18",
                          "serverInfo": {"name": "spec2proof", "version": "0.1.0"},
                          "capabilities": {"tools": {}, "resources": {}},
                          "instructions": "Show the compiled contract before running tests. Never imply a patch was applied before reviewer approval in the local browser. Unsupported policies must be clarified."}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "resources/list":
                result = {"resources": [{"uri": URI, "name": "Spec2Proof workbench", "mimeType": "text/html;profile=mcp-app"}]}
            elif method == "resources/read":
                if params.get("uri") != URI:
                    raise ValueError("Unknown resource")
                html = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
                html = html.replace("__TOKEN__", "").replace("__MODE__", "mcp")
                result = {"contents": [{"uri": URI, "mimeType": "text/html;profile=mcp-app", "text": html,
                                        "_meta": {"ui": {"prefersBorder": True}}}]}
            elif method == "tools/call":
                try:
                    value = self.call(params.get("name"), params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value}
                except (ValueError, TypeError) as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, TypeError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.environ.get("SPEC2PROOF_DATA", ".spec2proof"))
    args = parser.parse_args()
    adapter = Adapter(args.data_dir)
    for line in sys.stdin:
        try:
            if len(line) > 16384:
                raise ValueError("Request too large")
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be an object")
            response = adapter.dispatch(request)
        except (ValueError, TypeError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON-RPC request"}}
        except Exception:
            response = {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32603, "message": "Execution failed"}}
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
