from __future__ import annotations

import subprocess
import sys


def main() -> int:
    sync = subprocess.call([sys.executable, "tools/project.py", "sync"])
    if sync != 0:
        return sync
    return subprocess.call([sys.executable, "tools/project.py", "validate"])


if __name__ == "__main__":
    raise SystemExit(main())
