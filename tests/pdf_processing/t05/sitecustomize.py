"""Validation-only native child resists TERM; parent installs its asyncio handler."""
import os
import signal
if os.environ.get('T05_IGNORE_TERM') == '1':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
