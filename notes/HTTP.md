# HTTP Notes

## HTTP Request / Response Cycle

```
┌──────────┐         REQUEST           ┌──────────┐
│  Client  │ ──────────────────────▶   │  Server  │
│ (browser,│   - Method (GET/POST)     │  (your   │
│  curl,   │   - URL path              │  FastAPI │
│  app)    │   - Headers               │  app)    │
│          │   - Body (optional)       │          │
│          │                           │          │
│          │ ◀──────────────────────   │          │
│          │         RESPONSE          │          │
└──────────┘   - Status code (200)     └──────────┘
               - Headers
               - Body (JSON data)
```

## HTTP Methods: The Verbs of the Web

| Method | Intention | 
|--------|-----------|
| GET | Read data |
| POST | Write data |
| PUT | Create data | 
| PATH | Update data |
| DELETE | Delete data |

**CRUD**

- Create -> POST
- Read -> GET
- Update -> PUT/PATCH
- Delete -> DELETE

## Status Codes

**2XX - Success:**

`200 OK` - "Here's what you asked for"
`201 Created` - "I made the new thing you requested"
`204 No Content` - "Done, nothing to return"

**4XX - Client Error (your fault):**

`400 Bad Request` - "I don't understand what you sent"
`401 Unauthorized` - "Who are you?"
`403 Forbidden` - "I know who you are, but you can't do this"
`404 Not Found` - "That doesn't exist"
`422 Unprocessable Entity` - "I understnad the format but the data is wrong"

**5XX - Server Error (our fault):**
`500 Internal Server Error` - "Something broke on my end"
