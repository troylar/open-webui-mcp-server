"""Open WebUI MCP Server - Main entry point.

This MCP server exposes Open WebUI's API as MCP tools, allowing AI assistants
to manage users, groups, models, knowledge bases, and more.

IMPORTANT: All operations respect the currently logged-in user's permissions.
The user's Bearer token is passed through to Open WebUI, so admins can perform
admin operations while regular users are limited to their own resources.
"""

import os
from typing import Any, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .client import OpenWebUIClient

# Initialize MCP server
mcp = FastMCP(
    name="openwebui-mcp-server",
    version="0.1.0",
    description="MCP server for managing Open WebUI - users, groups, models, and more",
)

# Initialize client (URL from env, API key passed per-request)
_client: Optional[OpenWebUIClient] = None


def get_client() -> OpenWebUIClient:
    """Get or create the Open WebUI client."""
    global _client
    if _client is None:
        _client = OpenWebUIClient()
    return _client


# =============================================================================
# Parameter Models
# =============================================================================


class UserParams(BaseModel):
    """Parameters for user operations."""

    user_id: str = Field(description="User ID")
    api_key: Optional[str] = Field(
        default=None,
        description="Your Open WebUI API key (for authentication)",
    )


class UserRoleParams(BaseModel):
    """Parameters for updating user role."""

    user_id: str = Field(description="User ID")
    role: str = Field(description="New role: 'admin', 'user', or 'pending'")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class GroupCreateParams(BaseModel):
    """Parameters for creating a group."""

    name: str = Field(description="Group name")
    description: str = Field(default="", description="Group description")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class GroupParams(BaseModel):
    """Parameters for group operations."""

    group_id: str = Field(description="Group ID")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class GroupUpdateParams(BaseModel):
    """Parameters for updating a group."""

    group_id: str = Field(description="Group ID")
    name: Optional[str] = Field(default=None, description="New group name")
    description: Optional[str] = Field(default=None, description="New group description")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class GroupUserParams(BaseModel):
    """Parameters for group user operations."""

    group_id: str = Field(description="Group ID")
    user_id: str = Field(description="User ID to add/remove")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class ModelCreateParams(BaseModel):
    """Parameters for creating a model."""

    id: str = Field(description="Model ID (slug-format, e.g., 'my-custom-model')")
    name: str = Field(description="Display name for the model")
    base_model_id: str = Field(description="Base model ID (e.g., 'gpt-4', 'claude-3-opus')")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for the model")
    temperature: Optional[float] = Field(default=None, description="Temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens for responses")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class ModelParams(BaseModel):
    """Parameters for model operations."""

    model_id: str = Field(description="Model ID")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class ModelUpdateParams(BaseModel):
    """Parameters for updating a model."""

    model_id: str = Field(description="Model ID")
    name: Optional[str] = Field(default=None, description="New display name")
    system_prompt: Optional[str] = Field(default=None, description="New system prompt")
    temperature: Optional[float] = Field(default=None, description="New temperature")
    max_tokens: Optional[int] = Field(default=None, description="New max tokens")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class KnowledgeCreateParams(BaseModel):
    """Parameters for creating a knowledge base."""

    name: str = Field(description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class KnowledgeParams(BaseModel):
    """Parameters for knowledge base operations."""

    knowledge_id: str = Field(description="Knowledge base ID")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class ChatParams(BaseModel):
    """Parameters for chat operations."""

    chat_id: str = Field(description="Chat ID")
    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


class ApiKeyParams(BaseModel):
    """Parameters requiring only API key."""

    api_key: Optional[str] = Field(default=None, description="Your Open WebUI API key")


# =============================================================================
# User Management Tools
# =============================================================================


@mcp.tool()
async def get_current_user(params: ApiKeyParams) -> dict[str, Any]:
    """Get the currently authenticated user's profile.

    Returns information about the user making the request, including
    their ID, name, email, role, and permissions.
    """
    client = get_client()
    return await client.get_current_user(params.api_key)


@mcp.tool()
async def list_users(params: ApiKeyParams) -> dict[str, Any]:
    """List all users in Open WebUI.

    ADMIN ONLY: Requires admin permissions.
    Returns a list of all users with their IDs, names, emails, and roles.
    """
    client = get_client()
    return await client.list_users(params.api_key)


@mcp.tool()
async def get_user(params: UserParams) -> dict[str, Any]:
    """Get details for a specific user.

    ADMIN ONLY: Requires admin permissions to view other users.
    """
    client = get_client()
    return await client.get_user(params.user_id, params.api_key)


@mcp.tool()
async def update_user_role(params: UserRoleParams) -> dict[str, Any]:
    """Update a user's role.

    ADMIN ONLY: Requires admin permissions.

    Roles:
    - 'admin': Full access to all features
    - 'user': Standard user access
    - 'pending': Awaiting approval
    """
    client = get_client()
    return await client.update_user_role(params.user_id, params.role, params.api_key)


@mcp.tool()
async def delete_user(params: UserParams) -> dict[str, Any]:
    """Delete a user from Open WebUI.

    ADMIN ONLY: Requires admin permissions.
    WARNING: This action cannot be undone!
    """
    client = get_client()
    return await client.delete_user(params.user_id, params.api_key)


# =============================================================================
# Group Management Tools
# =============================================================================


@mcp.tool()
async def list_groups(params: ApiKeyParams) -> dict[str, Any]:
    """List all groups in Open WebUI.

    Returns all groups with their IDs, names, descriptions, and member counts.
    """
    client = get_client()
    return await client.list_groups(params.api_key)


@mcp.tool()
async def create_group(params: GroupCreateParams) -> dict[str, Any]:
    """Create a new group.

    ADMIN ONLY: Requires admin permissions.
    Groups can be used to organize users and control access to resources.
    """
    client = get_client()
    return await client.create_group(params.name, params.description, params.api_key)


@mcp.tool()
async def get_group(params: GroupParams) -> dict[str, Any]:
    """Get details for a specific group.

    Returns the group's name, description, and list of members.
    """
    client = get_client()
    return await client.get_group(params.group_id, params.api_key)


@mcp.tool()
async def update_group(params: GroupUpdateParams) -> dict[str, Any]:
    """Update a group's name or description.

    ADMIN ONLY: Requires admin permissions.
    """
    client = get_client()
    return await client.update_group(
        params.group_id, params.name, params.description, params.api_key
    )


@mcp.tool()
async def add_user_to_group(params: GroupUserParams) -> dict[str, Any]:
    """Add a user to a group.

    ADMIN ONLY: Requires admin permissions.
    """
    client = get_client()
    return await client.add_user_to_group(params.group_id, params.user_id, params.api_key)


@mcp.tool()
async def remove_user_from_group(params: GroupUserParams) -> dict[str, Any]:
    """Remove a user from a group.

    ADMIN ONLY: Requires admin permissions.
    """
    client = get_client()
    return await client.remove_user_from_group(params.group_id, params.user_id, params.api_key)


@mcp.tool()
async def delete_group(params: GroupParams) -> dict[str, Any]:
    """Delete a group.

    ADMIN ONLY: Requires admin permissions.
    WARNING: This will remove all users from the group!
    """
    client = get_client()
    return await client.delete_group(params.group_id, params.api_key)


# =============================================================================
# Model Management Tools
# =============================================================================


@mcp.tool()
async def list_models(params: ApiKeyParams) -> dict[str, Any]:
    """List all models in Open WebUI.

    Returns all available models including custom models, their IDs,
    names, and configurations.
    """
    client = get_client()
    return await client.list_models(params.api_key)


@mcp.tool()
async def get_model(params: ModelParams) -> dict[str, Any]:
    """Get details for a specific model.

    Returns the model's configuration including system prompt,
    parameters, and metadata.
    """
    client = get_client()
    return await client.get_model(params.model_id, params.api_key)


@mcp.tool()
async def create_model(params: ModelCreateParams) -> dict[str, Any]:
    """Create a new custom model.

    ADMIN ONLY: Requires admin permissions.

    Creates a model wrapper with custom system prompt and parameters
    based on an existing base model.
    """
    client = get_client()

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
        api_key=params.api_key,
    )


