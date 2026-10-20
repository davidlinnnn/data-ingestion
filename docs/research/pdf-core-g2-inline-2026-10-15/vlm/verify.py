"""Check frozen inputs, token/decoder evidence and CPU guards without inference."""

import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("inline_frozen_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    rows = []
    for phase, expected_count, cap in [("page", 5, 4096), ("paragraph", 17, 1024)]:
        assert runner.frozen(phase) == json.loads((HERE / phase / "frozen-inputs.json").read_text())
        summary = json.loads((HERE / phase / "summary.json").read_text())
        assert summary["runner_sha256"] == runner.sha(HERE / "run.py")
        assert len(summary["jobs"]) == expected_count
        for job in summary["jobs"]:
            out = HERE / phase / "runs" / job["id"]
            assert job["exit_code"] == 0 and job["stopped"] is None
            assert job["available_before_bytes"] >= 8 * 1024**3
            assert job["child_wall_seconds"] < 180 and job["sampled_tree_peak_rss_bytes"] <= 6 * 1024**3
            generation = json.loads((out / "generation.json").read_text())
            model = json.loads((out / "actual-model.json").read_text())
            decoder = json.loads((out / "decoder-before-rstrip.json").read_text())
            engine_input = json.loads((out / "engine-input.json").read_text())
            engine_output = json.loads((out / "engine-output.json").read_text())
            method = json.loads((out / "method.json").read_text())
            ids = generation["generated_ids"]
            assert len(ids) == generation["generated_tokens"]
            assert generation["full_sequence_ids"][generation["input_tokens"]:] == ids
            assert generation["actual_received_max_new_tokens"] == cap == engine_input["max_new_tokens"]
            assert engine_input["prompt"] == "Convert this page to docling." and engine_input["temperature"] == 0
            assert model["devices"] == ["cpu"] and model["dtypes"] == ["torch.float32"]
            assert all(value["device"] == "cpu" for value in generation["input_tensors"].values())
            assert method["model_calls"] == 1 and method["actual_torch_threads"] == 4 and method["actual_torch_interop_threads"] == 1
            assert engine_output[0]["text"] == decoder["texts"][0].rstrip(generation["pad_token"])
            assert engine_output[0]["text"] == (out / "engine-output.txt").read_text()
            if phase == "paragraph":
                source = json.loads((out / "source-input.json").read_text())
                original = Image.open(runner.REPO / source["image_path"]).convert("RGB")
                received = Image.open(out / "engine-input.png").convert("RGB")
                assert original.size == received.size and ImageChops.difference(original, received).getbbox() is None
                assert method["path"].startswith("paragraph engine")
            else:
                assert engine_input["extra_generation_config"] == {} and engine_input["stop_strings"] == []
                assert method["path"] == "official VlmPipeline" and (out / "conversion-result.json").exists()
                assert (out / "document.json").exists() and (out / "document.md").exists()
            rows.append({"phase": phase, "id": job["id"], "generated_tokens": len(ids),
                         "last_token_is_eos": generation["last_token_is_eos"], "at_token_limit": generation["at_token_limit"],
                         "engine_rstrip_changed_precleanup_text": decoder["texts"][0] != engine_output[0]["text"],
                         "token_aware_differs_from_engine_output": (out / "token-aware-decode.txt").read_text() != engine_output[0]["text"],
                         "child_wall_seconds": job["child_wall_seconds"], "sampled_tree_peak_rss_bytes": job["sampled_tree_peak_rss_bytes"]})
    replay = json.loads((HERE / "assembly-replay/verification.json").read_text())
    assert replay["checks"] == "passed" and replay["model_calls"] == 0
    replay_inputs = json.loads((HERE / "assembly-replay/input-manifest.json").read_text())
    for entry in replay_inputs["inputs"]:
        assert runner.sha(runner.REPO / entry["path"]) == entry["sha256"]
    for variant in replay["variants"]:
        assert variant["parser_page_keys"] == [1, 2] and variant["boundary_parts_are_separate_text_items"]
        assert not variant["text_items_spanning_multiple_parser_pages"]
        doc = json.loads((HERE / "assembly-replay" / variant["variant"] / "document.json").read_text())
        assert len(doc["texts"]) == variant["text_items"] == 36
    result = {"checks": "passed", "scope": "Saved evidence integrity/CPU/resources/decoder reproduction and official assembly-only replay; semantic/source oracle judgment is independent",
              "jobs": rows, "total_model_calls": len(rows), "all_last_token_eos": all(r["last_token_is_eos"] for r in rows),
              "any_token_cap": any(r["at_token_limit"] for r in rows), "assembly_replay": replay}
    runner.save(HERE / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "jobs"}))


if __name__ == "__main__":
    main()
