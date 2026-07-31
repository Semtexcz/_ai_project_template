from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    task = os.environ.get("TASK")
    if not task:
        print("ERROR: TASK is required for pre-task hook.")
        return 1
    return subprocess.call([sys.executable, "tools/agent.py", "pre-task", "--task", task])


if __name__ == "__main__":
    raise SystemExit(main())
