"""
Custom exceptions for the Task Manager API.
These exceptions represent specific logic errors
that can be converted to appropriate HTTP responses.
"""


class TaskNotFoundError(Exception):
    """Raised when a task doesn't exist or user doesnt have access to it"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.message = f"Task with ID {task_id} not found"
        super().__init__(self.message)


class UnauthorizedTaskAccessError(Exception):
    """Raised when user tries to access a task that doesn't belong to them"""

    def __init__(self, task_id: int, user_id: int):
        self.task_id = task_id
        self.user_id = user_id
        self.message = f"User {user_id} is not authorized to access task {task_id}"
        super().__init__(self.message)


class TagNotFoundError(Exception):
    """Raised when trying to remove a tag that doesn't exist on a task"""

    def __init__(self, task_id: int, tag: str):
        self.task_id = task_id
        self.tag = tag
        self.message = f"Tag '{tag}' not found on task {task_id}"
        super().__init__(self.message)


class DuplicateUserError(Exception):
    """Raised when trying to register with an existing username or email"""

    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        self.message = f"{field.capitalize()} '{value}' is already registered"
        super().__init__(self.message)


class InvalidCredentialsError(Exception):
    """Raised when login credentials are incorrect"""

    def __init__(self):
        self.message = "Invalid username or password"
        super().__init__(self.message)
