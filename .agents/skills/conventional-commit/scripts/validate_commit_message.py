#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_TYPES = {
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
}
HEADER_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9][a-z0-9\-/]*)\))?(?P<breaking>!)?: (?P<summary>.+)$"
)


def validate(message: str) -> list[str]:
    errors: list[str] = []
    normalized = message.strip()
    if not normalized:
        return ["commit message must not be empty"]
    lines = normalized.splitlines()
    header = lines[0]
    if len(header) > 72:
        errors.append("header must be 72 characters or fewer")
    match = HEADER_RE.fullmatch(header)
    if not match:
        errors.append("header must match type(scope): summary")
        return errors
    commit_type = match.group("type")
    scope = match.group("scope")
    summary = match.group("summary")
    if commit_type not in ALLOWED_TYPES:
        errors.append(f"type must be one of: {', '.join(sorted(ALLOWED_TYPES))}")
    if scope and scope != scope.lower():
        errors.append("scope must be lowercase")
    if summary != summary.strip():
        errors.append("summary must not start or end with whitespace")
    if summary.endswith("."):
        errors.append("summary must not end with a period")
    if summary[0].isupper():
        errors.append("summary should start lowercase")
    if len(summary) > 60:
        errors.append("summary should be 60 characters or fewer")
    if len(lines) > 1:
        if lines[1] != "":
            errors.append("body must be separated from header by one blank line")
        for body_line in lines[2:]:
            if len(body_line) > 72:
                errors.append("body lines must be 72 characters or fewer")
                break
    return errors


def read_message(args: argparse.Namespace) -> str:
    if args.message:
        return args.message
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a conventional commit message.")
    parser.add_argument("--message", help="Commit message text to validate.")
    parser.add_argument("--file", help="Path to a file containing the commit message.")
    args = parser.parse_args()

    if bool(args.message) and bool(args.file):
        print("ERROR: use either --message or --file, not both")
        return 2

    message = read_message(args)
    errors = validate(message)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: commit message is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
