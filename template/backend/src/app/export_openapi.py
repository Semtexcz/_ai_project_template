from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app
from app.shared.config.settings import Settings


def export_openapi(output_path: Path) -> None:
    app = create_app(Settings())
    document = app.openapi()

    # Force JSON serialization during export so invalid schemas fail before codegen.
    encoded = json.dumps(document, indent=2, sort_keys=True)
    json.loads(encoded)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{encoded}\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.export_openapi <output-path>")
    export_openapi(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
