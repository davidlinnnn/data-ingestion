"""Q04 test worker: interrupt one owned required-evidence child, then fail closed."""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import worker
from consumer import require


def owned_evidence_child_command(command, python):
    return command in (
        [python, "-m", "pdf_processing.evidence"],
        [python, "-m", "pdf_processing.lifecycle_child", "pdf_processing.evidence"],
    )


def should_inject(generation):
    return generation == 1


def audit_plan_incomplete(store, evidence_id, plan_id, operations):
    if store.resolve(evidence_id) is not None:
        raise RuntimeError("interruption_evidence_already_published")
    for operation in operations:
        if not operation.startswith("pdf-complete-"):
            continue
        registration = store.resolve(operation)
        file = next(item for item in registration["files"]
                    if item["name"] == "processing-result.json")
        if json.loads(store.read_artifact(file))["plan"] == plan_id:
            raise RuntimeError("interruption_complete_already_published")
    return operations


def install_hook(config, out):
    from temporalio import activity
    from temporalio.exceptions import ApplicationError
    from interruption import EvidenceInterruption, interrupted_call, registration_operations
    from pdf_processing import processing as production_processing
    from pdf_processing.compatibility import dependencies
    from pdf_processing.object_store import digest
    from pdf_processing.processing import encoded

    class ScopedInterruption(EvidenceInterruption):
        """A prior fresh complete may exist; this new plan must remain incomplete."""

        def __init__(self, *args, plan_id, **kwargs):
            super().__init__(*args, **kwargs)
            self.plan_id = plan_id

        def evidence_children(self):
            import psutil
            return [child for child in psutil.Process(os.getpid()).children(recursive=False)
                    if owned_evidence_child_command(child.cmdline(), sys.executable)]

        def audit_incomplete(self):
            return audit_plan_incomplete(self.store, self.evidence_id, self.plan_id,
                                         registration_operations(self.store))

    original = production_processing.Processing
    target = config["profiles"]["native-evidence"]
    marker = out / "interruption-claimed.json"

    class InjectedProcessing(original):
        @activity.defn(name="pdf_processing_step_v1")
        async def run(self, value):
            if (value["stage"] != "finalize" or self.profile != target
                    or marker.exists()):
                return await original.run(self, value)
            marker.write_text(json.dumps({"plan": value["plan"], "stage": "finalize"}))
            from pdf_processing.enrichment import Enrichment
            reader = Enrichment(self)
            plan = await asyncio.to_thread(self.load_plan, value["plan"])
            selection = await asyncio.to_thread(reader.read, value["selection"], "selection.json")
            registration = await asyncio.to_thread(self.store.resolve, selection["assembly"])
            document_file = next(file for file in registration["files"]
                                 if file["name"] == "document.json")
            document = await asyncio.to_thread(self.store.read_artifact, document_file)
            request = plan["request"]
            policy = plan["profile"]["content_evidence"]
            evidence_id = "pdf-evidence-v1:" + digest(encoded({
                "assembly": selection["assembly"], "parsed_result": selection["parsed_result"],
                "source": request, "policy": policy,
                "dependencies": dependencies("evidence", plan["profile"], plan["producer"]),
            }))
            hook = ScopedInterruption(self.store, self.scratch, evidence_id,
                                      request["artifact"]["sha256"], digest(document),
                                      out / "interruption", timeout=45,
                                      plan_id=value["plan"])
            observation, failure = await interrupted_call(
                hook, lambda: original.run(self, value))
            require(isinstance(failure, ApplicationError)
                    and failure.type == "parser"
                    and "execution_failed" in str(failure),
                    "injected child failure changed")
            (out / "interruption-result.json").write_text(json.dumps({
                "plan": value["plan"], "evidence_id": evidence_id,
                "original_failure": str(failure), "observation": observation,
            }, indent=2))
            # The production child failure was observed. Make this deliberately
            # injected Activity terminal so Temporal does not auto-retry it.
            raise ApplicationError("execution_failed",
                                   {"category": "parser", "code": "execution_failed"},
                                   type="parser", non_retryable=True) from failure

    production_processing.Processing = InjectedProcessing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--generation", type=int, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    require(config["window"]["starts_at"] <= time.time() < config["window"]["ends_at"],
            "outside capacity window")
    if should_inject(args.generation):
        install_hook(config, args.out)
    try:
        asyncio.run(asyncio.wait_for(worker.run(args.config, args.out, args.generation),
                                    timeout=config["window"]["ends_at"] - time.time()))
    except BaseException:
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
