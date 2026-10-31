"""The inference worker without its one-slot limit: the shape before the split."""
import sys

import temporalio.worker as tw

_init = tw.Worker.__init__


def init(self, *args, **kwargs):
    kwargs.pop("max_concurrent_activities", None)
    _init(self, *args, **kwargs)


tw.Worker.__init__ = init
from kp_processing.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
