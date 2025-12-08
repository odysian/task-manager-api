from fastapi import status


def test_comment_lifecycle(authenticated_client):
    """
    Test the full lifecycle of a comment
    Create task then create comment and read comments
    Update comment then delete and assert comments are empty
    """

    # Phase 1: Create task and attached comment
    # ARRANGE
    task_response = authenticated_client.post(
        "/tasks",
        json={
            "title": "Comment test task",
            "description": "Test all the comment lifecycle endpoints",
            "priority": "high",
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    # ACT
    response = authenticated_client.post(
        f"/tasks/{task_id}/comments", json={"content": "This is a comment for a test"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_201_CREATED

    comment_id = response.json()["id"]

    # Verify comment created
    response = authenticated_client.get(f"/tasks/{task_id}/comments")
    data = response.json()
    assert len(data) == 1
    assert data[0]["content"] == "This is a comment for a test"

    # Phase 2:
    # ACT
    response = authenticated_client.patch(
        f"/comments/{comment_id}", json={"content": "This is the updated comment"}
    )

    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "This is the updated comment"

    # Phase 3:
    # ACT
    response = authenticated_client.delete(f"/comments/{comment_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify comment was removed
    response = authenticated_client.get(f"/tasks/{task_id}/comments")
    data = response.json()
    assert len(data) == 0
    assert data == []


def test_cannot_comment_on_others_tasks(client, create_user_and_token):
    """Test that users can't comment on other users' tasks"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    task_id = response.json()["id"]

    # ACT
    response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "Hacked!"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_read_others_comments(client, create_user_and_token):
    """Test that users can't read other users' comments"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    task_id = response.json()["id"]

    response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "This is a comment for a test"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.get(
        f"/tasks/{task_id}/comments",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_edit_others_comments(client, create_user_and_token):
    """Test that users can't read other users' comments"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    task_id = response.json()["id"]

    response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "This is a comment for a test"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    comment_id = response.json()["id"]

    assert response.status_code == status.HTTP_201_CREATED

    response = client.patch(
        f"/comments/{comment_id}",
        json={"content": "Hacked!"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_cannot_delete_others_comments(client, create_user_and_token):
    """Test that users can't read other users' comments"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    task_id = response.json()["id"]

    response = client.post(
        f"/tasks/{task_id}/comments",
        json={"content": "This is a comment for a test"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    comment_id = response.json()["id"]

    assert response.status_code == status.HTTP_201_CREATED

    response = client.delete(
        f"/comments/{comment_id}", headers={"Authorization": f"Bearer {user_b_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
