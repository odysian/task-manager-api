from fastapi import status


def test_create_task_successfully(authenticated_client):
    """Test that an authenticated user can create a task"""

    # ARRANGE
    task_data = {
        "title": "Write more tests",
        "description": "Test all the task endpoints",
        "priority": "high",
    }

    # ACT
    response = authenticated_client.post("/tasks", json=task_data)

    # ASSERT
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert response_data["title"] == "Write more tests"
    assert response_data["description"] == "Test all the task endpoints"
    assert response_data["priority"] == "high"
    assert response_data["completed"] == False
    assert "id" in response_data
    assert "created_at" in response_data
    assert "user_id" in response_data


def test_create_task_without_authentication(client):
    """Test that craeting a task without auth fails"""

    # ARRANGE
    task_data = {"title": "Unauthorized task", "priority": "low"}

    # ACT
    response = client.post("/tasks", json=task_data)

    # ASSERT
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_tasks_returns_only_user_tasks(authenticated_client):
    """Test that users only see their own tasks"""

    # ARRANGE - Create 2 tasks as authenticated user
    task1 = {"title": "My task 1", "priority": "high"}
    task2 = {"title": "My task 2", "priority": "low"}

    authenticated_client.post("/tasks", json=task1)
    authenticated_client.post("/tasks", json=task2)

    # ACT
    response = authenticated_client.get("/tasks")
    data = response.json()

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    tasks = data["tasks"]
    assert len(tasks) == 2
    assert tasks[0]["title"] == "My task 1"
    assert tasks[1]["title"] == "My task 2"


def test_get_tasks_empty_list(authenticated_client):
    """Test that getting tasks with no tasks returns empty list"""

    # ARRANGE - Don't create any tasks

    # ACT
    response = authenticated_client.get("/tasks")
    data = response.json()
    tasks = data["tasks"]

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    assert tasks == []


def test_get_single_task_successfully(authenticated_client):
    """Test getting a specific task by ID"""

    # ARRANGE - Create a task first
    create_response = authenticated_client.post(
        "/tasks", json={"title": "Specific task", "priority": "medium"}
    )
    task_id = create_response.json()["id"]

    # ACT
    response = authenticated_client.get(f"/tasks/{task_id}")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == task_id
    assert response.json()["title"] == "Specific task"


def test_get_nonexistent_task(authenticated_client):
    """Test that getting a non-existent task returns 404"""

    # ARRANGE
    nonexistent_id = 99999

    # ACT
    response = authenticated_client.get(f"/tasks/{nonexistent_id}")

    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_task_successfully(authenticated_client):
    """Test that a user can update their own task"""

    # ARRANGE - Create a task first
    create_response = authenticated_client.post(
        "/tasks",
        json={
            "title": "Original title",
            "description": "Original description",
            "priority": "low",
            "completed": False,
        },
    )
    task_id = create_response.json()["id"]

    # Prepare the update data
    update_data = {"title": "Updated title", "completed": True, "priority": "high"}

    # ACT
    response = authenticated_client.patch(f"/tasks/{task_id}", json=update_data)

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    updated_task = response.json()
    assert updated_task["title"] == "Updated title"
    assert updated_task["completed"] == True
    assert updated_task["priority"] == "high"
    assert updated_task["description"] == "Original description"  # Unchanged


