import io
import json
import tempfile
import subprocess
import sys
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from spec2proof.core import DEFAULT_REQUIREMENT, ProofStore, compile_requirement, digest, execute
from spec2proof.mcp_server import Adapter, URI


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ProofStore(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self):
        p = self.store.create(DEFAULT_REQUIREMENT)
        self.store.run(p["id"])
        return self.store.propose(p["id"])

    def test_end_to_end_real_python_and_frozen_tests(self):
        p = self.proposal()
        self.assertEqual(p["before"]["passed"], 8)
        self.assertEqual({r["id"] for r in p["before"]["results"] if r["status"] == "failed"}, {"AC2", "AC4"})
        self.assertIsNone(p["after"])
        self.assertIsNone(p["approval"])
        result = self.store.approve(p["id"], p["proposal"]["sha256"], True)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["after"]["passed"], 10)
        self.assertEqual(result["before"]["tests_sha256"], result["after"]["tests_sha256"])
        self.assertNotEqual(result["before"]["source_sha256"], result["after"]["source_sha256"])

    def test_alternate_window(self):
        p = self.store.create(DEFAULT_REQUIREMENT.replace("30", "14"))
        self.assertEqual(p["contract"]["days"], 14)
        p = self.store.run(p["id"])
        self.assertEqual(p["before"]["passed"], 8)

    def test_missing_approval_does_not_apply(self):
        p = self.proposal()
        for value in (False, None, "true", 1):
            with self.assertRaises(ValueError):
                self.store.approve(p["id"], p["proposal"]["sha256"], value)
        self.assertIsNone(self.store.get(p["id"])["after"])

    def test_stale_hash_rejected(self):
        p = self.proposal()
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.store.approve(p["id"], "outdated", True)

    def test_tampering_between_baseline_and_proposal_rejected(self):
        p = self.store.create(DEFAULT_REQUIREMENT)
        p = self.store.run(p["id"])
        p["tests"] += "# changed after baseline"
        self.store.save(p)
        with self.assertRaisesRegex(ValueError, "Baseline inputs changed"):
            self.store.propose(p["id"])

    def test_tampered_tests_rejected(self):
        p = self.proposal()
        p["tests"] += "# changed"
        self.store.save(p)
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.store.approve(p["id"], p["proposal"]["sha256"], True)

    def test_tampered_patch_rejected(self):
        p = self.proposal()
        p["proposal"]["source"] += "# changed"
        self.store.save(p)
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.store.approve(p["id"], p["proposal"]["sha256"], True)

    def test_rejection_preserves_original(self):
        p = self.proposal()
        result = self.store.reject(p["id"])
        self.assertEqual(result["original_source"], p["original_source"])
        self.assertEqual(result["state"], "rejected")
        self.assertIsNone(result["after"])
        with self.assertRaises(ValueError):
            self.store.approve(p["id"], p["proposal"]["sha256"], True)

    def test_invalid_transition(self):
        p = self.store.create(DEFAULT_REQUIREMENT)
        with self.assertRaises(ValueError):
            self.store.propose(p["id"])
        self.store.run(p["id"])
        with self.assertRaises(ValueError):
            self.store.run(p["id"])

    def test_duplicate_approval(self):
        p = self.proposal()
        self.store.approve(p["id"], p["proposal"]["sha256"], True)
        with self.assertRaises(ValueError):
            self.store.approve(p["id"], p["proposal"]["sha256"], True)

    def test_concurrent_approval_only_applies_once(self):
        p = self.proposal()
        def approve(_):
            try:
                return ProofStore(self.temp.name).approve(p["id"], p["proposal"]["sha256"], True)["state"]
            except ValueError:
                return "blocked"
        with ThreadPoolExecutor(2) as pool:
            self.assertCountEqual(list(pool.map(approve, [0, 1])), ["verified", "blocked"])

    def test_evidence_bundle_hashes_and_reproducibility(self):
        p = self.proposal()
        self.store.approve(p["id"], p["proposal"]["sha256"], True)
        with zipfile.ZipFile(io.BytesIO(self.store.bundle(p["id"]))) as archive:
            hashes = json.loads(archive.read("SHA256SUMS.json"))
            for name, sha in hashes.items():
                self.assertEqual(digest(archive.read(name).decode()), sha)
            rerun = execute(archive.read("patched/subject.py").decode(), archive.read("patched/test_acceptance.py").decode())
            self.assertEqual(rerun["passed"], 10)

    def test_pending_bundle_has_no_applied_code(self):
        p = self.proposal()
        with zipfile.ZipFile(io.BytesIO(self.store.bundle(p["id"]))) as archive:
            self.assertNotIn("patched/subject.py", archive.namelist())

    def test_audit_chain(self):
        p = self.proposal()
        previous = "0" * 64
        for entry in p["audit"]:
            self.assertEqual(entry["previous"], previous)
            self.assertEqual(entry["hash"], digest({k: v for k, v in entry.items() if k != "hash"}))
            previous = entry["hash"]

    def test_path_traversal(self):
        with self.assertRaises(ValueError):
            self.store.get("../../secrets")

    def test_invalid_requirements(self):
        for text in ("", "Build a bank", DEFAULT_REQUIREMENT.replace("30", "400"),
                     DEFAULT_REQUIREMENT + " VIP exceptions apply.",
                     DEFAULT_REQUIREMENT + " A fee applies.",
                     DEFAULT_REQUIREMENT.replace("30 days", "14 days"),
                     DEFAULT_REQUIREMENT.replace("30", "-1"),
                     DEFAULT_REQUIREMENT.replace("30", "14.5"),
                     DEFAULT_REQUIREMENT + " Also 14 days."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                compile_requirement(text)

    def test_mcp_protocol_and_extension_metadata(self):
        adapter = Adapter(self.temp.name)
        def call(method, params=None):
            return adapter.dispatch({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})["result"]
        self.assertEqual(call("initialize", {"protocolVersion": "2025-06-18"})["serverInfo"]["name"], "spec2proof")
        tools = call("tools/list")["tools"]
        self.assertNotIn("approve_patch", [t["name"] for t in tools])
        self.assertEqual(tools[0]["_meta"]["openai/ui"]["entrypoints"], [{"type": "global"}, {"type": "thread"}])
        resource = call("resources/read", {"uri": URI})["contents"][0]
        self.assertEqual(resource["mimeType"], "text/html;profile=mcp-app")
        self.assertNotIn("__MODE__", resource["text"])
        p = call("tools/call", {"name": "create_proof", "arguments": {"requirement": DEFAULT_REQUIREMENT}})["structuredContent"]
        result = call("tools/call", {"name": "run_baseline", "arguments": {"proof_id": p["id"], "confirmed": True}})
        self.assertEqual(result["structuredContent"]["before"]["passed"], 8)
        result = call("tools/call", {"name": "approve_patch", "arguments": {}})
        self.assertTrue(result["isError"])

    def test_mcp_rejects_extra_code_arguments(self):
        adapter = Adapter(self.temp.name)
        with self.assertRaises(ValueError):
            adapter.call("create_proof", {"requirement": DEFAULT_REQUIREMENT, "code": "print('not run')"})

    def test_actual_stdio_transport(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "create_proof", "arguments": {"requirement": DEFAULT_REQUIREMENT}}},
        ]
        process = subprocess.run([sys.executable, "-m", "spec2proof.mcp_server", "--data-dir", self.temp.name],
                                 input="\n".join(json.dumps(row) for row in requests) + "\n", text=True,
                                 capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([row["id"] for row in responses], [1, 2, 3])
        self.assertEqual(responses[-1]["result"]["structuredContent"]["state"], "draft")


if __name__ == "__main__":
    unittest.main()
