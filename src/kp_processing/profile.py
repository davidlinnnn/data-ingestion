"""Processing Profile: a released, immutable yaml file shipped with the worker (ADR-0010)."""

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kp_processing.identity import module_digest

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
    try:
        data = yaml.safe_load(path.read_text())
        for key in ("profile", "status_rule", "methods", "limitations", "runtime"):
            if key not in data:
                raise ProfileError(f"{path}: missing required key {key}")
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
