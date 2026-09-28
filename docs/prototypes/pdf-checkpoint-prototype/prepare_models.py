"""Acquire exact model snapshots; pin the refs used by the unmodified Docling options."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['HF_HOME']=str(ROOT/'PROTOTYPE-wipe-me/hf')
from huggingface_hub import snapshot_download
for repo,revision,ref in [
    ('docling-project/docling-layout-heron','8f39ad3c0b4c58e9c2d2c84a38465abf757272d8','main'),
    ('docling-project/docling-models','fc0f2d45e2218ea24bce5045f58a389aed16dc23','v2.3.0')]:
    snapshot=Path(snapshot_download(repo_id=repo,revision=revision))
    target=snapshot.parent.parent/'refs'/ref
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(revision)
    print(repo,revision)
