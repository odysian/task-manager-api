from fastapi import status


def test_share_task_success(client, create_user_and_token):
    "Test that a task can be shared successfully"

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
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    # ASSERT
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["shared_with_username"] == "userb"
    assert data["permission"] == "view"


# Share with yourself test
def test_cannot_share_with_self(authenticated_client):
    """Test that user can't share their task with themself"""

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
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "testuser", "permission": "view"},
    )
    # ASSERT
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Share with nonexistent user test
def test_share_with_nonexistent_user(authenticated_client):
    """Test that user can't share their task with themself"""

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
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "fakeuser", "permission": "view"},
    )
    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND


# Double dip - unique constraint: share twice with same person
def test_share_task_twice(client, create_user_and_token):
    "Test that a task cannot be shared twice"

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
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["shared_with_username"] == "userb"
    assert data["permission"] == "view"

    response = client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    # ASSERT
    assert response.status_code == status.HTTP_409_CONFLICT


# User B tries to share User A's task with peeped credentials
def test_share_unowned_task(client, create_user_and_token):
    "Test that non-owners cannot share tasks"

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
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN


# Unsharing works test
def test_unshare_task(client, create_user_and_token):
    "Test that task can be unshared"

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
    share_response = client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    data = share_response.json()
    user_b_username = data["shared_with_username"]
    response = client.delete(
        f"/tasks/{task_id}/share/{user_b_username}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    print(share_response)
    print(data)
    print(response)
    # ASSERT
    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_update_share_permission(client, create_user_and_token):
    """Test that share permissions can be updated"""

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

    share_response = client.post(
        f"/tasks/{task_id}/share",
        json={"shared_with_username": "userb", "permission": "view"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    data = share_response.json()
    user_b_username = data["shared_with_username"]

    # ACT
    update_response = client.put(
        f"/tasks/{task_id}/share/{user_b_username}",
        json={"permission": "edit"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    # ASSERT
    assert update_response.status_code == status.HTTP_200_OK
    data = update_response.json()
    assert data["permission"] == "edit"
