"""Two-step confirmation for destructive actions (delete, shutdown, ...).

NL skills can't pop a blocking prompt (it would hang the web HUD), so the
first call stores the pending action and asks; "yes" executes, "no" cancels.
Pending actions expire after TTL seconds. Explicitly typed Router commands
(e.g. `pc shutdown`) execute immediately - typing it IS the confirmation.
"""

import time

from ..utils import storage

TTL = 120
YES = {"yes", "yes please", "yes do it", "confirm", "do it", "go ahead",
       "proceed", "sure", "ok do it", "delete it", "shut it down"}
NO = {"no", "cancel", "stop", "never mind", "nevermind", "don't", "dont"}


def request(action, label, payload):
    storage.save("pending_confirm", {"action": action, "label": label,
                                     "payload": payload, "ts": time.time()})
    return f"{label} Are you sure? Say 'yes' to confirm."


def check(text, actions=None):
    """Returns the pending dict on 'yes', {'cancelled': True} on 'no',
    or None when there is nothing pending / no decision yet / the pending
    action is not in `actions` (another skill owns it - left untouched)."""
    p = storage.load("pending_confirm", None)
    if not p or not isinstance(p, dict) or "action" not in p:
        return None
    if actions is not None and p.get("action") not in actions:
        return None
    if time.time() - p.get("ts", 0) > TTL:
        storage.save("pending_confirm", {})
        return None
    t = (text or "").lower().strip().strip("?.!")
    if t in YES:
        storage.save("pending_confirm", {})
        return p
    if t in NO:
        storage.save("pending_confirm", {})
        return {"cancelled": True}
    return None
