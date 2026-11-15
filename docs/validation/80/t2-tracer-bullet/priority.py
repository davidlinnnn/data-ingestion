"""Does a normal request overtake a bulk backlog on one shared queue (#131, priority keys)?

One worker with a single Activity slot; eight low-priority workflows (key 4) are queued and
the first is running when two normal ones (key 2) start. Prints the order the Activities ran,
on the dev server's default partitions and with one partition. Run with `uv run python
docs/validation/80/t2-tracer-bullet/priority.py`; needs the `temporal` CLI.
"""

import asyncio
import shutil
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import Priority
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

ran: list[str] = []
started = asyncio.Event()


@activity.defn
async def work(name: str) -> None:
    ran.append(name)
    started.set()
    await asyncio.sleep(0.5)


@workflow.defn
class Probe:
    @workflow.run
    async def run(self, name: str) -> None:
        await workflow.execute_activity(work, name, start_to_close_timeout=timedelta(minutes=1))


async def trial(extra_args: list[str]) -> list[str]:
    ran.clear()
    started.clear()
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal"), dev_server_extra_args=extra_args
    ) as env:
        client = env.client

        async def start(name: str, key: int):
            return await client.start_workflow(
                Probe.run, name, id=name, task_queue="cpu", priority=Priority(priority_key=key)
            )

        handles = [await start(f"low-{i}", 4) for i in range(8)]
        async with Worker(
            client, task_queue="cpu", workflows=[Probe], activities=[work],
            max_concurrent_activities=1,
        ):  # fmt: skip
            await started.wait()
            handles += [await start(f"normal-{i}", 2) for i in range(2)]
            await asyncio.gather(*(h.result() for h in handles))
    return list(ran)


async def main() -> None:
    one = [
        "--dynamic-config-value", "matching.numTaskqueueReadPartitions=1",
        "--dynamic-config-value", "matching.numTaskqueueWritePartitions=1",
    ]  # fmt: skip
    for label, args in [("default partitions", []), ("one partition", one)]:
        for attempt in range(3):
            order = await trial(args)
            print(label, attempt + 1, [order.index("normal-0"), order.index("normal-1")], order)


if __name__ == "__main__":  # the workflow sandbox re-imports this module
    asyncio.run(main())
