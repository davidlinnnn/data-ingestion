"""#174 held-out summaries: t5b-seam-b's run.py on the DEV profile without the d3 Quality Check.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/seamb_heldout.py \\
        PROFILE_COPY CORPUS_MANIFEST OUT_DIR INDEX...

#161 added d3-check@1 to the DEV profile after t5b-seam-b was written; that runner starts no d3
worker, so the check Activity, which runs after the summary, waits forever. The summary does
not read the check, so dropping it leaves the summaries unchanged. PROFILE_COPY (outside git)
gets the copy.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t5b_seam_b", HERE.parents[1] / "validation/80/t5b-seam-b/run.py")
seamb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seamb)

if __name__ == "__main__":
    copy = Path(sys.argv[1]).expanduser()
    profile = yaml.safe_load(Path(seamb.t2.PROFILE).read_text())
    del profile["methods"]["d3-check@1"]
    copy.write_text(yaml.safe_dump(profile, sort_keys=False))
    seamb.t2.PROFILE = str(copy)
    sys.exit(asyncio.run(seamb.main(sys.argv[2:])))
