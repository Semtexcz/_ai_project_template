from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
GENERATED = FRONTEND / "shared" / "api" / "generated"
HEADER = "/* DO NOT EDIT — generated from backend OpenAPI */\n"


def run_codegen(output_dir: Path) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "OPENAPI_CLIENT_OUTPUT": str(output_dir)}
    subprocess.run(
        [
            "pnpm",
            "--dir",
            str(FRONTEND),
            "exec",
            "openapi-ts",
            "-i",
            "../artifacts/openapi.json",
            "-o",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    stamp_generated_files(output_dir)


def stamp_generated_files(output_dir: Path) -> None:
    for path in sorted(output_dir.rglob("*.ts")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith(HEADER):
            path.write_text(f"{HEADER}{text}", encoding="utf-8")


def clear_generated() -> None:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)


def compare_dirs(expected: Path, actual: Path) -> list[str]:
    if not actual.exists():
        return [f"missing generated client directory: {actual.relative_to(ROOT)}"]

    comparison = filecmp.dircmp(expected, actual)
    differences: list[str] = []

    def collect(diff: filecmp.dircmp[str], relative: Path) -> None:
        for name in diff.left_only:
            differences.append(f"missing: {(relative / name).as_posix()}")
        for name in diff.right_only:
            differences.append(f"unexpected: {(relative / name).as_posix()}")
        for name in diff.diff_files:
            differences.append(f"changed: {(relative / name).as_posix()}")
        for name, child in diff.subdirs.items():
            collect(child, relative / name)

    collect(comparison, Path())
    return differences


def generate() -> None:
    clear_generated()
    run_codegen(GENERATED)


def check() -> None:
    with tempfile.TemporaryDirectory(prefix="openapi-client-") as tmp:
        expected = Path(tmp) / "generated"
        run_codegen(expected)
        differences = compare_dirs(expected, GENERATED)
        if differences:
            print("Generated OpenAPI client drift detected.")
            for difference in differences:
                print(f"- {difference}")
            print("Run `make api-generate` after updating the backend OpenAPI contract.")
            raise SystemExit(1)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"generate", "check"}:
        raise SystemExit("Usage: python tools/api_client.py <generate|check>")
    if sys.argv[1] == "generate":
        generate()
    else:
        check()


if __name__ == "__main__":
    main()
