"""Processing Profile: a released, immutable yaml file shipped with the worker (ADR-0010)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROFILES_DIR = Path(__file__).parent / "profiles"


class ProfileError(Exception):
    """Malformed profile, or one that disagrees with the method packages: do not start."""


@dataclass(frozen=True)
class Method:
    id: str  # "docling-parse"
    version: int  # 1
    components: tuple[str, ...]  # declared order, e.g. ("docling-slim@2.132.0", ...)
    module_digest: str  # hex sha256 of the method package, computed when the profile loads

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class Limitation:
    code: str  # UPPER_SNAKE_CASE
    detail: str


@dataclass(frozen=True)
class Profile:
    profile: str  # "paper-pdf@1"
    released: bool
    status_rule: str
    methods: dict[str, Method]  # keyed by method id, in file order
    limitations: tuple[Limitation, ...]
    runtime: dict[str, Any]  # opaque here; never enters a reuse key


def load_profile(path: Path) -> Profile:
    """Load a profile yaml and check it against the method packages.

    Raises ProfileError when a required key (profile, status_rule, methods, limitations,
    runtime) is missing, a methods key is not `<id>@<int>`, a method's package
    (kp_processing.methods.<id with _>) does not exist, or the package's ID or VERSION
    differs from the listed `<id>@<version>`. `released` defaults to False.
    """
    raise NotImplementedError
