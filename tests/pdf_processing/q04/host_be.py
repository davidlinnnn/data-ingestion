"""Keep Pod-local signal helpers outside strict process snapshots."""

from contextlib import contextmanager
import fcntl
import os
import time

from host_bc import Host as BCHost


@contextmanager
def lifecycle_boundary():
    path = os.environ.get('PDF_PROCESS_LIFECYCLE_LOCK')
    if not path:
        yield
        return
    with open(path, 'a') as stream:
        deadline = time.monotonic() + float(os.environ.get(
            'PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS', '1'))
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('process lifecycle lock timed out')
                time.sleep(.01)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Host(BCHost):
    def signal(self, pid, sig, child=False):
        try:
            with lifecycle_boundary():
                return super().signal(pid, sig, child)
        except RuntimeError as error:
            if str(error) == 'process lifecycle lock timed out':
                self.force_stop()
            raise