def test_update_nonexistent_task(authenticated_client):
    """Test that updating a non-existent task returns 404"""

    # ARRANGE
    update_data = {"title": "New title"}

    # ACT
    response = authenticated_client.patch("/tasks/99999", json=update_data)

    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_task_successfully(authenticated_client):
    """Test that a user can delete their own task"""

    # ARRANGE - Create a task first
    create_response = authenticated_client.post(
        "/tasks", json={"title": "Original title", "priority": "low"}
    )
    task_id = create_response.json()["id"]

    # ACT
    response = authenticated_client.delete(f"/tasks/{task_id}")

    # ASSERT
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify task is actually deleted
    get_response = authenticated_client.get(f"/tasks/{task_id}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_nonexistent_task(authenticated_client):
    """Test that deletting a non-existent task returns 404"""

    # ACT
    response = authenticated_client.delete("/tasks/99999")

    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_user_cannot_get_another_users_task(client, create_user_and_token):
    """Test that a user cannot access another user's task"""

    # ARRANGE - Create User A with a task
    user_a_token = create_user_and_token("usera", "usera@test.com", "pass1234")
    user_b_token = create_user_and_token("userb", "userb@test.com", "pass5678")

    # User A creates a task
    task_response = client.post(
        "/tasks",
        json={"title": "User A's task", "priority": "high"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task_response.json()["id"]

    # ACT - User B tries to access User A's task
    response = client.get(
        f"/tasks/{task_id}", headers={"Authorization": f"Bearer {user_b_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_user_cannot_update_another_users_task(client, create_user_and_token):
    """Test that a user cannot update another user's task"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "pass1234")
    user_b_token = create_user_and_token("userb", "userb@test.com", "pass5678")

    # User A creates a task
    task_response = client.post(
        "/tasks",
        json={"title": "User A's task", "priority": "high"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task_response.json()["id"]

    # ACT - User B tries to update User A's task
    response = client.patch(
        f"/tasks/{task_id}",
        json={"title": "Hacked!"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )

    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_user_cannot_delete_another_users_task(client, create_user_and_token):
    """Test that a user cannot delete another user's task"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "pass1234")
    user_b_token = create_user_and_token("userb", "userb@test.com", "pass5678")

    # User A creates a task
    task_response = client.post(
        "/tasks",
        json={"title": "User A's task", "priority": "high"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task_response.json()["id"]

    # ACT - User B tries to delete User A's task
    response = client.delete(
        f"/tasks/{task_id}", headers={"Authorization": f"Bearer {user_b_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_task_missing_required_fields(authenticated_client):
    """Test that creating a task without required fields fails"""

    # ARRANGE - Missing title (required field)
    invalid_task = {"description": "No title provided", "priority": "high"}

    # ACT
    response = authenticated_client.post("/tasks", json=invalid_task)

    # ASSERT
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_task_invalid_priority(authenticated_client):
    """Test that creating a task with invalid priority fails"""

    # ARRANGE
    invalid_task = {
        "title": "Test task",
        "priority": "super-urgent",  # Not in ["low", "medium", "high"]
    }

    # ACT
    response = authenticated_client.post("/tasks", json=invalid_task)

    # ASSERT
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_task_empty_title(authenticated_client):
    """Test that creating a task with empty title fails"""

    # ARRANGE
    invalid_task = {"title": "", "priority": "low"}  # Empty string

    # ACT
    response = authenticated_client.post("/tasks", json=invalid_task)

    # ASSERT
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_task_invalid_priority(authenticated_client):
    """Test that updating a task with invalid priority fails"""

    # ARRANGE - Create a valid task first
    create_response = authenticated_client.post(
        "/tasks", json={"title": "Valid task", "priority": "low"}
    )
    task_id = create_response.json()["id"]

    # Try to update with invalid priority
    invalid_update = {"priority": "critical"}  # Not valid

    # ACT
    response = authenticated_client.patch(f"/tasks/{task_id}", json=invalid_update)

    # ASSERT
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_filter_tasks_by_completed(authenticated_client):
    """Test filtering tasks by completed status"""

    # ARRANGE - Create mix of completed and incomplete tasks
    create1 = authenticated_client.post(
        "/tasks",
        json={"title": "Incomplete task", "priority": "low", "completed": False},
    )
    print(f"\nCreated incomplete: {create1.json()}")

    create2 = authenticated_client.post(
        "/tasks",
        json={"title": "Completed task", "priority": "high", "completed": True},
    )
    print(f"Created completed: {create2.json()}")

    # ACT - Filter for completed tasks only
    response = authenticated_client.get("/tasks?completed=true")
    data = response.json()

    # ASSERT
    print(f"Filter response: {data}")
    assert response.status_code == status.HTTP_200_OK
    tasks = data["tasks"]
    assert len(tasks) == 1


def test_filter_tasks_by_priority(authenticated_client):
    """Test filtering tasks by priority"""

    # ARRANGE
    authenticated_client.post(
        "/tasks", json={"title": "Low priority", "priority": "low"}
    )
    authenticated_client.post(
        "/tasks", json={"title": "High priority", "priority": "high"}
    )
    authenticated_client.post(
        "/tasks", json={"title": "Another high", "priority": "high"}
    )

    # ACT
    response = authenticated_client.get("/tasks?priority=high")
    data = response.json()

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    tasks = data["tasks"]
    assert len(tasks) == 2
    assert all(task["priority"] == "high" for task in tasks)


def test_search_tasks_by_text(authenticated_client):
    """Test searching tasks by text in title or description"""

    # ARRANGE
    authenticated_client.post(
        "/tasks",
        json={
            "title": "Buy groceries",
            "description": "Milk and eggs",
            "priority": "low",
        },
    )
    authenticated_client.post(
        "/tasks",
        json={
            "title": "Write report",
            "description": "Quarterly financial report",
            "priority": "high",
        },
    )

    # ACT - Search for "report"
    response = authenticated_client.get("/tasks?search=report")
    data = response.json()

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    tasks = data["tasks"]
    assert len(tasks) == 1
    assert (
        "report" in tasks[0]["title"].lower()
        or "report" in tasks[0]["description"].lower()
    )


def test_sort_tasks_by_priority(authenticated_client):
    """Test sorting tasks by priority"""

    # ARRANGE - Create tasks in random order
    authenticated_client.post("/tasks", json={"title": "Low task", "priority": "low"})
    authenticated_client.post("/tasks", json={"title": "High task", "priority": "high"})
    authenticated_client.post(
        "/tasks", json={"title": "Medium task", "priority": "medium"}
    )

    # ACT - Sort by priority
    response = authenticated_client.get("/tasks?sort_by=priority&sort_order=asc")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    tasks = response.json()
    # Check order: low, medium, high (alphabetically if your sort works that way)
    # Or adjust based on how your API actually sorts priorities


def test_pagination(authenticated_client):
    """Test pagination with skip and limit"""

    # ARRANGE - Create 5 tasks
    for i in range(5):
        authenticated_client.post(
            "/tasks", json={"title": f"Task {i+1}", "priority": "low"}
        )

    # ACT - Get first 2 tasks
    response = authenticated_client.get("/tasks?skip=0&limit=2")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    tasks = data["tasks"]
    assert len(tasks) == 2

    # ACT - Get next 2 tasks
    response = authenticated_client.get("/tasks?skip=2&limit=2")
    data = response.json()

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    tasks = data["tasks"]
    assert len(tasks) == 2


def test_combine_multiple_filters(authenticated_client):
    """Test combining multiple query parameters"""

    # ARRANGE
    authenticated_client.post(
        "/tasks",
        json={"title": "Important work", "priority": "high", "completed": False},
    )
    authenticated_client.post(
        "/tasks", json={"title": "Done work", "priority": "high", "completed": True}
    )
    authenticated_client.post(
        "/tasks",
        json={"title": "Low priority work", "priority": "low", "completed": False},
    )

    # ACT - Filter: high priority AND not completed
    response = authenticated_client.get("/tasks?priority=high&completed=false")
    data = response.json()

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    tasks = data["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Important work"


def test_get_stats_with_tasks(authenticated_client):
    """Test getting task statistics"""

    # ARRANGE - Create a variety of tasks
    authenticated_client.post(
        "/tasks", json={"title": "Task 1", "priority": "high", "completed": True}
    )
    authenticated_client.post(
        "/tasks", json={"title": "Task 2", "priority": "low", "completed": False}
    )
    authenticated_client.post(
        "/tasks", json={"title": "Task 3", "priority": "high", "completed": False}
    )

    # ACT
    response = authenticated_client.get("/tasks/stats")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    stats = response.json()
    assert stats["total"] == 3
    assert stats["completed"] == 1
    assert stats["incomplete"] == 2
    assert stats["by_priority"]["high"] == 2
    assert stats["by_priority"]["low"] == 1


def test_get_stats_empty(authenticated_client):
    """Test stats endpoint with no tasks"""

    # ARRANGE - No tasks created

    # ACT
    response = authenticated_client.get("/tasks/stats")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    stats = response.json()
    assert stats["total"] == 0
    assert stats["completed"] == 0
    assert stats["incomplete"] == 0


def test_stats_only_shows_user_tasks(client, create_user_and_token):
    """Test that stats only count the current user's tasks"""

    # ARRANGE - Create two users with different tasks
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    # User A creates 3 tasks
    for i in range(3):
        client.post(
            "/tasks",
            json={"title": f"User A task {i}", "priority": "low"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

    # User B creates 2 tasks
    for i in range(2):
        client.post(
            "/tasks",
            json={"title": f"User B task {i}", "priority": "high"},
            headers={"Authorization": f"Bearer {user_b_token}"},
        )

    # ACT - Get stats as User A
    response = client.get(
        "/tasks/stats", headers={"Authorization": f"Bearer {user_a_token}"}
    )

    # ASSERT - Should only see User A's tasks
    assert response.status_code == status.HTTP_200_OK
    stats = response.json()
    assert stats["total"] == 3  # Not 5!


def test_bulk_update_tasks(authenticated_client):
    """Test updating multiple tasks at once"""

    # ARRANGE - Create 3 tasks
    task_ids = []
    for i in range(3):
        response = authenticated_client.post(
            "/tasks",
            json={"title": f"Task {i+1}", "priority": "low", "completed": False},
        )
        task_ids.append(response.json()["id"])

    # Prepare bulk update
    bulk_update = {
        "task_ids": task_ids,
        "updates": {"completed": True, "priority": "high"},
    }

    # ACT
    response = authenticated_client.patch("/tasks/bulk", json=bulk_update)

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    # Your endpoint returns a LIST of updated tasks
    updated_tasks = response.json()
    assert len(updated_tasks) == 3  # Check we got 3 tasks back

    # Verify each task was updated
    for task in updated_tasks:
        assert task["completed"] == True
        assert task["priority"] == "high"


def test_bulk_update_with_invalid_id_fails(client, create_user_and_token):
    """Test that bulk update fails if any task ID is invalid"""

    # ARRANGE
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    # User A creates 2 tasks
    user_a_task_ids = []
    for i in range(2):
        response = client.post(
            "/tasks",
            json={"title": f"User A task {i}", "priority": "low"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        user_a_task_ids.append(response.json()["id"])

    # User B creates a task
    user_b_response = client.post(
        "/tasks",
        json={"title": "User B task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    user_b_task_id = user_b_response.json()["id"]

    # ACT - User A tries to bulk update including User B's task
    bulk_update = {
        "task_ids": user_a_task_ids + [user_b_task_id],
        "updates": {"completed": True},
    }

    response = client.patch(
        "/tasks/bulk",
        json=bulk_update,
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    # ASSERT - Should fail because one task doesn't belong to User A
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Verify NO tasks were updated (all-or-nothing)
    for task_id in user_a_task_ids:
        task = client.get(
            f"/tasks/{task_id}", headers={"Authorization": f"Bearer {user_a_token}"}
        ).json()
        assert task["completed"] == False  # Still incomplete

    # --- SCENARIO 2: Non-Existent ID (404) ---
    # User A treis to update a fake ID
    fake_id = 99999
    bulk_update_404 = {
        "task_ids": user_a_task_ids + [fake_id],
        "updates": {"completed": True},
    }

    response_404 = client.patch(
        "/tasks/bulk",
        json=bulk_update_404,
        headers={"Authorization": f"Bearer {user_a_token}"},
    )

    # print("\nDEBUG RESPONSE:", response_404.json())

    assert response_404.status_code == status.HTTP_404_NOT_FOUND
    assert str(fake_id) in response_404.json()["detail"]


def test_bulk_update_empty_list(authenticated_client):
    """Test bulk update with empty task list returns validation error"""

    # ARRANGE
    bulk_update = {"task_ids": [], "updates": {"completed": True}}

    # ACT
    response = authenticated_client.patch("/tasks/bulk", json=bulk_update)

    # ASSERT - Empty list should be rejected
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_add_tag_to_task(authenticated_client):
    """Test adding a tag to a task"""

    # ARRANGE - Create a task
    task_response = authenticated_client.post(
        "/tasks", json={"title": "Task with tags", "priority": "low"}
    )
    task_id = task_response.json()["id"]

    # ACT - Add a tag (send as a list, not a dict!)
    response = authenticated_client.post(
        f"/tasks/{task_id}/tags",
        json=["urgent"],  # ← Changed from {"tag": "urgent"} to ["urgent"]
    )

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    # Verify tag was added
    task = authenticated_client.get(f"/tasks/{task_id}").json()
    assert "urgent" in task["tags"]


def test_add_duplicate_tag(authenticated_client):
    """Test that adding the same tag twice doesn't duplicate it"""

    # ARRANGE - Create task and add a tag
    task_response = authenticated_client.post(
        "/tasks", json={"title": "Task", "priority": "low"}
    )
    task_id = task_response.json()["id"]

    authenticated_client.post(f"/tasks/{task_id}/tags", json=["urgent"])

    # ACT - Try to add the same tag again
    response = authenticated_client.post(f"/tasks/{task_id}/tags", json=["urgent"])

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    # Verify no duplicate
    task = authenticated_client.get(f"/tasks/{task_id}").json()
    assert task["tags"].count("urgent") == 1


def test_remove_tag_from_task(authenticated_client):
    """Test removing a tag from a task"""

    # ARRANGE - Create task with a tag
    task_response = authenticated_client.post(
        "/tasks",
        json={"title": "Task", "priority": "low", "tags": ["urgent", "important"]},
    )
    task_id = task_response.json()["id"]

    # ACT - Remove a tag
    response = authenticated_client.delete(f"/tasks/{task_id}/tags/urgent")

    # ASSERT
    assert response.status_code == status.HTTP_200_OK

    # Verify tag was removed
    task = authenticated_client.get(f"/tasks/{task_id}").json()
    assert "urgent" not in task["tags"]
    assert "important" in task["tags"]  # Other tag still there


def test_remove_nonexistent_tag(authenticated_client):
    """Test removing a tag that doesn't exist"""

    # ARRANGE - Create task without tags
    task_response = authenticated_client.post(
        "/tasks", json={"title": "Task", "priority": "low"}
    )
    task_id = task_response.json()["id"]

    # ACT - Try to remove non-existent tag
    response = authenticated_client.delete(f"/tasks/{task_id}/tags/nonexistent")

    # ASSERT
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_add_tag_to_other_users_task(client, create_user_and_token):
    """Test that users cannot add tags to other users' tasks"""

    # ARRANGE - User A creates a task
    user_a_token = create_user_and_token("usera", "usera@test.com", "password123")
    user_b_token = create_user_and_token("userb", "userb@test.com", "password456")

    task_response = client.post(
        "/tasks",
        json={"title": "User A task", "priority": "low"},
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    task_id = task_response.json()["id"]

    # ACT - User B tries to add a tag
    response = client.post(
        f"/tasks/{task_id}/tags",
        json=["hacked"],
        headers={"Authorization": f"Bearer {user_b_token}"},
    )

    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN
