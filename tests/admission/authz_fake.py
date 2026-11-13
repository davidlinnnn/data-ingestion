"""An Authorizer for PEP tests (#113); never selectable in a deployment's configuration."""

from kp_admission.authz import Action, Decision, Outcome, Reason, Ref, decision


class FakeAuthorizer:
    """Every call returns `outcome`. A deny carries `reason`; `list_resources` returns
    `resource_ids` in one page, or nothing visible when the outcome is deny."""

    decided_by = "fake/model-1"

    def __init__(
        self,
        outcome: Outcome = "allow",
        reason: Reason = "no_relation",
        resource_ids: tuple[str, ...] = (),
    ) -> None:
        self.outcome: Outcome = outcome
        self.reason: Reason = reason
        self.resource_ids = resource_ids

    async def check(
        self,
        subject: Ref,
        action: Action,
        resource_id: str,
        *,
        actor: Ref | None = None,
        trace_id: str,
    ) -> Decision:
        reason = self.reason if self.outcome == "deny" else None
        args = (self.decided_by, subject, action, resource_id, actor, trace_id)
        return decision(self.outcome, *args, reason=reason)

    async def list_resources(
        self,
        subject: Ref,
        action: Action,
        *,
        actor: Ref | None = None,
        cursor: str | None = None,
        trace_id: str,
    ) -> Decision:
        args = (self.decided_by, subject, action, None, actor, trace_id)
        if self.outcome == "unavailable":
            return decision("unavailable", *args)
        ids = list(self.resource_ids) if self.outcome == "allow" else []
        return decision("allow", *args, resource_ids=ids)
