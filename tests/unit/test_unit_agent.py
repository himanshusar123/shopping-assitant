# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from app.agent import DISCOUNT_CODES, login, redeem_discount_code


class MockToolContext:
    def __init__(self, state=None):
        self.state = state if state is not None else {}


@pytest.fixture(autouse=True)
def reset_state():
    """Fixture to reset the in-memory DISCOUNT_CODES state before and after each test."""
    original_codes = {code: state.copy() for code, state in DISCOUNT_CODES.items()}
    yield
    for code, state in original_codes.items():
        DISCOUNT_CODES[code] = state.copy()


def test_login_success() -> None:
    """Verify that a registered user with correct secret credentials logs in successfully."""
    tool_context = MockToolContext()
    response = login(
        user_id="user123", secret_token="token123", tool_context=tool_context
    )

    assert response["status"] == "success"
    assert "Successfully authenticated" in response["message"]
    assert tool_context.state["authenticated_user_id"] == "user123"
    assert tool_context.state["failed_attempts"] == 0


def test_login_wrong_token() -> None:
    """Verify that login fails with wrong credentials."""
    tool_context = MockToolContext()
    response = login(
        user_id="user123", secret_token="wrong_token", tool_context=tool_context
    )

    assert response["status"] == "error"
    assert "Invalid credentials" in response["message"]
    assert "authenticated_user_id" not in tool_context.state


def test_login_unregistered_user() -> None:
    """Verify that login fails for unregistered user ID."""
    tool_context = MockToolContext()
    response = login(
        user_id="fake_user", secret_token="token123", tool_context=tool_context
    )

    assert response["status"] == "error"
    assert "Invalid credentials" in response["message"]


def test_redeem_without_login() -> None:
    """Verify that redemption fails if the user is not authenticated in their session state."""
    tool_context = MockToolContext()
    response = redeem_discount_code(code="WELCOME50", tool_context=tool_context)

    assert response["status"] == "error"
    assert "You must login first" in response["message"]


def test_redeem_discount_success() -> None:
    """Verify that a logged-in user can successfully redeem a valid, unused coupon code."""
    tool_context = MockToolContext(state={"authenticated_user_id": "user123"})
    response = redeem_discount_code(code="WELCOME50", tool_context=tool_context)

    assert response["status"] == "success"
    assert "successfully redeemed" in response["message"]
    assert response["discount"] == "50% off"
    assert DISCOUNT_CODES["WELCOME50"]["redeemed_by"] == "user123"


def test_redeem_discount_invalid_code() -> None:
    """Verify that entering an invalid code is rejected and increments the failed attempts counter."""
    tool_context = MockToolContext(
        state={"authenticated_user_id": "user123", "failed_attempts": 0}
    )
    response = redeem_discount_code(code="FAKECODE100", tool_context=tool_context)

    assert response["status"] == "error"
    assert "is not valid" in response["message"]
    assert tool_context.state["failed_attempts"] == 1


def test_redeem_discount_double_redemption() -> None:
    """Verify that a coupon code can only be redeemed once (single-use constraint)."""
    # First redemption succeeds
    tool_context1 = MockToolContext(state={"authenticated_user_id": "user123"})
    first_res = redeem_discount_code(code="SUMMER20", tool_context=tool_context1)
    assert first_res["status"] == "success"

    # Second redemption fails
    tool_context2 = MockToolContext(state={"authenticated_user_id": "buyer456"})
    second_res = redeem_discount_code(code="SUMMER20", tool_context=tool_context2)
    assert second_res["status"] == "error"
    assert "already been redeemed" in second_res["message"]


def test_redeem_discount_case_insensitivity_and_whitespace() -> None:
    """Verify that codes are cleaned (whitespace stripped, capitalized) before verification."""
    tool_context = MockToolContext(state={"authenticated_user_id": "user123"})
    response = redeem_discount_code(code="   summer20   ", tool_context=tool_context)

    assert response["status"] == "success"
    assert response["discount"] == "20% off"
    assert DISCOUNT_CODES["SUMMER20"]["redeemed_by"] == "user123"


def test_redeem_discount_lockout() -> None:
    """Verify that a session is locked from redemption after 3 or more failed attempts."""
    tool_context = MockToolContext(
        state={"authenticated_user_id": "user123", "failed_attempts": 3}
    )
    response = redeem_discount_code(code="WELCOME50", tool_context=tool_context)

    assert response["status"] == "error"
    assert "locked for coupon redemption" in response["message"]
