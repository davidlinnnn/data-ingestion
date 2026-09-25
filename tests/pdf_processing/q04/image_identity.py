"""Fail-closed image identity binding for the fixed Q04 worker image.

OCI manifest digests, image config digests, and Kubernetes ``imageID`` values
name different objects.  This module accepts a runtime representation only
when committed, locally inspected evidence binds it to the pinned repository,
single-platform manifest, config object, and linux/arm64 platform.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


Q04 = Path(__file__).resolve().parent
EVIDENCE = Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/image-chain"
SPEC_REPOSITORY = "docker.io/library/pdf-t08-runtime"
PLATFORM_MANIFEST_DIGEST = (
    "sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0"
)
CONFIG_DIGEST = (
    "sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce"
)
PLATFORM_OS = "linux"
PLATFORM_ARCHITECTURE = "arm64"
MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"


class ImageIdentityError(ValueError):
    """The supplied runtime image identity cannot be bound to the fixed image."""


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _without_transport(value: str) -> tuple[str | None, str]:
    for scheme in ("docker-pullable://", "docker://", "containerd://"):
        if value.startswith(scheme):
            return scheme[:-3], value[len(scheme):]
    return None, value


@dataclass(frozen=True)
class ImageIdentityChain:
    repository: str
    registry_index_digest: str | None
    platform_manifest_digest: str
    config_digest: str
    os: str
    architecture: str
    cri_repo_digests: tuple[str, ...]
    cri_repo_tags: tuple[str, ...]
    cri_config_id: str
    docker_engine_id: str
    docker_repo_digests: tuple[str, ...]
    docker_repo_tags: tuple[str, ...]

    @property
    def spec_reference(self) -> str:
        return f"{self.repository}@{self.platform_manifest_digest}"

    def bind_runtime_image_id(
        self,
        image_id: str,
        *,
        spec_image: str,
        status_image: str | None,
        expected_os: str = PLATFORM_OS,
        expected_architecture: str = PLATFORM_ARCHITECTURE,
    ) -> str:
        if spec_image != self.spec_reference:
            raise ImageIdentityError("spec image is not the pinned repository manifest")
        if (self.os, self.architecture) != (expected_os, expected_architecture):
            raise ImageIdentityError("pinned image platform changed")

        transport, value = _without_transport(image_id)
        if "@" in value:
            repository, digest = value.rsplit("@", 1)
            if repository != self.repository:
                raise ImageIdentityError("runtime image repository changed")
            if digest != self.platform_manifest_digest:
                raise ImageIdentityError("runtime platform manifest digest changed")
            if f"{repository}@{digest}" not in self.cri_repo_digests:
                raise ImageIdentityError("runtime manifest is not bound by CRI evidence")
            return "repository-platform-manifest"

        if value.startswith("sha256:"):
            if transport not in {"docker", "containerd"}:
                raise ImageIdentityError("bare content digest cannot bind an image repository")
            if value != self.config_digest or value != self.cri_config_id:
                raise ImageIdentityError("runtime config content digest changed")
            if status_image not in self.cri_repo_tags:
                raise ImageIdentityError("config imageID is not bound to an inspected repository tag")
            return "runtime-config-content"

        raise ImageIdentityError("unsupported runtime imageID representation")


def load_pinned_image_identity(evidence: Path = EVIDENCE) -> ImageIdentityChain:
    manifest_raw = (evidence / "platform-manifest.json").read_bytes()
    config_raw = (evidence / "config.json").read_bytes()
    if _sha256(manifest_raw) != PLATFORM_MANIFEST_DIGEST:
        raise ImageIdentityError("platform manifest evidence digest changed")
    if _sha256(config_raw) != CONFIG_DIGEST:
        raise ImageIdentityError("config evidence digest changed")

    manifest = json.loads(manifest_raw)
    config = json.loads(config_raw)
    cri = json.loads((evidence / "cri-inspect.json").read_text())
    docker_rows = json.loads((evidence / "docker-inspect.json").read_text())
    if len(docker_rows) != 1:
        raise ImageIdentityError("exactly one Docker image inspection required")
    docker = docker_rows[0]
    status = cri["status"]
    image_spec = cri["info"]["imageSpec"]
    if manifest.get("mediaType") != MANIFEST_MEDIA_TYPE:
        raise ImageIdentityError("pinned descriptor is not a platform manifest")
    docker_descriptor = docker.get("Descriptor", {})
    if docker_descriptor.get("mediaType") != MANIFEST_MEDIA_TYPE:
        raise ImageIdentityError("Docker descriptor unexpectedly names an image index")
    if docker_descriptor.get("digest") != PLATFORM_MANIFEST_DIGEST:
        raise ImageIdentityError("Docker platform manifest digest changed")
    if docker.get("Id") != PLATFORM_MANIFEST_DIGEST:
        raise ImageIdentityError("Docker engine image ID changed")
    if (docker.get("Os"), docker.get("Architecture")) != (
        PLATFORM_OS,
        PLATFORM_ARCHITECTURE,
    ):
        raise ImageIdentityError("Docker image platform changed")
    docker_repo_tags = tuple(docker.get("RepoTags", ()))
    docker_repo_digests = tuple(docker.get("RepoDigests", ()))
    if "pdf-checkpoint-prototype:linux-v2" not in docker_repo_tags:
        raise ImageIdentityError("Docker local image tag changed")
    if not any(
        value.endswith("@" + PLATFORM_MANIFEST_DIGEST)
        for value in docker_repo_digests
    ):
        raise ImageIdentityError("Docker repo digest does not bind platform manifest")
    descriptor = manifest.get("config", {})
    if descriptor.get("mediaType") != CONFIG_MEDIA_TYPE:
        raise ImageIdentityError("manifest config media type changed")
    if descriptor.get("digest") != CONFIG_DIGEST:
        raise ImageIdentityError("manifest no longer points to pinned config")
    if (config.get("os"), config.get("architecture")) != (
        PLATFORM_OS,
        PLATFORM_ARCHITECTURE,
    ):
        raise ImageIdentityError("config platform changed")
    if (image_spec.get("os"), image_spec.get("architecture")) != (
        PLATFORM_OS,
        PLATFORM_ARCHITECTURE,
    ):
        raise ImageIdentityError("CRI platform metadata changed")
    if status.get("id") != CONFIG_DIGEST:
        raise ImageIdentityError("CRI config ID changed")
    repo_digests = tuple(status.get("repoDigests", ()))
    if f"{SPEC_REPOSITORY}@{PLATFORM_MANIFEST_DIGEST}" not in repo_digests:
        raise ImageIdentityError("CRI evidence does not bind the pinned repository manifest")

    return ImageIdentityChain(
        repository=SPEC_REPOSITORY,
        registry_index_digest=None,
        platform_manifest_digest=PLATFORM_MANIFEST_DIGEST,
        config_digest=CONFIG_DIGEST,
        os=PLATFORM_OS,
        architecture=PLATFORM_ARCHITECTURE,
        cri_repo_digests=repo_digests,
        cri_repo_tags=tuple(status.get("repoTags", ())),
        cri_config_id=status["id"],
        docker_engine_id=docker["Id"],
        docker_repo_digests=docker_repo_digests,
        docker_repo_tags=docker_repo_tags,
    )


PINNED_IMAGE_IDENTITY = load_pinned_image_identity()
