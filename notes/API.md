# API

## Why do we have three separate Pydantic models (TaskCreate, TaskUpdate, Task) instead of just one?

Each model reflects what makes sense for that operation:
**TaskCreate** - Client provides title (required) + description (optional). They can't set id (server assigns it) or completed (defaults to false).
**TaskUpdate** - Everything optional. Client sends only what they want to change. If they could only send complete objects, they'd have to fetch the task first, modify it, then send the whole thing back.
**Task** - The complete picture. Server always returns the full object so clients know the current state.

This pattern has a name: **DTOs (Data Transfer Objects)** or sometimes called **schemas**. You'll see this in every professional API. One model for input, one for output, sometimes variations for different operations.

## Query Parameters

- Query parameters come from function arguments that aren't in the path and aren't Pydantic models. FastAPI figures out the difference automatically:

`{task_id}` in path → path parameter
`task_data: TaskCreate` → request body
`completed: Optional[bool] = None` → query parameter

