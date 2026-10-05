"""Verify retained offline model/runtime bytes before accepting Activity work."""
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform


def memory_policy():
    """Retain #44's per-supervisor THP policy; inherited across child exec."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(41, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'cannot disable workload THP')
    if libc.prctl(42, 0, 0, 0, 0) != 1:
        raise OSError('workload THP policy readback failed')
    return {'thp_disabled': 1, 'pid': os.getpid(), 'inherited_by_children': True}


def verify(profile, cache):
    method = profile['method']
    if (method['python'] != platform.python_version() or method['platform'] != platform.platform()
            or method['packages'] != {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}):
        raise ValueError('bootstrap_runtime_mismatch')
    rapid = importlib.util.find_spec('rapidocr')
    if rapid is None or rapid.origin is None:
        raise ValueError('bootstrap_models_missing')
    for name, digest in method['model_artifacts'].items():
        path = (Path(rapid.origin).parent/'models'/name.split('/')[-1]
                if name.startswith('rapidocr/') else Path(cache)/name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('bootstrap_model_mismatch: '+name)
    return {'runtime': 'verified', 'models': len(method['model_artifacts']), 'offline': True}


if __name__ == '__main__':
    print(json.dumps(verify(json.loads(Path(os.environ['PROFILE_FILE']).read_text()), os.environ['MODEL_CACHE'])))
