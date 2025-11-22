```bash
# Create project directory
mkdir task-manager-api
cd task-manager-api

# Create virtual environment (isolates dependencies)
python3 -m venv venv
source venv/bin/activate

# Install FastAPI + Uvicorn (the server that runs FastAPI)
pip install fastapi uvicorn

# Initialize Git
git init
echo "venv/" > .gitignore
echo "__pycache__/" >> .gitignore
```

- **Why virtual environments?** Same reason you use separate Terraform workspaces—isolation. Project A might need library version 1.0, Project B needs version 2.0. Virtual environments keep them separate.

- **Why Uvicorn?** FastAPI is just the framework. Uvicorn is an ASGI server—it's what actually listens on a port and handles incoming HTTP requests. Think of FastAPI as the application code, Uvicorn as the web server (like nginx, but built for Python async apps).