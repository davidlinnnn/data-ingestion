"""kp-processing command line. Later tickets add `worker`, `start-request` and
`list-service-unavailable`."""

import argparse
import sys
from pathlib import Path

from kp_processing.profile import PROFILES_DIR, ProfileError, load_profile


def main(argv: list[str] | None = None) -> int:
    """`kp-processing profile [PATH]`: load the profile (default: the bundled
    paper-pdf@1) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1."""
    parser = argparse.ArgumentParser(prog="kp-processing")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile")
    profile.add_argument("path", nargs="?", type=Path, default=PROFILES_DIR / "paper-pdf@1.yaml")
    args = parser.parse_args(argv)
    try:
        loaded = load_profile(args.path)
    except ProfileError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for method in loaded.methods.values():
        print(
            f"{method.ref}  module_digest={method.module_digest}  "
            f"components={','.join(method.components)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
