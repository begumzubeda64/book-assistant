"""Authorization helpers for user-owned resources.

Every user-owned resource (books, uploads, conversations, progress, jobs, saved
concepts, generated artifacts) must be checked against the authenticated
``user_id`` before it is read or mutated (security steering, requirement 1.3).
These helpers centralize that check so services fail closed and consistently.
"""

from __future__ import annotations

from src.core.errors import ForbiddenError, NotFoundError
from src.core.security.cognito import AuthenticatedUser


def assert_owner(
    user: AuthenticatedUser,
    resource_owner_id: str | None,
    *,
    resource: str = "resource",
) -> None:
    """Raise if ``user`` does not own the resource.

    A missing owner id is treated as not-found (rather than leaking existence),
    and a mismatch is forbidden.
    """
    if resource_owner_id is None:
        raise NotFoundError(f"The requested {resource} could not be found")
    if resource_owner_id != user.user_id:
        raise ForbiddenError(f"You do not have access to this {resource}")


def is_owner(user: AuthenticatedUser, resource_owner_id: str | None) -> bool:
    """Return True if ``user`` owns the resource."""
    return resource_owner_id is not None and resource_owner_id == user.user_id
