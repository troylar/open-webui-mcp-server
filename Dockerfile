FROM python:3.12-slim

WORKDIR /app

# Install uv for faster package installation
RUN pip install uv

# Copy pyproject.toml for dependency installation
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system fastmcp httpx pydantic uvicorn

# Copy application code
COPY src/ ./src/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=8000
ENV MCP_HTTP_PATH=/mcp

# Expose MCP port
EXPOSE 8000

# Run the server
CMD ["python", "-m", "src.openwebui_mcp.main"]