@mcp.tool()
async def update_model(params: ModelUpdateParams) -> dict[str, Any]:
    """Update a model's configuration.

    Updates the model's name, system prompt, or parameters.
    """
    client = get_client()

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
        api_key=params.api_key,
    )


@mcp.tool()
async def delete_model(params: ModelParams) -> dict[str, Any]:
    """Delete a custom model.

    ADMIN ONLY: Requires admin permissions.
    WARNING: This action cannot be undone!
    """
    client = get_client()
    return await client.delete_model(params.model_id, params.api_key)


# =============================================================================
# Knowledge Base Management Tools
# =============================================================================


@mcp.tool()
async def list_knowledge_bases(params: ApiKeyParams) -> dict[str, Any]:
    """List all knowledge bases.

    Returns all knowledge bases with their IDs, names, and descriptions.
    """
    client = get_client()
    return await client.list_knowledge(params.api_key)


@mcp.tool()
async def get_knowledge_base(params: KnowledgeParams) -> dict[str, Any]:
    """Get details for a specific knowledge base.

    Returns the knowledge base's configuration and file list.
    """
    client = get_client()
    return await client.get_knowledge(params.knowledge_id, params.api_key)


@mcp.tool()
async def create_knowledge_base(params: KnowledgeCreateParams) -> dict[str, Any]:
    """Create a new knowledge base.

    Knowledge bases store documents for RAG (Retrieval Augmented Generation).
    """
    client = get_client()
    return await client.create_knowledge(params.name, params.description, params.api_key)


