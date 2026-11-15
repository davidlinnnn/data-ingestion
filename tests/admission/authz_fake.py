"""An Authorizer for PEP tests (#113); never selectable in a deployment's configuration."""

from kp_admission.authz import Action, Decision, Outcome, Reason, Ref, new_decision


class FakeAuthorizer:
    """Every call returns `outcome`. A deny carries `reason`; `list_resources` returns
    `resource_ids`, `page_size` at a time (all in one page without it), or nothing visible when
    the outcome is deny. `pages` gives the pages themselves instead, so one can be empty with
    more to follow."""

    decided_by = "fake/model-1"

    def __init__(
        self,
        outcome: Outcome = "allow",
        reason: Reason = "no_relation",
        resource_ids: tuple[str, ...] = (),
        page_size: int | None = None,
        pages: tuple[tuple[str, ...], ...] | None = None,
    ) -> None:
        self.outcome: Outcome = outcome
        self.reason: Reason = reason
        self.resource_ids = resource_ids
        self.page_size = page_size
        self.pages = pages

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
        return new_decision(self.outcome, *args, reason=reason)

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
            return new_decision("unavailable", *args)
        ids = list(self.resource_ids) if self.outcome == "allow" else []
        size = self.page_size or len(ids) or 1
        pages = [ids[start : start + size] for start in range(0, len(ids), size)] or [[]]
        if self.pages is not None and self.outcome == "allow":
            pages = [list(page) for page in self.pages]
        page = int(cursor or 0)
        more = str(page + 1) if page + 1 < len(pages) else None
        return new_decision("allow", *args, resource_ids=pages[page], next_cursor=more)
