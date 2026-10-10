"""Run repository checks and save an honest local test report."""
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root, capture_output=True, text=True)
report = {"verified_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
          "os": platform.system(), "command": "python -m unittest discover -s tests -v", "exit_code": process.returncode,
          "stdout": process.stdout, "stderr": process.stderr,
          "limits": ["GitHub Actions matrix has not run yet", "No live ChatGPT host installation or tunnel verified"]}
(root / "docs" / "test-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(process.stderr)
raise SystemExit(process.returncode)
