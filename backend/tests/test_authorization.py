"""Tests for the user-owned-resource authorization helpers."""

from __future__ import annotations

import pytest
from src.core.errors import ForbiddenError, NotFoundError
from src.core.security.authorization import assert_owner, is_owner
from src.core.security.cognito import AuthenticatedUser

USER = AuthenticatedUser(user_id="owner-1")


def test_assert_owner_allows_owner() -> None:
    assert_owner(USER, "owner-1", resource="book")  # no raise


def test_assert_owner_denies_other_user() -> None:
    with pytest.raises(ForbiddenError):
        assert_owner(USER, "someone-else", resource="book")


def test_assert_owner_missing_owner_is_not_found() -> None:
    with pytest.raises(NotFoundError):
        assert_owner(USER, None, resource="book")


def test_is_owner() -> None:
    assert is_owner(USER, "owner-1") is True
    assert is_owner(USER, "other") is False
    assert is_owner(USER, None) is False
