from . import config


def started_before(a_start, a_uuid, b_start, b_uuid, eps=config.TIE_EPS):
    """Return True if node A launched before node B (ties broken by uuid)."""
    if abs(a_start - b_start) > eps:
        return a_start < b_start
    return a_uuid < b_uuid


def member_id_of(uuid, members):
    """Member number (1-based) of uuid in the roster, or 0 if not in it."""
    members = list(members)
    return members.index(uuid) + 1 if uuid in members else 0
