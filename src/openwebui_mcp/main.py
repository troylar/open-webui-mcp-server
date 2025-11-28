"""Open WebUI MCP Server - Main entry point.

This MCP server exposes Open WebUI's API as MCP tools, allowing AI assistants
to manage users, groups, models, knowledge bases, and more.

IMPORTANT: All operations use the current user's session token automatically.
When configured with "session" auth in Open WebUI, the user's token is passed
through, ensuring all operations respect their permissions.
"""

import os
from typing import Any, Optional
from contextvars import ContextVar

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from .client import OpenWebUIClient

# Context variable to store the current user's token
_current_user_token: ContextVar[Optional[str]] = ContextVar("current_user_token", default=None)


class AuthMiddleware:
    """ASGI middleware to extract Authorization header and set context variable."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract Authorization header
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()

            # Extract Bearer token
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                _current_user_token.set(token)

        await self.app(scope, receive, send)

# Initialize MCP server
mcp = FastMCP(
    name="openwebui-mcp-server",
    version="0.1.0",
    description="MCP server for managing Open WebUI - users, groups, models, and more",
)

# Initialize client (URL from env)
_client: Optional[OpenWebUIClient] = None


def get_client() -> OpenWebUIClient:
    """Get or create the Open WebUI client."""
    global _client
    if _client is None:
        _client = OpenWebUIClient()
    return _client


def get_user_token() -> Optional[str]:
    """Get the current user's token from context or environment."""
    # First check context (set by middleware)
    token = _current_user_token.get()
    if token:
        return token
    # Fall back to environment variable
    return os.getenv("OPENWEBUI_API_KEY")


# =============================================================================
# Parameter Models - No more api_key fields, uses current user automatically
# =============================================================================


class UserIdParam(BaseModel):
    """Parameters requiring a user ID."""
    user_id: str = Field(description="User ID")


class UserRoleParam(BaseModel):
    """Parameters for updating user role."""
    user_id: str = Field(description="User ID")
    role: str = Field(description="New role: 'admin', 'user', or 'pending'")


class GroupCreateParam(BaseModel):
    """Parameters for creating a group."""
    name: str = Field(description="Group name")
    description: str = Field(default="", description="Group description")


class GroupIdParam(BaseModel):
    """Parameters requiring a group ID."""
    group_id: str = Field(description="Group ID")


class GroupUpdateParam(BaseModel):
    """Parameters for updating a group."""
    group_id: str = Field(description="Group ID")
    name: Optional[str] = Field(default=None, description="New group name")
    description: Optional[str] = Field(default=None, description="New group description")


class GroupUserParam(BaseModel):
    """Parameters for group user operations."""
    group_id: str = Field(description="Group ID")
    user_id: str = Field(description="User ID to add/remove")


class ModelCreateParam(BaseModel):
    """Parameters for creating a model."""
    id: str = Field(description="Model ID (slug-format, e.g., 'my-custom-model')")
    name: str = Field(description="Display name for the model")
    base_model_id: str = Field(description="Base model ID (e.g., 'gpt-4', 'claude-3-opus')")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for the model")
    temperature: Optional[float] = Field(default=None, description="Temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens for responses")


class ModelIdParam(BaseModel):
    """Parameters requiring a model ID."""
    model_id: str = Field(description="Model ID")


class ModelUpdateParam(BaseModel):
    """Parameters for updating a model."""
    model_id: str = Field(description="Model ID")
    name: Optional[str] = Field(default=None, description="New display name")
    system_prompt: Optional[str] = Field(default=None, description="New system prompt")
    temperature: Optional[float] = Field(default=None, description="New temperature")
    max_tokens: Optional[int] = Field(default=None, description="New max tokens")


