from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

import db_models


@pytest.fixture
def mock_ses():
    """Mock SES Client for email sending."""
    with patch("services.notifications.ses_client") as mock:
        mock.send_email.return_value = {"MessageId": "test-123"}
        yield mock


def test_register_new_user(client):
    """Test that a new user can successfully register"""

    # ARRANGE
    user_data = {
        "username": "chris",
        "email": "chris@example.com",
        "password": "secure_password123",
    }

    # ACT
    response = client.post("/auth/register", json=user_data)

    # ASSERT
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert response_data["username"] == "chris"
    assert response_data["email"] == "chris@example.com"
    assert "id" in response_data
    assert "hashed_password" not in response_data  # Security: don't return password
    assert "password" not in response_data


def test_register_duplicate_username(client, test_user):
    """Test that registering with an existing username fails"""

    # ARRANGE
    # test_user fixture already created user with username "testuser"
    duplicate_user = {
        "username": "testuser",  # Same username
        "email": "different@example.com",  # Different email
        "password": "password123",
    }

    # ACT
    response = client.post("/auth/register", json=duplicate_user)

    # ASSERT
    assert response.status_code == status.HTTP_409_CONFLICT


def test_login_success(client, test_user):
    """Test that a user can login with correct credentials"""

    # ARRANGE
    # test_user fixture created a user, we have their credentials
    login_data = {"username": test_user["username"], "password": test_user["password"]}

    # ACT
    response = client.post("/auth/login", json=login_data)

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    response_data = response.json()
    assert "access_token" in response_data
    assert response_data["token_type"] == "bearer"


def test_login_invalid_password(client, test_user):
    """Test that login fails with wrong password"""

    # ARRANGE
    login_data = {"username": test_user["username"], "password": "wrong_password"}

    # ACT
    response = client.post("/auth/login", json=login_data)

    # ASSERT
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_password_success(authenticated_client):
    """Test successful password change"""

    response = authenticated_client.patch(
        "/users/me/change-password",
        json={
            "current_password": "testpass123",  # Original password
            "new_password": "newpassword123",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"

    # Verify old password no longer works
    login_response = authenticated_client.post(
        "/auth/login", json={"username": "testuser", "password": "password123"}
    )
    assert login_response.status_code == 401

    # Verify new password works
    login_response = authenticated_client.post(
        "/auth/login", json={"username": "testuser", "password": "newpassword123"}
    )
    assert login_response.status_code == 200


def test_password_reset_lifecycle(client, create_user_and_token, mock_ses, db_session):
    """Test that password reset request sends"""

    test_user_token = create_user_and_token("Alice", "usera@test.com", "password123")

    reset_request_data = {"email": "usera@test.com"}
    response = client.post("/auth/password-reset/request", json=reset_request_data)
    assert response.status_code == 200
    assert response.json()["message"] == "If email exists, password reset sent"
    mock_ses.send_email.assert_called_once()

    user_data = (
        db_session.query(db_models.User)
        .filter(db_models.User.email == "usera@test.com")
        .first()
    )
    reset_token = user_data.password_reset_token

    response = client.post(
        "/auth/password-reset/verify",
        json={"token": reset_token, "new_password": "password456"},
    )
    assert response.status_code == 200
    assert (
        response.json()["message"]
        == "Password updated successfully. You can now log in with your new password."
    )
