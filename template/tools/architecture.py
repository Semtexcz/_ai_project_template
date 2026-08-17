from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false
import argparse
import fnmatch
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised before generated setup
    yaml = None


DEFAULT_CONFIG = "quality.yaml"
DEFAULT_EXCLUDE = [
    ".git/**",
    ".venv/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    ".output/**",
    "coverage/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "__pycache__/**",
    "**/__pycache__/**",
    ".mypy_cache/**",
    ".pyright/**",
    "artifacts/**",
    "generated/**",
    "vendor/**",
]


class ArchitectureError(Exception):
    pass


@dataclass(frozen=True)
class ModuleDesignConfig:
    target_loc: int
    soft_limit_loc: int
    hard_limit_loc: int
    exclude: tuple[str, ...]
    exceptions: dict[str, str]


@dataclass(frozen=True)
class ModuleReport:
    path: str
    loc: int
    status: str
    exempt: bool = False


def load_config(path: Path) -> ModuleDesignConfig:
    if not path.exists():
        raise ArchitectureError(f"{path} does not exist.")
    data = yaml_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchitectureError(f"{path} must contain a YAML mapping.")

    module_design = data.get("module_design")
    if not isinstance(module_design, dict):
        raise ArchitectureError("quality.yaml must define module_design.")
    if module_design.get("principle") != "single-responsibility":
        raise ArchitectureError("module_design.principle must be single-responsibility.")

    python = module_design.get("python")
    if not isinstance(python, dict):
        raise ArchitectureError("module_design.python must be a mapping.")

    target = positive_int(python, "target_loc")
    soft = positive_int(python, "soft_limit_loc")
    hard = positive_int(python, "hard_limit_loc")
    if not target <= soft <= hard:
        raise ArchitectureError(
            "module_design.python limits must satisfy "
            "target_loc <= soft_limit_loc <= hard_limit_loc."
        )

    exclude = tuple(DEFAULT_EXCLUDE + string_list(python.get("exclude", []), "exclude"))
    exceptions = parse_exceptions(python.get("exceptions", []))
    return ModuleDesignConfig(
        target_loc=target,
        soft_limit_loc=soft,
        hard_limit_loc=hard,
        exclude=exclude,
        exceptions=exceptions,
    )


def positive_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ArchitectureError(f"module_design.python.{key} must be a positive integer.")
    return value


def string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ArchitectureError(f"module_design.python.{name} must be a list of non-empty strings.")
    return value


def parse_exceptions(value: Any) -> dict[str, str]:
    if not isinstance(value, list):
        raise ArchitectureError("module_design.python.exceptions must be a list.")
    exceptions: dict[str, str] = {}
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ArchitectureError(f"exception #{index} must be a mapping.")
        path = item.get("path")
        reason = item.get("reason")
        if not isinstance(path, str) or not path.strip():
            raise ArchitectureError(f"exception #{index} must include a non-empty path.")
        if not isinstance(reason, str) or not reason.strip():
            raise ArchitectureError(f"exception for {path} must include a non-empty reason.")
        exceptions[normalize_pattern(path)] = reason.strip()
    return exceptions


def yaml_load(text: str) -> Any:
    if yaml is not None:
        return yaml.safe_load(text)
    return parse_yaml_subset(text)


def parse_yaml_value(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if value in {"[]", "[ ]"}:
        return []
    if value.isdigit():
        return int(value)
    return value.strip('"').strip("'")


def parse_yaml_subset(text: str) -> Any:
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def block(start: int, indent: int) -> tuple[Any, int]:
        container: Any = [] if start < len(lines) and lines[start].lstrip().startswith("- ") else {}
        index = start
        while index < len(lines):
            raw = lines[index]
            current_indent = len(raw) - len(raw.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ArchitectureError(f"Unsupported YAML indentation near: {raw}")
            stripped = raw.strip()
            if isinstance(container, list):
                if not stripped.startswith("- "):
                    break
                item = stripped[2:].strip()
                if ":" in item:
                    key, _, value_text = item.partition(":")
                    mapping: dict[str, Any] = {key.strip(): parse_yaml_value(value_text)}
                    index += 1
                    while index < len(lines):
                        next_raw = lines[index]
                        next_indent = len(next_raw) - len(next_raw.lstrip(" "))
                        if next_indent <= indent:
                            break
                        next_key, sep, next_value = next_raw.strip().partition(":")
                        if not sep:
                            raise ArchitectureError(f"Invalid YAML line: {next_raw}")
                        mapping[next_key.strip()] = parse_yaml_value(next_value)
                        index += 1
                    container.append(mapping)
                    continue
                container.append(parse_yaml_value(item))
                index += 1
                continue
            key, sep, value_text = stripped.partition(":")
            if not sep:
                raise ArchitectureError(f"Invalid YAML line: {raw}")
            if value_text.strip():
                container[key.strip()] = parse_yaml_value(value_text)
                index += 1
            else:
                value, index = block(index + 1, indent + 2)
                container[key.strip()] = value
        return container, index

    parsed, final_index = block(0, 0)
    if final_index != len(lines):
        raise ArchitectureError(f"Unsupported YAML near: {lines[final_index]}")
    return parsed


def normalize_pattern(pattern: str) -> str:
    normalized = pattern.strip().replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def source_loc(path: Path) -> int:
    loc = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            loc += 1
    return loc


def iter_python_modules(root: Path, config: ModuleDesignConfig) -> list[Path]:
    modules = []
    for path in sorted(root.rglob("*.py")):
        if path.is_file() and not is_excluded(root, path, config.exclude):
            modules.append(path)
    return modules


def is_excluded(root: Path, path: Path, patterns: tuple[str, ...]) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(matches(relative, pattern) for pattern in patterns)


def matches(relative: str, pattern: str) -> bool:
    normalized = normalize_pattern(pattern)
    return fnmatch.fnmatch(relative, normalized) or fnmatch.fnmatch(relative, f"**/{normalized}")


def is_exception(path: str, config: ModuleDesignConfig) -> bool:
    return any(matches(path, pattern) for pattern in config.exceptions)


def classify(path: str, loc: int, config: ModuleDesignConfig) -> ModuleReport:
    if loc > config.hard_limit_loc:
        if is_exception(path, config):
            return ModuleReport(path=path, loc=loc, status="WARNING", exempt=True)
        return ModuleReport(path=path, loc=loc, status="ERROR")
    if loc > config.soft_limit_loc:
        return ModuleReport(path=path, loc=loc, status="WARNING")
    return ModuleReport(path=path, loc=loc, status="OK")


def inspect_modules(root: Path, config: ModuleDesignConfig) -> list[ModuleReport]:
    reports = []
    for path in iter_python_modules(root, config):
        relative = path.relative_to(root).as_posix()
        reports.append(classify(relative, source_loc(path), config))
    return reports


def format_report(report: ModuleReport) -> str:
    suffix = " exempt" if report.exempt else ""
    return f"{report.status:7} {report.loc:4} LOC {report.path}{suffix}"


def check(root: Path, config_path: Path) -> int:
    config = load_config(config_path)
    reports = inspect_modules(root, config)
    for report in reports:
        print(format_report(report))
    errors = [report for report in reports if report.status == "ERROR"]
    warnings = [report for report in reports if report.status == "WARNING"]
    print(
        f"Architecture check: {len(reports)} modules, "
        f"{len(warnings)} warnings, {len(errors)} errors."
    )
    if errors:
        print(
            "Hard limit exceeded. Split by cohesive responsibility or add a documented exception.",
            file=sys.stderr,
        )
        return 1
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Python module size architecture rules.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root to inspect.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Quality configuration path. Defaults to {DEFAULT_CONFIG} under --root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()
    config_path = args.config.resolve() if args.config else root / DEFAULT_CONFIG
    try:
        return check(root, config_path)
    except (ArchitectureError, OSError, UnicodeDecodeError) as exc:
        print(f"Architecture check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
