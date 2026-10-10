"""Loopback-only demo server; no third-party runtime dependencies."""
import argparse
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .core import DEFAULT_REQUIREMENT, ProofStore

WEB = Path(__file__).parent / "web"


def make_server(port=8765, data_dir=".spec2proof"):
    store = ProofStore(data_dir)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, value, content_type="application/json"):
            body = json.dumps(value).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def trusted_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.trusted_host():
                return self.reply(403, {"error": "Untrusted host"})
            path = urlparse(self.path).path
            try:
                if path == "/":
                    html = (WEB / "index.html").read_text(encoding="utf-8")
                    html = html.replace("__TOKEN__", token).replace("__MODE__", "local")
                    return self.reply(200, html.encode(), "text/html; charset=utf-8")
                if path == "/health":
                    return self.reply(200, {"status": "ok", "version": "0.1.0"})
                if self.headers.get("X-Spec2Proof-Token") != token:
                    return self.reply(403, {"error": "Open the local app to access evidence."})
                if path.startswith("/api/proofs/"):
                    parts = path.strip("/").split("/")
                    if len(parts) == 4 and parts[3] == "bundle":
                        return self.reply(200, store.bundle(parts[2]), "application/zip")
                    if len(parts) == 3:
                        return self.reply(200, store.get(parts[2]))
                return self.reply(404, {"error": "Not found"})
            except ValueError as exc:
                self.reply(400, {"error": str(exc)})

        def do_POST(self):
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.trusted_host() or self.headers.get("X-Spec2Proof-Token") != token or (origin and origin not in allowed):
                return self.reply(403, {"error": "Use the local app to perform this action."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Request size must be 1–8192 bytes")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                path = urlparse(self.path).path
                if path == "/api/proofs":
                    return self.reply(201, store.create(data.get("requirement", DEFAULT_REQUIREMENT)))
                parts = path.strip("/").split("/")
                if len(parts) != 4 or parts[:2] != ["api", "proofs"]:
                    return self.reply(404, {"error": "Not found"})
                proof_id, action = parts[2:]
                if action == "run":
                    if data.get("confirmed") is not True:
                        raise ValueError("Confirm the displayed contract before running tests.")
                    result = store.run(proof_id)
                elif action == "propose":
                    result = store.propose(proof_id)
                elif action == "approve":
                    result = store.approve(proof_id, data.get("proposal_sha256"), data.get("approved"))
                elif action == "reject":
                    result = store.reject(proof_id)
                else:
                    return self.reply(404, {"error": "Not found"})
                self.reply(200, result)
            except (ValueError, TypeError) as exc:
                self.reply(400, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "Execution failed. The proof remains available; inspect the local runner."})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.proof_store = store
    return server


def main():
    parser = argparse.ArgumentParser(description="Run Spec2Proof locally")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=os.environ.get("SPEC2PROOF_DATA", ".spec2proof"))
    args = parser.parse_args()
    server = make_server(args.port, args.data_dir)
    print(f"Spec2Proof ready at http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
