"""Group-5 baseline coordinator, reusing the accepted complete-output oracle.

The outer launch must supply a fresh T09b integration manifest and capacity
window. This entry point does not relax the inherited 29-group baseline contract.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'q04'))
sys.path.insert(0, str(HERE))
from candidate import warm_pod_window_db
from t09b_host import Host

warm_pod_window_db.base.Host = Host

if __name__ == '__main__':
    raise SystemExit(warm_pod_window_db.main())
