from unittest.mock import MagicMock, patch

import pytest
from fastapi import status


@pytest.fixture
def mock_sns():
    """
    Replaces the actual AWS connection with a 'spy' object.
    """
    # Verify this string matches your file structure!
    with patch("notifications.sns_client") as mock:
        mock.publish.return_value = {"MessageId": "test-123"}
        mock.subscribe.return_value = {"SubscriptionArn": "arn:test:123"}
        yield mock


def test_notification_preferences(authenticated_client):
    """
    Test that default notification preferences are set
    and that users can update them
    """
    response = authenticated_client.get("/notifications/preferences")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    print(data)
    assert data["email_enabled"] is True
    assert data["task_shared_with_me"] is True
    assert data["email_verified"] is False

    update = authenticated_client.patch(
        "/notifications/preferences", json={"task_shared_with_me": False}
    )
    assert update.status_code == status.HTTP_200_OK
    assert update.json()["task_shared_with_me"] is False

    response = response = authenticated_client.get("/notifications/preferences")
    data = response.json()
    assert data["task_shared_with_me"] == False
    assert data["email_enabled"] is True


def test_notification_lifecycle(client, create_user_and_token, mock_sns):
    # Bob's email is verified
    # Alice shares task with bob
    # Assert that sns_client is called when sharing task

    user_a_token = create_user_and_token("Alice", "usera@test.com", "password123")
    user_b_token = create_user_and_token("Bob", "userb@test.com", "password456")

    # Alice creates task
    response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    task_id = response.json()["id"]

    # Bob verifies email
    verify_response = client.post(
        "notifications/verify", headers={"Authorization": f"Bearer {user_b_token}"}
    )
    assert verify_response.status_code == status.HTTP_200_OK

    # Alice shares task with Bob
    response = client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "Bob", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    mock_sns.publish.assert_called_once()


def test_comment_notification(client, create_user_and_token, mock_sns):
    """Test that task owner gets notified when someone comments"""
    # ARRANGE
    user_a_token = create_user_and_token("Alice", "usera@test.com", "password123")
    user_b_token = create_user_and_token("Bob", "userb@test.com", "password456")

    # Alice verifies email
    client.post(
        "notifications/verify", headers={"Authorization": f"Bearer {user_a_token}"}
    )

    # Alice creates task
    task = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task.json()["id"]

    # Alice shares task with Bob
    client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "Bob", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    # Reset mock to ignore the share notification
    mock_sns.reset_mock()

    # ACT: Bob comments
    client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "This is a comment for a test"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )

    # ASSERT
    mock_sns.publish.assert_called_once()

    # Verify content
    call_args = mock_sns.publish.call_args
    assert "New Comment" in call_args.kwargs["Subject"]
    assert "Bob" in call_args.kwargs["Message"]


def test_completed_notification(client, create_user_and_token, mock_sns):
    """Test that task owner gets notified when someone marks their task completed"""
    # ARRANGE
    user_a_token = create_user_and_token("Alice", "usera@test.com", "password123")
    user_b_token = create_user_and_token("Bob", "userb@test.com", "password456")

    # Alice verifies email
    client.post(
        "notifications/verify", headers={"Authorization": f"Bearer {user_a_token}"}
    )

    # Alice creates task
    task = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task.json()["id"]

    # Alice shares task with Bob
    client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "Bob", "permission": "edit"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    # Reset mock to ignore the share notification
    mock_sns.reset_mock()

    # ACT: Bob marks Alice's task as completed
    response = client.patch(
        f"/tasks/{task_id}",
        json={"completed": True},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    # ASSERT
    mock_sns.publish.assert_called_once()

    # Verify content
    call_args = mock_sns.publish.call_args
    assert "Task Completed" in call_args.kwargs["Subject"]
    assert "Bob" in call_args.kwargs["Message"]


def test_notification_guards(client, create_user_and_token, mock_sns):
    """Test that endpoints respect preferences"""
    # ARRANGE
    user_a_token = create_user_and_token("Alice", "usera@test.com", "password123")
    user_b_token = create_user_and_token("Bob", "userb@test.com", "password456")

    # Alice creates three tasks
    task1 = client.post(
        "/tasks",
        json={"title": "User A task 1", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task2 = client.post(
        "/tasks",
        json={"title": "User A task 2", "priority": "medium"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task3 = client.post(
        "/tasks",
        json={"title": "User A task 3", "priority": "high"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task1_id = task1.json()["id"]
    task2_id = task2.json()["id"]
    task3_id = task3.json()["id"]

    # SCENARIO 1: Unverified email
    # Alice shares task with Bob
    client.post(
        f"/tasks/{task1_id}/share",
        json={"shared_with_username": "Bob", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    mock_sns.publish.assert_not_called()
    mock_sns.reset_mock()

    # SCENARIO 2: Verified but sharing preference disabled
    # Bob verifies but disables sharing notification
    client.post(
        "notifications/verify", headers={"Authorization": f"Bearer {user_b_token}"}
    )
    client.patch(
        "/notifications/preferences",
        json={"task_shared_with_me": False},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )

    # Alice shares task with Bob
    client.post(
        f"/tasks/{task2_id}/share",
        json={"shared_with_username": "Bob", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    mock_sns.publish.assert_not_called()
    mock_sns.reset_mock()

    # SCENARIO 3: Master Switch
    # Bob enables sharing notification but disables master switch
    client.patch(
        "/notifications/preferences",
        json={"task_shared_with_me": True, "email_enabled": False},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    # Alice shares task with Bob
    client.post(
        f"/tasks/{task3_id}/share",
        json={"shared_with_username": "Bob", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    mock_sns.publish.assert_not_called()
