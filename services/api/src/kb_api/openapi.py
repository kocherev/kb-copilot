"""Print the OpenAPI schema. The web client types are generated from it."""

import json

from kb_api.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
