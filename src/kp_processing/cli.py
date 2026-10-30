"""kp-processing command line. Later tickets add `worker`, `start-request` and
`list-service-unavailable`."""

import sys


def main(argv: list[str] | None = None) -> int:
    """`kp-processing profile [PATH]`: load the profile (default: the bundled
    paper-pdf@1) and print one line per method:
    `<id>@<version>  module_digest=<hex>  components=<c1>,<c2>,...` (components empty when
    none). A ProfileError prints to stderr and exits 1."""
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
