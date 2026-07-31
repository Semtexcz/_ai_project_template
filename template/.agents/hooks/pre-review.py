from __future__ import annotations

import subprocess


def main() -> int:
    return subprocess.call(["make", "check"])


if __name__ == "__main__":
    raise SystemExit(main())
