"""Processing Profile: a released, immutable yaml file shipped with the worker (ADR-0010)."""

import importlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from kp_processing import identity
from kp_processing.identity import module_digest

PROFILES_DIR = Path(__file__).parent / "profiles"
# The runtime keys the code reads, as dotted paths; a profile without one does not load.
REQUIRED_RUNTIME = (
    "heartbeat_interval_s",
    "heartbeat_timeout_s.inference",
    "start_to_close_s.orchestration",
    "start_to_close_s.inference",
    *(
        f"activity_retry.{queue}.{key}"
        for queue in ("orchestration", "inference")
        for key in ("initial_s", "multiplier", "cap_s", "max_attempts")
    ),
    "parse_group_pages",
    "preflight.max_pages",
    "preflight.max_bytes",
    "preflight.max_page_pixels",
    "status_report_budget_s",
)


class ProfileError(Exception):
    """Malformed profile, or one that disagrees with the method packages: do not start."""


@dataclass(frozen=True)
class Method:
    id: str  # "docling-parse"
    version: int  # 1
    components: tuple[str, ...]  # declared order, e.g. ("docling-slim@2.132.0", ...)
    module_digest: str  # hex sha256 of the method package, computed when the profile loads
    package: ModuleType = field(compare=False, repr=False)  # kp_processing.methods.<id>

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def reuse_key(self, document_uid: str, input_digests: Sequence[str]) -> str:
        """The reuse key of one of this method's items (identity.reuse_key)."""
        return identity.reuse_key(
            document_uid, self.ref, self.components, self.module_digest, input_digests
        )


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
    runtime: dict[str, Any]  # has every REQUIRED_RUNTIME key; never enters a reuse key


def load_profile(path: Path) -> Profile:
    """Load a profile yaml and check it against the method packages.

    Raises ProfileError when a required key (profile, status_rule, methods, limitations,
    runtime) is missing, a methods key is not `<id>@<int>`, a method's package
    (kp_processing.methods.<id with _>) does not exist, or the package's ID or VERSION
    differs from the listed `<id>@<version>`, or runtime lacks a REQUIRED_RUNTIME key.
    `released` defaults to False.
    """
    try:
        data = yaml.safe_load(path.read_text())
        for key in ("profile", "status_rule", "methods", "limitations", "runtime"):
            if key not in data:
                raise ProfileError(f"{path}: missing required key {key}")
        for dotted in REQUIRED_RUNTIME:
            section = data["runtime"]
            for part in dotted.split("."):
                if not isinstance(section, dict) or part not in section:
                    raise ProfileError(f"{path}: missing runtime key {dotted}")
                section = section[part]
        methods: dict[str, Method] = {}
        for ref, entry in data["methods"].items():
            match = re.fullmatch(r"([a-z][a-z0-9-]*)@(\d+)", str(ref))
            if not match:
                raise ProfileError(f"{path}: malformed method key {ref!r}; expected <id>@<int>")
            method_id, version = match.group(1), int(match.group(2))
            if method_id in methods:
                raise ProfileError(f"{path}: duplicate method ID {method_id}")
            package_name = f"kp_processing.methods.{method_id.replace('-', '_')}"
            try:
                package = importlib.import_module(package_name)
            except ImportError as exc:
                raise ProfileError(
                    f"{path}: cannot import method {ref} ({package_name}): {exc}"
                ) from exc
            if getattr(package, "ID", None) != method_id:
                raise ProfileError(f"{path}: {ref} package ID differs from {method_id}")
            if getattr(package, "VERSION", None) != version:
                raise ProfileError(f"{path}: {ref} package VERSION differs from {version}")
            if package.__file__ is None:
                raise ProfileError(f"{path}: {ref} package has no source file")
            methods[method_id] = Method(
                id=method_id,
                version=version,
                components=tuple(entry["components"]),
                module_digest=module_digest(Path(package.__file__).parent),
                package=package,
            )
        return Profile(
            profile=data["profile"],
            released=data.get("released", False),
            status_rule=data["status_rule"],
            methods=methods,
            limitations=tuple(Limitation(**entry) for entry in data["limitations"]),
            runtime=data["runtime"],
        )
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
