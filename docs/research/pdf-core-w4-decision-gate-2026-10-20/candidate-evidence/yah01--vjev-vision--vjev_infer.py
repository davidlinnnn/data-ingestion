"""Stand-alone inference for vjev: typed decisions from text and images, one forward pass.

    pip install "transformers>=5.15" torch pillow safetensors

    from vjev_infer import Vjev
    m = Vjev("yah01/vjev-vision")            # cuda, mps or cpu; bf16 on cuda, fp16 on mps
    m.ask(state=["photo.jpg", "Frame from the warehouse camera."],
          questions={"person": {"type": "noul", "instructions": "There is a person in this image."},
                     "where":  {"type": "choice", "instructions": "Where is the forklift?",
                                "criteria": {"left": "left half", "right": "right half", "none": "no forklift"}},
                     "busy":   {"type": "score", "instructions": "How cluttered is the scene?",
                                "criteria": ["empty", "sparse", "busy", "crowded"]}})
    # -> {"person": {"type": "noul", "noul": 0.93},
    #     "where": {"type": "choice", "choice": "left", "probabilities": {...}, "confidence": ...},
    #     "busy": {"type": "score", "score": 1.4, "probabilities": {"0": ..}, "legend": {...}}}

`state` is a string, a PIL image, a path, or a list mixing them (images first is not required,
but text is placed after all images). Every question is scored on its own: questions never see
each other. Options of one choice/score question do see each other - that is the point of the
listwise readout - and are read in the order given.

This file is the minimum needed to use the weights; the project it comes from also has a
Jev-compatible HTTP server, a web console, prefix sharing across questions, and the training code.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

MAX_SIDE = 512                     # every training image had its longer side at 512 px


def label(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def fit(image: Image.Image) -> Image.Image:
    w, h = image.size
    if max(w, h) <= MAX_SIDE:
        return image
    k = MAX_SIDE / max(w, h)
    return image.resize((max(1, int(w * k)), max(1, int(h * k))))


class Vjev:
    def __init__(self, repo: str, device: str | None = None, dtype=None):
        from huggingface_hub import hf_hub_download
        from transformers import AutoModelForImageTextToText, AutoProcessor
        device = device or ("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        dtype = dtype or (torch.float16 if device == "mps" else torch.bfloat16)
        self.device = device
        self.proc = AutoProcessor.from_pretrained(repo)
        self.tok = self.proc.tokenizer
        full = AutoModelForImageTextToText.from_pretrained(repo, dtype=dtype, attn_implementation="sdpa")
        self.trunk = full.model.to(device).eval()            # the vocabulary projection is unused
        self.trunk.config.use_cache = False
        self.cfg = full.config
        get = (lambda f: Path(repo) / f) if Path(repo).is_dir() else (lambda f: hf_hub_download(repo, f))
        self.meta = json.loads(Path(get("vjev.json")).read_text())
        hidden = self.cfg.text_config.hidden_size
        self.head = nn.Linear(hidden, 1, dtype=torch.float32)
        self.head.load_state_dict(torch.load(get("head.pt"), map_location="cpu"))
        self.head.to(device)
        self._linear_patch_embed()

    def _linear_patch_embed(self):
        # The ViT's patch embedding is a Conv3d whose kernel == stride == input: a linear map of
        # each flattened patch. As a Conv3d torch runs it very slowly in bf16 on CUDA (measured
        # 35 s per 8 images); the same weights as one matmul take milliseconds.
        pe = self.trunk.visual.patch_embed

        def forward(x):
            w = pe.proj.weight
            return F.linear(x.to(w.dtype).view(-1, w[0].numel()), w.view(w.size(0), -1), pe.proj.bias)
        pe.forward = forward

    # ---- rendering -------------------------------------------------------------
    def _ids(self, s: str) -> list[int]:
        return self.tok(s, add_special_tokens=False).input_ids

    def _render(self, images: list[Image.Image], grids: list[int], text: str, q: dict):
        cfg = self.cfg
        ids, types = [], []
        for i, n in enumerate(grids):
            if len(grids) > 1:                              # several images are numbered
                lab = self._ids(("" if i == 0 else "\n") + f"Picture {i + 1}: ")
                ids += lab; types += [0] * len(lab)
            ids += [cfg.vision_start_token_id] + [cfg.image_token_id] * n + [cfg.vision_end_token_id]
            types += [0] + [1] * n + [0]
        if text:
            ids += self._ids(text)
        ids += self._ids(f"\n\nQuestion: {q['instructions']}")
        t = q["type"]
        opts = [] if t == "noul" else (list(q["criteria"].values()) if isinstance(q["criteria"], dict) else list(q["criteria"]))
        slots = []
        if t == "noul":
            slots.append(len(ids) - 1)
        else:
            for i, o in enumerate(opts):
                ids += self._ids(f"\n({label(i)}) {o}")
            ids += self._ids("\nAnswer:")                   # trailing readout: every slot after the whole list
            for i in range(len(opts)):
                ids += self._ids(f" ({label(i)})")
                slots.append(len(ids) - 1)
        types += [0] * (len(ids) - len(types))
        if len(ids) > self.meta.get("max_len", 2560) + 1536:
            raise ValueError(f"question {q['instructions'][:40]!r}: {len(ids)} tokens is over the limit")
        return ids, types, slots

    # ---- scoring ---------------------------------------------------------------
    @torch.no_grad()
    def ask(self, state, questions: dict, batch_rows: int = 8) -> dict:
        items = state if isinstance(state, list) else [state]
        images, texts = [], []
        for x in items:
            if isinstance(x, Image.Image):
                images.append(fit(x.convert("RGB")))
            elif isinstance(x, (str, Path)) and Path(x).is_file():
                images.append(fit(Image.open(x).convert("RGB")))
            else:
                texts.append(str(x))
        text = "\n".join(texts)
        mm, grids = {}, []
        if images:
            out = self.proc.image_processor(images=images, return_tensors="pt")
            merge = self.proc.image_processor.merge_size ** 2
            grids = [int(g.prod()) // merge for g in out["image_grid_thw"]]
            mm = {"pixel_values": out["pixel_values"].to(self.device), "image_grid_thw": out["image_grid_thw"].to(self.device)}
        rendered = {name: self._render(images, grids, text, q) for name, q in questions.items()}
        pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id
        answers, names = {}, list(rendered)
        for b0 in range(0, len(names), batch_rows):
            batch = names[b0:b0 + batch_rows]
            S = max(len(rendered[n][0]) for n in batch)
            ids = torch.full((len(batch), S), pad, dtype=torch.long)
            att = torch.zeros((len(batch), S), dtype=torch.long)
            typ = torch.zeros((len(batch), S), dtype=torch.long)
            for i, n in enumerate(batch):                    # left-padded, as in training
                r_ids, r_typ, _ = rendered[n]
                ids[i, S - len(r_ids):] = torch.tensor(r_ids); att[i, S - len(r_ids):] = 1
                typ[i, S - len(r_ids):] = torch.tensor(r_typ)
            kw = dict(mm)
            if images:
                kw["pixel_values"] = mm["pixel_values"].repeat(len(batch), 1)
                kw["image_grid_thw"] = mm["image_grid_thw"].repeat(len(batch), 1)
                kw["mm_token_type_ids"] = typ.to(self.device)
            h = self.trunk(input_ids=ids.to(self.device), attention_mask=att.to(self.device), **kw).last_hidden_state
            for i, n in enumerate(batch):
                slots = torch.tensor(rendered[n][2], device=self.device) + (S - len(rendered[n][0]))
                logits = self.head(h[i, slots].float()).squeeze(-1)
                answers[n] = self._answer(questions[n], logits)
        return answers

    @staticmethod
    def _answer(q: dict, logits: torch.Tensor) -> dict:
        t = q["type"]
        if t == "noul":
            return {"type": "noul", "noul": round(float(torch.sigmoid(logits[0])), 4)}
        p = torch.softmax(logits, -1).tolist()
        n = len(p)
        conf = round(max(0.0, (max(p) - 1 / n) / (1 - 1 / n)), 4) if n > 1 else 0.0
        if t == "choice":
            keys = list(q["criteria"])
            probs = {k: round(v, 4) for k, v in zip(keys, p)}
            return {"type": "choice", "choice": max(probs, key=probs.get), "confidence": conf, "probabilities": probs}
        levels = list(q["criteria"])
        return {"type": "score", "score": round(sum(i * v for i, v in enumerate(p)), 4), "confidence": conf,
                "legend": {str(i): l for i, l in enumerate(levels)},
                "probabilities": {str(i): round(v, 4) for i, v in enumerate(p)}}
