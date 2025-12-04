import pytest
from fastapi import status
from unittest.mock import patch, MagicMock

# --- FIXTURE: Mock S3 Client ---
@pytest.fixture
def mock_s3():
    """
    Replaces the actual AWS connection with a 'spy' object.
    """
    # Verify this string matches your file structure!
    with patch("routers.files.s3_client") as mock:
        yield mock

# --- Editor Can Upload ---
def test_editor_can_upload_file(client, create_user_and_token, mock_s3):
    """Test that a shared user with EDIT permissions CAN upload"""
    
    # ARRANGE
    alice_token = create_user_and_token("alice", "alice@test.com", "password")
    bob_token = create_user_and_token("bob", "bob@test.com", "password")

    # 1. Setup Task & Share
    task = client.post("/tasks", 
        json={"title": "File Task", "priority": "low"},
        headers={"Authorization": f"Bearer {alice_token}"}
    ).json()
    task_id = task["id"]

    client.post(f"/tasks/{task_id}/share",
        json={"shared_with_username": "bob", "permission": "edit"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    # 2. Fake File
    files_payload = {"file": ("test.txt", b"fake content", "text/plain")}

    # ACT
    response = client.post(
        f"/tasks/{task_id}/files",
        files=files_payload,
        headers={"Authorization": f"Bearer {bob_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_201_CREATED
    mock_s3.put_object.assert_called_once() 


# --- Viewer Cannot Upload ---
def test_viewer_cannot_upload_file(client, create_user_and_token, mock_s3):
    """Test that a shared user with VIEW permissions CANNOT upload"""
    
    # ARRANGE
    alice_token = create_user_and_token("alice", "alice@test.com", "password")
    charlie_token = create_user_and_token("charlie", "charlie@test.com", "password")

    # 1. Setup Task & Share
    task = client.post("/tasks", 
        json={"title": "View Task", "priority": "low"},
        headers={"Authorization": f"Bearer {alice_token}"}
    ).json()
    task_id = task["id"]
    
    client.post(f"/tasks/{task_id}/share",
        json={"shared_with_username": "charlie", "permission": "view"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    files_payload = {"file": ("test.txt", b"content", "text/plain")}

    # ACT
    response = client.post(
        f"/tasks/{task_id}/files",
        files=files_payload,
        headers={"Authorization": f"Bearer {charlie_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_403_FORBIDDEN
    mock_s3.put_object.assert_not_called()


# --- Viewer Can Download ---
def test_viewer_can_download_file(client, create_user_and_token, mock_s3):
    """Test that a viewer can download a file"""
    
    # ARRANGE
    alice_token = create_user_and_token("alice", "alice@test.com", "password")
    charlie_token = create_user_and_token("charlie", "charlie@test.com", "password")

    # 1. Setup Task & Share
    task = client.post("/tasks", 
        json={"title": "Download Task", "priority": "low"},
        headers={"Authorization": f"Bearer {alice_token}"}
    ).json()
    task_id = task["id"]

    client.post(f"/tasks/{task_id}/share",
        json={"shared_with_username": "charlie", "permission": "view"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    # 2. Alice uploads a file (to populate DB)
    files_payload = {"file": ("alice_file.txt", b"real content", "text/plain")}
    upload_res = client.post(f"/tasks/{task_id}/files", files=files_payload, headers={"Authorization": f"Bearer {alice_token}"})
    file_id = upload_res.json()["id"]

    # 3. Setup Mock Return Value
    mock_stream = MagicMock()
    mock_stream.read.return_value = b"real content"
    mock_s3.get_object.return_value = {"Body": mock_stream}

    # ACT (Using the NEW clean URL)
    response = client.get(
        f"/files/{file_id}", # <--- Look! No double /files/files/
        headers={"Authorization": f"Bearer {charlie_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"real content"


# --- Editor Can Delete ---
def test_editor_can_delete_file(client, create_user_and_token, mock_s3):
    """Test that an editor can delete a file"""
    
    # ARRANGE
    alice_token = create_user_and_token("alice", "alice@test.com", "password")
    bob_token = create_user_and_token("bob", "bob@test.com", "password")

    # 1. Setup Task & Share
    task = client.post("/tasks", 
        json={"title": "Delete Task", "priority": "low"},
        headers={"Authorization": f"Bearer {alice_token}"}
    ).json()
    task_id = task["id"]

    client.post(f"/tasks/{task_id}/share",
        json={"shared_with_username": "bob", "permission": "edit"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    # 2. Upload file
    files_payload = {"file": ("todelete.txt", b"trash", "text/plain")}
    upload_res = client.post(f"/tasks/{task_id}/files", files=files_payload, headers={"Authorization": f"Bearer {alice_token}"})
    file_id = upload_res.json()["id"]

    # ACT (Using the NEW clean URL)
    response = client.delete(
        f"/files/{file_id}", # <--- Clean URL
        headers={"Authorization": f"Bearer {bob_token}"}
    )

    # ASSERT
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_s3.delete_object.assert_called_once()