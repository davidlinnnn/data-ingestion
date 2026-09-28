# Worker image identity contract

The pinned worker image reference is
`docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
That digest identifies the image manifest. The reviewed local image content ID
is `sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce`.

The runner requires the Pod spec to retain the exact pinned manifest reference.
For `containerStatuses[].imageID`, it accepts the content ID by itself and the
same content ID wrapped in common CRI forms such as `containerd://<digest>`,
`docker-pullable://<repository>@<digest>`, or `<repository>@<digest>`. Removing
the transport/repository wrapper must still yield the reviewed content ID. The
manifest digest is not interchangeable with the content ID.

The failed first window did not save its Pod status snapshot. Existing frozen
inventory demonstrates the plain content-ID form, but it does not establish the
value returned for the failed Pod. The wrapped forms above are compatibility
cases verified by local tests, not observations attributed to that Pod. Its
readiness root cause therefore remains unknown. The contract is an offline
compatibility correction, not a post-hoc diagnosis.