class KnowledgeCreateParam(BaseModel):
    """Parameters for creating a knowledge base."""
    name: str = Field(description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")


class KnowledgeIdParam(BaseModel):
    """Parameters requiring a knowledge base ID."""
    knowledge_id: str = Field(description="Knowledge base ID")


class ChatIdParam(BaseModel):
    """Parameters requiring a chat ID."""
    chat_id: str = Field(description="Chat ID")


# =============================================================================
# User Management Tools
# =============================================================================


@mcp.tool()
async def get_current_user(ctx: Context) -> dict[str, Any]:
    """Get the currently authenticated user's profile.

    Returns information about YOU - your ID, name, email, role, and permissions.
    Uses your current session automatically.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_current_user(token)


@mcp.tool()
async def list_users(ctx: Context) -> dict[str, Any]:
    """List all users in Open WebUI.

    ADMIN ONLY: Returns 403 if you're not an admin.
    Returns a list of all users with their IDs, names, emails, and roles.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_users(token)


@mcp.tool()
async def get_user(params: UserIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific user.

    ADMIN ONLY: Returns 403 if you're not an admin.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_user(params.user_id, token)


@mcp.tool()
async def update_user_role(params: UserRoleParam, ctx: Context) -> dict[str, Any]:
    """Update a user's role.

    ADMIN ONLY: Returns 403 if you're not an admin.

    Roles:
    - 'admin': Full access to all features
    - 'user': Standard user access
    - 'pending': Awaiting approval
    """
    client = get_client()
    token = get_user_token()
    return await client.update_user_role(params.user_id, params.role, token)


@mcp.tool()
async def delete_user(params: UserIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a user from Open WebUI.

    ADMIN ONLY: Returns 403 if you're not an admin.
    WARNING: This action cannot be undone!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_user(params.user_id, token)


# =============================================================================
# Group Management Tools
# =============================================================================


@mcp.tool()
async def list_groups(ctx: Context) -> dict[str, Any]:
    """List all groups in Open WebUI.

    Returns all groups with their IDs, names, descriptions, and member counts.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_groups(token)


@mcp.tool()
async def create_group(params: GroupCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new group.

    ADMIN ONLY: Returns 403 if you're not an admin.
    Groups can be used to organize users and control access to resources.
    """
    client = get_client()
    token = get_user_token()
    return await client.create_group(params.name, params.description, token)


@mcp.tool()
async def get_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific group.

    Returns the group's name, description, and list of members.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_group(params.group_id, token)


@mcp.tool()
async def update_group(params: GroupUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a group's name or description.

    ADMIN ONLY: Returns 403 if you're not an admin.
    """
    client = get_client()
    token = get_user_token()
    return await client.update_group(params.group_id, params.name, params.description, token)


@mcp.tool()
async def add_user_to_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Add a user to a group.

    ADMIN ONLY: Returns 403 if you're not an admin.
    """
    client = get_client()
    token = get_user_token()
    return await client.add_user_to_group(params.group_id, params.user_id, token)


@mcp.tool()
async def remove_user_from_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Remove a user from a group.

    ADMIN ONLY: Returns 403 if you're not an admin.
    """
    client = get_client()
    token = get_user_token()
    return await client.remove_user_from_group(params.group_id, params.user_id, token)


@mcp.tool()
async def delete_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a group.

    ADMIN ONLY: Returns 403 if you're not an admin.
    WARNING: This will remove all users from the group!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_group(params.group_id, token)


# =============================================================================
# Model Management Tools
# =============================================================================


@mcp.tool()
async def list_models(ctx: Context) -> dict[str, Any]:
    """List all models in Open WebUI.

    Returns all available models including custom models, their IDs,
    names, and configurations.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_models(token)


@mcp.tool()
async def get_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific model.

    Returns the model's configuration including system prompt,
    parameters, and metadata.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_model(params.model_id, token)


@mcp.tool()
async def create_model(params: ModelCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new custom model.

    ADMIN ONLY: Returns 403 if you're not an admin.

    Creates a model wrapper with custom system prompt and parameters
    based on an existing base model.
    """
    client = get_client()
    token = get_user_token()

    meta = {}
    if params.system_prompt:
        meta["system"] = params.system_prompt

    model_params = {}
    if params.temperature is not None:
        model_params["temperature"] = params.temperature
    if params.max_tokens is not None:
        model_params["max_tokens"] = params.max_tokens

    return await client.create_model(
        id=params.id,
        name=params.name,
        base_model_id=params.base_model_id,
        meta=meta if meta else None,
        params=model_params if model_params else None,
        api_key=token,
    )


@mcp.tool()
async def update_model(params: ModelUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a model's configuration.

    Updates the model's name, system prompt, or parameters.
    """
    client = get_client()
    token = get_user_token()

    meta = None
    if params.system_prompt is not None:
        meta = {"system": params.system_prompt}

    model_params = None
    if params.temperature is not None or params.max_tokens is not None:
        model_params = {}
        if params.temperature is not None:
            model_params["temperature"] = params.temperature
        if params.max_tokens is not None:
            model_params["max_tokens"] = params.max_tokens

    return await client.update_model(
        model_id=params.model_id,
        name=params.name,
        meta=meta,
        params=model_params,
        api_key=token,
    )


@mcp.tool()
async def delete_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a custom model.

    ADMIN ONLY: Returns 403 if you're not an admin.
    WARNING: This action cannot be undone!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_model(params.model_id, token)


# =============================================================================
# Knowledge Base Management Tools
# =============================================================================


@mcp.tool()
async def list_knowledge_bases(ctx: Context) -> dict[str, Any]:
    """List all knowledge bases.

    Returns all knowledge bases with their IDs, names, and descriptions.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_knowledge(token)


@mcp.tool()
async def get_knowledge_base(params: KnowledgeIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific knowledge base.

    Returns the knowledge base's configuration and file list.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_knowledge(params.knowledge_id, token)


@mcp.tool()
async def create_knowledge_base(params: KnowledgeCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new knowledge base.

    Knowledge bases store documents for RAG (Retrieval Augmented Generation).
    """
    client = get_client()
    token = get_user_token()
    return await client.create_knowledge(params.name, params.description, token)


@mcp.tool()
async def delete_knowledge_base(params: KnowledgeIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a knowledge base.

    WARNING: This will delete all files in the knowledge base!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_knowledge(params.knowledge_id, token)


# =============================================================================
# Chat Management Tools
# =============================================================================


@mcp.tool()
async def list_chats(ctx: Context) -> dict[str, Any]:
    """List YOUR chats.

    Returns all chats for your account. You can only see your own chats.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_chats(token)


@mcp.tool()
async def get_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Get a specific chat's details and messages.

    Returns the full chat history. You can only access your own chats.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_chat(params.chat_id, token)


@mcp.tool()
async def delete_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Delete one of your chats.

    WARNING: This action cannot be undone!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_chat(params.chat_id, token)


@mcp.tool()
async def delete_all_chats(ctx: Context) -> dict[str, Any]:
    """Delete ALL of your chats.

    WARNING: This will delete ALL your chats and cannot be undone!
    """
    client = get_client()
    token = get_user_token()
    return await client.delete_all_chats(token)


# =============================================================================
# Tool & Function Management Tools
# =============================================================================


@mcp.tool()
async def list_tools(ctx: Context) -> dict[str, Any]:
    """List all available tools in Open WebUI.

    Returns all tools including MCP servers, OpenAPI tools, and custom tools.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_tools(token)


@mcp.tool()
async def list_functions(ctx: Context) -> dict[str, Any]:
    """List all functions (filters/pipes) in Open WebUI.

    Returns all custom functions including their IDs and configurations.
    """
    client = get_client()
    token = get_user_token()
    return await client.list_functions(token)


# =============================================================================
# System Tools
# =============================================================================


@mcp.tool()
async def get_system_config(ctx: Context) -> dict[str, Any]:
    """Get Open WebUI system configuration.

    ADMIN ONLY: Returns 403 if you're not an admin.
    """
    client = get_client()
    token = get_user_token()
    return await client.get_config(token)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    import sys

    # Check for required environment variable
    if not os.getenv("OPENWEBUI_URL"):
        print("ERROR: OPENWEBUI_URL environment variable is required", file=sys.stderr)
        print("Example: export OPENWEBUI_URL=https://ai.example.com", file=sys.stderr)
        sys.exit(1)

    # Get transport mode from environment
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_HTTP_PORT", "8000"))
    path = os.getenv("MCP_HTTP_PATH", "/mcp")

    if transport == "http":
        # For HTTP transport, wrap with auth middleware to extract tokens
        import uvicorn

        # Get the ASGI app from FastMCP and wrap with middleware
        app = mcp.http_app(path=path)
        app = AuthMiddleware(app)

        print(f"Starting Open WebUI MCP server on http://{host}:{port}{path}")
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
