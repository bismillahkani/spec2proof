"""Deterministic, bounded refund-policy compiler and real Python test runner.

Only application-owned Python templates are executed. Neither requirements nor
MCP arguments can supply Python, paths, shell commands, or patches.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class ProcessLock:
    """Serialize state transitions across the browser and stdio processes."""
    def __init__(self, path):
        self.path = path
        self.thread_lock = threading.RLock()
        self.depth = 0

    def __enter__(self):
        self.thread_lock.acquire()
        if self.depth == 0:
            self.handle = open(self.path, "a+b")
            self.handle.seek(0, 2)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            try:
                if sys.platform == "win32":
                    import msvcrt
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() > deadline:
                                raise TimeoutError("Proof store is busy")
                            time.sleep(.05)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            except BaseException:
                self.handle.close()
                self.thread_lock.release()
                raise
        self.depth += 1
        return self

    def __exit__(self, *_):
        self.depth -= 1
        if self.depth == 0:
            if sys.platform == "win32":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
        self.thread_lock.release()

DEFAULT_REQUIREMENT = (
    "Refund unused items within 30 days, including day 30, for the full purchase "
    "amount. Used items and late returns receive no refund. Reject negative amounts or days."
)


def digest(value):
    data = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def compile_requirement(requirement):
    if not isinstance(requirement, str) or not 20 <= len(requirement) <= 2000:
        raise ValueError("Enter a refund policy between 20 and 2,000 characters.")
    text = requirement.lower()
    if re.search(r"-\s*\d+\s*days?\b|\d+\.\d+\s*days?\b", text):
        raise ValueError("Use a whole-number return window between 1 and 365 days.")
    windows = set(re.findall(r"\b(\d+)\s*days?\b", text) + re.findall(r"\bday\s+(\d+)\b", text))
    if len(windows) != 1:
        raise ValueError("Specify one consistent return window, e.g. within 30 days, including day 30.")
    days = int(windows.pop())
    if not 1 <= days <= 365:
        raise ValueError("The supported return window is 1–365 days.")
    if not all(word in text for word in ("refund", "unused", "full")):
        raise ValueError("This MVP supports full refunds for unused items. Use the example or edit its day window.")
    if re.search(r"\b(partial|fee|fees|percent|except|unless|vip|exclude|excluding|before|business|working)\b|%", text):
        raise ValueError("This policy needs rules beyond the MVP. Supported: full refunds, unused items, inclusive calendar-day window.")
    # Scope is shown for confirmation before any tests execute; never claim a
    # general natural-language model understood arbitrary business logic.
    return {"days": days, "inclusive": True, "unused_only": True,
            "negative_inputs": "ValueError", "amount_unit": "integer minor currency units",
            "assumptions": ["The deadline is inclusive; days are elapsed calendar days.",
                            "Amounts and days are integers; used is a boolean.",
                            "Negative inputs raise ValueError; zero amount is allowed.",
                            "No fees, partial refunds, exceptions, or external systems."]}


def source_for(days, fixed=False):
    operator = ">" if fixed else ">="
    used_return = "0" if fixed else "amount"
    return ("def refund(amount, days, used):\n"
            "    if amount < 0 or days < 0:\n"
            "        raise ValueError('negative input')\n"
            f"    if days {operator} {days}:\n"
            "        return 0\n"
            "    if used:\n"
            f"        return {used_return}\n"
            "    return amount\n")


def cases_for(days):
    return [
        {"id": "AC1", "title": "Unused item before deadline gets full refund", "args": [10000, days - 1, False], "expected": 10000},
        {"id": "AC2", "title": f"Day {days} is included", "args": [10000, days, False], "expected": 10000},
        {"id": "AC3", "title": "After deadline gets no refund", "args": [10000, days + 1, False], "expected": 0},
        {"id": "AC4", "title": "Used items get no refund", "args": [10000, 0, True], "expected": 0},
        {"id": "AC5", "title": "Zero purchase amount remains zero", "args": [0, 0, False], "expected": 0},
        {"id": "AC6", "title": "Negative amount is rejected", "args": [-1, 0, False], "raises": "ValueError"},
        {"id": "AC7", "title": "Negative elapsed days are rejected", "args": [10000, -1, False], "raises": "ValueError"},
        {"id": "AC8", "title": "Same-day unused item gets full refund", "args": [1, 0, False], "expected": 1},
        {"id": "AC9", "title": "Used item at deadline gets no refund", "args": [10000, days, True], "expected": 0},
        {"id": "AC10", "title": "Used and late item gets no refund", "args": [10000, days + 1, True], "expected": 0},
    ]


def test_source(cases):
    lines = ["import unittest", "from subject import refund", "", "class AcceptanceTests(unittest.TestCase):"]
    for case in cases:
        lines += [f"    def test_{case['id']}(self):", f"        # {case['title']}"]
        args = ", ".join(repr(a) for a in case["args"])
        if "raises" in case:
            lines += ["        with self.assertRaises(ValueError):", f"            refund({args})"]
        else:
            lines += [f"        self.assertEqual(refund({args}), {case['expected']!r})"]
    lines += ["", "if __name__ == '__main__':", "    unittest.main(verbosity=2)", ""]
    return "\n".join(lines)


RUNNER = '''import json, unittest
from test_acceptance import AcceptanceTests
class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rows = []
    def record(self, test, status, detail=''):
        self.rows.append({'id': test._testMethodName.removeprefix('test_'), 'status': status, 'detail': detail})
    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'passed')
    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'failed', self._exc_info_to_string(err, test))
    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'error', self._exc_info_to_string(err, test))
result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceTests))
print(json.dumps({'results': result.rows, 'passed': result.testsRun-len(result.failures)-len(result.errors), 'total': result.testsRun}))
raise SystemExit(0 if result.wasSuccessful() else 1)
'''


def execute(source, tests):
    with tempfile.TemporaryDirectory(prefix="spec2proof-") as directory:
        root = Path(directory)
        (root / "subject.py").write_text(source, encoding="utf-8")
        (root / "test_acceptance.py").write_text(tests, encoding="utf-8")
        (root / "runner.py").write_text(RUNNER, encoding="utf-8")
        # Controlled fixture, separate process, bounded wall time. Not an OS sandbox.
        proc = subprocess.run([sys.executable, "-B", "runner.py"], cwd=root,
                              capture_output=True, text=True, timeout=10)
        if proc.returncode not in (0, 1):
            raise RuntimeError("Python runner failed: " + proc.stderr[:1000])
        try:
            evidence = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Runner returned no valid evidence") from exc
        for row in evidence["results"]:
            row["detail"] = row["detail"].replace(directory, "<execution>")
        evidence.update(exit_code=proc.returncode, log=proc.stderr.replace(directory, "<execution>"), at=now(),
                        source_sha256=digest(source), tests_sha256=digest(tests),
                        python=sys.version.split()[0], command="python -B runner.py")
        return evidence


class ProofStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = ProcessLock(self.root / ".lock")

    def _path(self, proof_id):
        if not isinstance(proof_id, str) or not re.fullmatch(r"[a-f0-9]{32}", proof_id):
            raise ValueError("Invalid proof ID")
        return self.root / (proof_id + ".json")

    def get(self, proof_id):
        with self.lock:
            path = self._path(proof_id)
            if not path.exists():
                raise ValueError("Proof not found")
            return json.loads(path.read_text(encoding="utf-8"))

    def save(self, proof):
        path = self._path(proof["id"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        temporary.replace(path)

    def event(self, proof, action):
        previous = proof["audit"][-1]["hash"] if proof["audit"] else "0" * 64
        row = {"at": now(), "action": action, "previous": previous}
        row["hash"] = digest(row)
        proof["audit"].append(row)

    def create(self, requirement):
        with self.lock:
            contract = compile_requirement(requirement)
            cases = cases_for(contract["days"])
            proof = {"id": uuid.uuid4().hex, "created_at": now(), "requirement": requirement,
                     "mode": "deterministic refund-policy compiler", "contract": contract,
                     "criteria": cases, "tests": test_source(cases),
                     "original_source": source_for(contract["days"]), "state": "draft",
                     "before": None, "after": None, "proposal": None, "approval": None, "audit": []}
            self.event(proof, "Acceptance criteria and executable tests created")
            self.save(proof)
            return proof

    def run(self, proof_id):
        with self.lock:
            proof = self.get(proof_id)
            if proof["state"] != "draft":
                raise ValueError("Baseline can only run once; create a new proof to change requirements.")
            proof["before"] = execute(proof["original_source"], proof["tests"])
            proof["state"] = "failed" if proof["before"]["exit_code"] else "passed"
            self.event(proof, "Human confirmed displayed contract; baseline tests executed")
            self.save(proof)
            return proof

    def propose(self, proof_id):
        with self.lock:
            proof = self.get(proof_id)
            if proof["state"] != "failed":
                raise ValueError("Run failing baseline tests before proposing a patch.")
            if digest(proof["tests"]) != proof["before"]["tests_sha256"] or digest(proof["original_source"]) != proof["before"]["source_sha256"]:
                raise ValueError("Baseline inputs changed; create a fresh proof.")
            fixed = source_for(proof["contract"]["days"], fixed=True)
            diff = "".join(difflib.unified_diff(proof["original_source"].splitlines(True),
                                               fixed.splitlines(True), "a/subject.py", "b/subject.py"))
            proposal = {"source": fixed, "diff": diff, "base_sha256": digest(proof["original_source"]),
                        "tests_sha256": digest(proof["tests"]),
                        "diagnosis": [{"criterion": "AC2", "reason": "The >= comparison rejects the inclusive boundary. Change it to >."},
                                      {"criterion": "AC4", "reason": "The used-item branch returns the purchase amount. Return zero."}]}
            proposal["sha256"] = digest(proposal)
            proof["proposal"] = proposal
            proof["state"] = "awaiting_approval"
            self.event(proof, "Two-line patch proposed; no source changed")
            self.save(proof)
            return proof

    def approve(self, proof_id, proposal_sha256, approved):
        with self.lock:
            proof = self.get(proof_id)
            if approved is not True:
                raise ValueError("Explicit human approval is required.")
            if proof["state"] != "awaiting_approval":
                raise ValueError("There is no pending patch to approve.")
            proposal = proof["proposal"]
            if proposal_sha256 != proposal["sha256"]:
                raise ValueError("Stale proposal. Review the current diff before approval.")
            check = {key: value for key, value in proposal.items() if key != "sha256"}
            if (digest(check) != proposal["sha256"]
                    or digest(proof["tests"]) != proposal["tests_sha256"]
                    or digest(proof["original_source"]) != proposal["base_sha256"]
                    or proposal["tests_sha256"] != proof["before"]["tests_sha256"]
                    or proposal["base_sha256"] != proof["before"]["source_sha256"]):
                raise ValueError("Proof inputs changed; create a fresh proof.")
            proof["approval"] = {"at": now(), "proposal_sha256": proposal_sha256,
                                 "actor": "local reviewer", "scope": "apply displayed fixture patch and rerun frozen tests"}
            self.event(proof, "Reviewer approved the exact patch hash")
            proof["after"] = execute(proposal["source"], proof["tests"])
            proof["state"] = "verified" if proof["after"]["exit_code"] == 0 else "patch_failed"
            self.event(proof, "Patched fixture executed against unchanged acceptance tests")
            self.save(proof)
            return proof

    def reject(self, proof_id):
        with self.lock:
            proof = self.get(proof_id)
            if proof["state"] != "awaiting_approval":
                raise ValueError("There is no pending patch to reject.")
            proof["state"] = "rejected"
            self.event(proof, "Reviewer rejected patch; original source preserved")
            self.save(proof)
            return proof

    def bundle(self, proof_id):
        proof = self.get(proof_id)
        files = {"proof.json": json.dumps(proof, indent=2), "original/subject.py": proof["original_source"],
                 "original/test_acceptance.py": proof["tests"], "runner.py": RUNNER,
                 "README.txt": "Spec2Proof evidence\nRun: cd original && python -m unittest -v\nIf approved: cd patched && python -m unittest -v\nHashes establish internal consistency, not independent attestation.\n"}
        if proof["proposal"]:
            files["proposed.patch"] = proof["proposal"]["diff"]
        if proof["approval"]:
            files["patched/subject.py"] = proof["proposal"]["source"]
            files["patched/test_acceptance.py"] = proof["tests"]
        files["SHA256SUMS.json"] = json.dumps({name: digest(value) for name, value in files.items()}, indent=2)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        return buffer.getvalue()
