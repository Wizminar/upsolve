"""Write the OpenAPI 3 document to docs/openapi.json (for the report and the partner team).

Usage: python -m scripts.export_openapi
"""

import json
import sys

from app import config
from app.main import app


def main() -> int:
    out = config.ROOT / "docs" / "openapi.json"
    out.parent.mkdir(exist_ok=True)
    spec = app.openapi()
    out.write_text(json.dumps(spec, indent=2))
    print(f"Wrote {out} ({len(spec['paths'])} paths, OpenAPI {spec['openapi']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
