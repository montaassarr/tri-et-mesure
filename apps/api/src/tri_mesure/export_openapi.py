"""Write the OpenAPI spec to a file (used to generate the typed web client)."""

import json
import sys
from pathlib import Path

from tri_mesure.main import create_app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OpenAPI spec written to {out}")


if __name__ == "__main__":
    main()
