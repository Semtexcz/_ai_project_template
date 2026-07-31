from pathlib import Path


def test_domain_does_not_import_frameworks() -> None:
    domain_files = Path("src/app/modules").glob("*/domain/**/*.py")
    forbidden = ("fastapi", "sqlalchemy", "httpx")
    offenders: list[str] = []

    for path in domain_files:
        text = path.read_text()
        if any(f"import {name}" in text or f"from {name}" in text for name in forbidden):
            offenders.append(str(path))

    assert offenders == []