@mcp.tool()
async def delete_knowledge_base(params: KnowledgeParams) -> dict[str, Any]:
    """Delete a knowledge base.

    WARNING: This will delete all files in the knowledge base!
    """
    client = get_client()
    return await client.delete_knowledge(params.knowledge_id, params.api_key)


# =============================================================================
# Chat Management Tools
# =============================================================================


@mcp.tool()
async def list_chats(params: ApiKeyParams) -> dict[str, Any]:
    """List the current user's chats.

    Returns all chats for the authenticated user.
    """
    client = get_client()
    return await client.list_chats(params.api_key)


@mcp.tool()
async def get_chat(params: ChatParams) -> dict[str, Any]:
    """Get a specific chat's details and messages.

    Returns the full chat history including all messages.
    """
    client = get_client()
    return await client.get_chat(params.chat_id, params.api_key)


@mcp.tool()
async def delete_chat(params: ChatParams) -> dict[str, Any]:
    """Delete a chat.

    WARNING: This action cannot be undone!
    """
    client = get_client()
    return await client.delete_chat(params.chat_id, params.api_key)


@mcp.tool()
async def delete_all_chats(params: ApiKeyParams) -> dict[str, Any]:
    """Delete all of the current user's chats.

    WARNING: This will delete ALL your chats and cannot be undone!
    """
    client = get_client()
    return await client.delete_all_chats(params.api_key)


# =============================================================================
# Tool & Function Management Tools
# =============================================================================


@mcp.tool()
async def list_tools(params: ApiKeyParams) -> dict[str, Any]:
    """List all available tools in Open WebUI.

    Returns all tools including MCP servers, OpenAPI tools, and custom tools.
    """
    client = get_client()
    return await client.list_tools(params.api_key)


@mcp.tool()
async def list_functions(params: ApiKeyParams) -> dict[str, Any]:
    """List all functions (filters/pipes) in Open WebUI.

    Returns all custom functions including their IDs and configurations.
    """
    client = get_client()
    return await client.list_functions(params.api_key)


# =============================================================================
# System Tools
# =============================================================================


@mcp.tool()
async def get_system_config(params: ApiKeyParams) -> dict[str, Any]:
    """Get Open WebUI system configuration.

    ADMIN ONLY: Returns system settings and configuration.
    """
    client = get_client()
    return await client.get_config(params.api_key)


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
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
