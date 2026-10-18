"""Print the real test total (the standard forbids `-qq` swallowing it)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header",
     "-p", "no:cacheprovider"],
    capture_output=True, text=True, cwd=ROOT,
)
tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
print(tail)
