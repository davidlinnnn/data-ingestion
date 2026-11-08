"""Processing Profile: a released, immutable yaml file shipped with the worker (ADR-0010)."""

import importlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import yaml

from kp_canonicalization.identity import module_digest, reuse_key

PROFILES_DIR = Path(__file__).parent / "profiles"
# The inference egresses of the data-security design §5; a new one updates §5 in the same PR.
Service = Literal["vlm", "summary", "d3"]
SERVICES: tuple[Service, ...] = ("vlm", "summary", "d3")
# The runtime keys the code reads, as dotted paths, each a number; else the profile does not
# load. Workflow code reads some of them, where a bad value would retry the task forever.
REQUIRED_RUNTIME = (
    "heartbeat_interval_s",
    "heartbeat_timeout_s.inference",
    "heartbeat_timeout_s.vlm",
    "heartbeat_timeout_s.summary",
    "heartbeat_timeout_s.d3",
    "start_to_close_s.orchestration",
    "start_to_close_s.inference",
    *(
        f"activity_retry.{queue}.{key}"
        for queue in ("orchestration", "inference", "vlm", "summary", "d3")
        for key in ("initial_s", "multiplier", "cap_s", "max_attempts")
    ),
    "external_start_to_close_slack_s",
    "vlm_request_deadline_s.connect",
    "vlm_request_deadline_s.total",
    "d3_request_deadline_s.connect",
    "d3_request_deadline_s.total",
    "d3_concurrency_per_document",
    "summary_request_deadline_s.connect",
    "summary_request_deadline_s.total",
    "summary_budget_s",
    "summary_concurrency_per_document",
    "summary_requests_per_worker",
    *(f"retry.{key}" for key in ("initial_s", "multiplier", "cap_s", "max_attempts")),
    "vlm_concurrency_per_document",
    "request_cap.per_item",
    "request_cap.per_section",
    "request_cap.extra",
    "enrichment_stage_budget_s.hard",
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
    package: ModuleType = field(compare=False, repr=False)  # kp_canonicalization.methods.<id>

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    @property
    def scope(self) -> Literal["item", "document"] | None:
        """ "item" for a package that declares TARGET, the package's SCOPE ("document") when it
        declares one, None for a method without inventory items (docling-parse, a Quality
        Check)."""
        if hasattr(self.package, "SCOPE"):
            return self.package.SCOPE
        return "item" if hasattr(self.package, "TARGET") else None

    @property
    def service(self) -> Service | None:
        """The external service whose Activities run its items: the package's SERVICE when it
        declares one, else "vlm" when it declares request and parse; None for a package that
        declares only run, whose items run in the local Activity."""
        if hasattr(self.package, "SERVICE"):
            return self.package.SERVICE
        return "vlm" if hasattr(self.package, "request") else None

    @property
    def checks(self) -> dict[str, Any]:
        """A Quality Check package's CHECKS, {judged method ref: Check}; {} for any other."""
        return getattr(self.package, "CHECKS", {})

    def reuse_key(self, document_uid: str, input_digests: Sequence[str]) -> str:
        """The reuse key of one of this method's items (identity.reuse_key)."""
        return reuse_key(document_uid, self.ref, self.components, self.module_digest, input_digests)


@dataclass(frozen=True)
class Limitation:
    code: str  # UPPER_SNAKE_CASE
    detail: str


@dataclass(frozen=True)
class ProcessingProfile:
    id: str  # "paper-pdf@1"
    released: bool
    status_rule: str
    methods: dict[str, Method]  # keyed by method id, in file order
    limitations: tuple[Limitation, ...]
    runtime: dict[str, Any]  # has every REQUIRED_RUNTIME key; never enters a reuse key

    @property
    def quality_check(self) -> Method | None:
        """The profile's Quality Check, its method with checks; None when it lists none."""
        return next((method for method in self.methods.values() if method.checks), None)


def load_profile(path: Path) -> ProcessingProfile:
    """Load a profile yaml and check it against the method packages.

    Raises ProfileError when a required key (profile, status_rule, methods, limitations,
    runtime) is missing, a methods key is not `<id>@<int>`, a method's package
    (kp_canonicalization.methods.<id with _>) does not exist, or the package's ID or VERSION
    differs from the listed `<id>@<version>`, a method's service is not one of SERVICES, a
    REQUIRED_RUNTIME key is missing or not a number, or a Quality Check judges a listed method
    at other versions only.
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
            if type(section) not in (int, float):
                raise ProfileError(f"{path}: runtime key {dotted} is not a number")
        methods: dict[str, Method] = {}
        for ref, entry in data["methods"].items():
            match = re.fullmatch(r"([a-z][a-z0-9-]*)@(\d+)", str(ref))
            if not match:
                raise ProfileError(f"{path}: malformed method key {ref!r}; expected <id>@<int>")
            method_id, version = match.group(1), int(match.group(2))
            if method_id in methods:
                raise ProfileError(f"{path}: duplicate method ID {method_id}")
            package_name = f"kp_canonicalization.methods.{method_id.replace('-', '_')}"
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
            method = Method(
                id=method_id,
                version=version,
                components=tuple(entry["components"]),
                module_digest=module_digest(Path(package.__file__).parent),
                package=package,
            )
            if method.service not in (None, *SERVICES):
                raise ProfileError(f"{path}: {ref} calls undeclared service {method.service!r}")
            methods[method_id] = method
        for check in methods.values():
            judged_ids = {ref.split("@")[0] for ref in check.checks}
            for method in methods.values():
                if method.id in judged_ids and method.ref not in check.checks:
                    raise ProfileError(f"{path}: {check.ref} has no check for {method.ref}")
        return ProcessingProfile(
            id=data["profile"],
            released=data.get("released", False),
            status_rule=data["status_rule"],
            methods=methods,
            limitations=tuple(Limitation(**entry) for entry in data["limitations"]),
            runtime=data["runtime"],
        )
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProfileError(f"{path}: {exc}") from exc
