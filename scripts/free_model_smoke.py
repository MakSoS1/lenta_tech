"""Deliberate live smoke of the official CLI bridge; never uses paid credentials."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.ostrovok.backend.app.agent.model_gateway import (
    FREE_MODELS,
    ModelGateway,
    PRIMARY_MODEL,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(FREE_MODELS), default=PRIMARY_MODEL)
    options = parser.parse_args()
    os.environ["LLM_MODE"] = "opencode"
    os.environ["OPENCODE_MODEL"] = options.model
    result = await ModelGateway().extract(
        "Из Москвы в Казань с 10 ноября 2026 на 3 ночи, 2 взрослых, до 60000 рублей.",
        {},
        "2026-10-24T12:00:00+03:00",
    )
    print(
        json.dumps(
            {"check": "official_cli_free_model", "result": result}, ensure_ascii=False
        )
    )
    return 0 if result["used"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
