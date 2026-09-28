"""One-page, no-network check of capture -> restore -> capture in one parser."""

import asyncio
import json
from pathlib import Path

from pdf_processing.execution import Execution
from pdf_processing.supervision import WarmParser


ROOT = Path("/workspace")
OUT = Path("/output")


async def main():
    config = json.loads((ROOT / "config.json").read_text())
    method = config["profiles"]["07"]["method"]
    common = {
        "pdf": "/input/07.pdf",
        "model_cache": "/experiment/PROTOTYPE-wipe-me/hf",
        "scan": False,
        "start": 1,
        "end": 1,
        "expected_method": method,
    }
    parser = WarmParser(max_requests=20)
    execution = Execution(None, None, OUT, child_runner=parser, child_timeout=180)
    observations = []
    capture_count = None
    try:
        for name, request in (
            ("capture-1", {**common, "mode": "capture", "checkpoint_only": True}),
            (
                "restore",
                {**common, "mode": "restore", "checkpoint": str(OUT / "capture-1")},
            ),
            ("capture-2", {**common, "mode": "capture", "checkpoint_only": True}),
        ):
            request["out"] = str(OUT / name)
            await execution.child("pdf_processing.parse", request, OUT)
            observations.append(dict(execution.observation["parser"]))
    finally:
        capture_count = parser.count
        await parser.close()

    restored = json.loads((OUT / "restore/metrics.json").read_text())
    assert len({row["pid"] for row in observations}) == 1
    assert [row["restarts"] for row in observations] == [1, 1, 1]
    assert observations[-1]["recycles"] == 0
    assert capture_count == 2
    assert not any(
        count
        for stage, count in restored["page_stage_inputs"].items()
        if stage.endswith("Model")
    )
    print(
        json.dumps(
            {
                "pid": observations[0]["pid"],
                "same_pid": True,
                "capture_requests": 2,
                "restore_page_stage_inputs": restored["page_stage_inputs"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
