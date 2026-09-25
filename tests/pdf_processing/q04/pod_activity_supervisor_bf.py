"""Sample the Activity Pod before spawning its one current-v3 worker child."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import require
from pod_durable_evidence import write_once
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector


async def run(config_path: Path, root: Path, generation: int) -> None:
    config = json.loads(config_path.read_text())
    require(config['run_id'] == 'q04-pod-loss-pod-cgroup-20260925-bf'
            and config['pod_namespace'] == 'pdf-t09a-validation'
            and generation in (1, 2), 'Activity Pod supervisor identity changed')
    measurement = root.parent / (root.name + '-measurement') / f'worker-{generation}'
    measurement.mkdir(parents=True, exist_ok=False)
    collector = StrictAttributionCollector(
        measurement / 'resource-attribution.jsonl',
        measurement / 'resource-attribution-summary.json',
        root_pid=os.getpid(), observation_root=root,
        interval_seconds=.25, attribution_gap_seconds=1,
        lifecycle_lock_path=measurement / 'process-lifecycle.lock')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    collector.start()
    raw_stat = Path('/proc/self/stat').read_text()
    start_ticks = int(raw_stat[raw_stat.rfind(')') + 1:].split()[19])
    command = [config['python'], str(Path(__file__).with_name('worker_bc.py')),
               '--config', str(config_path), '--out', str(root / f'worker-{generation}'),
               '--generation', str(generation)]
    worker_env = os.environ.copy()
    worker_env['PDF_PROCESS_LIFECYCLE_LOCK'] = str(collector.lifecycle_lock_path)
    worker_env['PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS'] = '1'
    with (root / f'worker-{generation}.log').open('x') as log:
        worker = subprocess.Popen(command, env=worker_env, stdout=log,
                                  stderr=subprocess.STDOUT)
        write_once(measurement / 'supervisor-ownership.json', {
            'pid': os.getpid(), 'start_ticks': start_ticks,
            'worker_pid': worker.pid,
            'generation': generation, 'started': time.time(),
            'command': command}, volume_root=root.parents[1])
        try:
            while worker.poll() is None and not stop.is_set():
                collector.require_healthy()
                marker = measurement / 'stop-request.json'
                if marker.exists():
                    request = json.loads(marker.read_text())
                    require(request == {'run_id': config['run_id'],
                                        'generation': generation},
                            'Activity worker stop request identity changed')
                    stop.set()
                await asyncio.sleep(.1)
        finally:
            async def stop_worker():
                if worker.poll() is None:
                    worker.send_signal(signal.SIGTERM)
                    try:
                        await asyncio.to_thread(worker.wait, 35)
                    except subprocess.TimeoutExpired:
                        worker.kill()
                        await asyncio.to_thread(worker.wait, 10)
                require(worker.returncode == 0, 'Activity worker exited unsuccessfully')
            primary = None
            try:
                await collector.process_transition('controlled_worker_shutdown', stop_worker)
            except BaseException as error:
                primary = error
            outcome = collector.stop(expect_cancel=False,
                require_no_warm_fresh_overlap=True)
            if primary is not None:
                raise primary
            require(outcome.attribution_complete, 'Activity Pod process attribution incomplete')
            summary = json.loads((measurement / 'resource-attribution-summary.json').read_text())
            samples = [json.loads(line) for line in
                       (measurement / 'resource-attribution.jsonl').read_text().splitlines()]
            gate = evaluate_resource_gate(samples, summary)
            (measurement / 'all-sample-resource-gate.json').write_text(
                json.dumps(gate, sort_keys=True) + '\n')
            require(gate['status'] == 'PASS', 'Activity Pod resource gate failed')


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--config', required=True, type=Path)
    cli.add_argument('--root', required=True, type=Path)
    cli.add_argument('--generation', required=True, type=int)
    args = cli.parse_args(argv)
    asyncio.run(run(args.config, args.root, args.generation))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
