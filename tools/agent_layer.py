#!/usr/bin/env python3
"""Template-maintainer agent-layer mirror tool (repository-root only).

The template repository dogfoods its own agent layer: canonical skills,
schemas, and Codex adapters live under ``.agents/`` and ``.codex/`` and are
mirrored into ``template/.agents/`` and ``template/.codex/`` so generated
projects start from identical content. Historically every agent-layer change
was applied by hand to both trees (see audits/template-authoring-cost-audit.md).

This tool makes propagation deterministic and inspectable:

* ``check`` (default): verify every mirrored file is byte-identical to its
  canonical counterpart and that the mirror has no stale files. Exits non-zero
  and reports every drift path. ``make validate-agent-layer`` runs this and the
  canonical ``make check`` gate includes it, so canonical and derived assets
  cannot drift silently.
* ``sync``: copy changed canonical files into the mirror and remove stale
  mirrored files. Idempotent (a second run changes nothing) and never touches
  the intentional divergences below.

Intentional divergences (never mirrored): ``.agents/README.md`` and
``.agents/context-map.yaml`` differ from their ``template/.agents/``
counterparts on purpose - root describes the template repository's own agent
layer, the template versions describe generated projects (profile routing,
lightweight vs managed governance).

Usage: ``python tools/agent_layer.py {check|sync} [--root PATH]``
``--root`` defaults to the repository root and exists for deterministic tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# (pair name, canonical dir, mirror dir, excluded file names relative to the
# pair root). Excluded names are intentional divergences that belong to each
# representation and must never be overwritten or deleted by sync.
MIRROR_PAIRS: list[tuple[str, str, str, frozenset[str]]] = [
    (
        "agent layer",
        ".agents",
        "template/.agents",
        frozenset({"README.md", "context-map.yaml"}),
    ),
    ("codex adapter", ".codex", "template/.codex", frozenset()),
]


def _files_relative(directory: Path) -> set[str]:
    """Return file paths relative to ``directory`` (empty when absent)."""
    if not directory.exists():
        return set()
    return {
        path.relative_to(directory).as_posix()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def check_mirrors(root: Path) -> list[str]:
    """Return drift descriptions, or an empty list when mirrors are in sync."""
    errors: list[str] = []
    for _name, canonical_rel, mirror_rel, excluded in MIRROR_PAIRS:
        canonical_dir = root / canonical_rel
        mirror_dir = root / mirror_rel
        if not canonical_dir.exists():
            errors.append(f"{canonical_rel}/ does not exist; cannot validate mirrors.")
            continue
        canonical_files = {
            rel for rel in _files_relative(canonical_dir) if rel not in excluded
        }
        mirror_files = _files_relative(mirror_dir)
        for rel in sorted(canonical_files):
            source = canonical_dir / rel
            target = mirror_dir / rel
            if not target.exists():
                errors.append(f"{mirror_rel}/{rel} is missing its canonical counterpart.")
            elif target.read_bytes() != source.read_bytes():
                errors.append(f"{mirror_rel}/{rel} drifted from {canonical_rel}/{rel}.")
        for rel in sorted(mirror_files - canonical_files):
            if rel not in excluded:
                errors.append(f"{mirror_rel}/{rel} has no canonical counterpart (stale).")
    return errors


def sync_mirrors(root: Path) -> list[str]:
    """Propagate canonical files to mirrors; return human-readable actions."""
    actions: list[str] = []
    for _name, canonical_rel, mirror_rel, excluded in MIRROR_PAIRS:
        canonical_dir = root / canonical_rel
        mirror_dir = root / mirror_rel
        if not canonical_dir.exists():
            actions.append(f"SKIP {canonical_rel}/ does not exist.")
            continue
        mirror_dir.mkdir(parents=True, exist_ok=True)
        canonical_files = {
            rel for rel in _files_relative(canonical_dir) if rel not in excluded
        }
        for rel in sorted(canonical_files):
            source = canonical_dir / rel
            target = mirror_dir / rel
            if not target.exists() or target.read_bytes() != source.read_bytes():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
                actions.append(f"SYNC {mirror_rel}/{rel}")
        mirror_files = _files_relative(mirror_dir)
        for rel in sorted(mirror_files - canonical_files):
            if rel not in excluded:
                (mirror_dir / rel).unlink()
                actions.append(f"REMOVE {mirror_rel}/{rel} (no canonical counterpart)")
    return actions


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or synchronize the canonical agent-layer mirrors."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["check", "sync"],
        default="check",
        help="check verifies mirror parity; sync propagates canonical files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of this tool).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    root = args.root.resolve()
    if args.command == "sync":
        actions = sync_mirrors(root)
        for action in actions:
            print(action)
        if actions:
            print(f"{len(actions)} sync action(s).")
        else:
            print("Agent-layer mirrors are already in sync.")
        return 0
    errors = check_mirrors(root)
    if errors:
        for error in errors:
            print(error)
        print("Run `make sync-agent-layer` to propagate canonical files.")
        return 1
    print("Agent-layer mirrors are in sync (canonical root -> template mirrors).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

