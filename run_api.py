import os, sys

sys.path.insert(0, ".")

from src.api.app import create_app

import uvicorn

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=7860)
